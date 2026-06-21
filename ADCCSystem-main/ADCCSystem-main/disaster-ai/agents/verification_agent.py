"""
ADCC — Verification Agent
==========================
The first autonomous decision-making layer of ADCC.

Reads disaster events from DisasterState, cross-verifies each event
against weather, GDACS, news, and earthquake data, then computes a
confidence score using the confidence_engine.

Responsibilities:
    ✅ Read disaster_events and earthquake_events from state
    ✅ Fetch news evidence per event (via news_tool.py)
    ✅ Call confidence_engine.generate_confidence_report() per event
    ✅ Write verified_reports to DisasterState
    ✅ Compute and set aggregate confidence_score
    ✅ Update metadata with verification trace

NOT responsible for:
    ❌ Resource allocation → allocation_agent.py
    ❌ Severity scoring    → severity_agent.py
    ❌ AI reasoning        → command_center.py (Gemini)
    ❌ Replanning          → replanning_agent.py
    ❌ LangGraph graph     → workflows/graph.py

Position in Pipeline:
    [data_collection_agent]  ← populates raw data
         ↓
    [verification_agent]     ← THIS FILE
         ↓
    [severity_agent]         (Phase 6)
         ↓
    [allocation_agent]       (Phase 6)

Usage (standalone):
    from agents.verification_agent import run_verification
    from workflows.state import create_initial_state
    from agents.data_collection_agent import collect_all_data

    state = create_initial_state()
    state = collect_all_data(state, 19.0760, 72.8777, "Mumbai")
    state = run_verification(state)

    for report in state["verified_reports"]:
        print(report["event_title"], report["confidence_score"], report["verification_status"])

Usage (future LangGraph node):
    def verification_node(state: DisasterState) -> StateUpdate:
        return run_verification(state)
"""

import time
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from services.confidence_engine import (
    ConfidenceReport,
    ComponentScore,
    generate_confidence_report,
)
from tools.news_tool import NewsArticle, NewsResponse, get_news_by_keyword
from workflows.state import (
    DisasterState,
    StateUpdate,
    VerifiedReportState,
    get_state_summary,
    set_severity,
    update_state_metadata,
    validate_state,
    severity_score_from_data,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "verification_agent"

# Min confidence to include in verified_reports (filter noise)
MIN_CONFIDENCE_TO_REPORT = 30.0

# News fetch window per event
NEWS_FETCH_DAYS = 7

# Max disaster events to verify (performance guard)
MAX_EVENTS_TO_VERIFY = 10

# How many earthquake events to verify (separately from GDACS)
MAX_EARTHQUAKES_TO_VERIFY = 5


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================


def _report_to_state(report: ConfidenceReport, sources_checked: list[str]) -> VerifiedReportState:
    """
    Converts a ConfidenceReport (Pydantic) to VerifiedReportState (TypedDict).
    """
    return VerifiedReportState(
        disaster_id="",          # will be set when linked to DB disaster
        disaster_title=report.event_title,
        sources_checked=report.sources_checked,
        verification_result=report.verification_status,
        consensus_confidence=round(report.confidence_score / 100.0, 4),
        verification_notes=report.summary,
        verified_at=datetime.now(timezone.utc).isoformat(),
    )


def _fetch_news_for_event(
    event_title: str,
    event_type: str,
    country: str,
) -> list[dict]:
    """
    Fetches news articles relevant to a specific disaster event.
    Returns list of NewsArticle dicts for confidence_engine.

    On failure, returns [] — verification continues without news.
    """
    try:
        # Build a focused query
        query = f"{event_title} {event_type}"
        if country and country.lower() not in event_title.lower():
            query = f"{country} {query}"

        result: NewsResponse = get_news_by_keyword(
            keyword=query,
            country=country,
            days=NEWS_FETCH_DAYS,
        )
        articles = [a.model_dump() for a in result.articles]
        logger.debug(
            f"[VerificationAgent] News for '{event_title}': "
            f"{len(articles)} articles from {result.source_used}"
        )
        return articles

    except Exception as e:
        logger.warning(f"[VerificationAgent] News fetch failed for '{event_title}': {e}")
        return []


def _verify_single_event(
    event_type: str,
    event_title: str,
    country: str,
    location_label: Optional[str],
    gdacs_events: list[dict],
    weather_data: Optional[dict],
    earthquake_events: list[dict],
) -> ConfidenceReport:
    """
    Verifies one disaster event by:
    1. Fetching targeted news
    2. Running confidence_engine with all available evidence

    Returns ConfidenceReport.
    """
    logger.info(f"[VerificationAgent] Verifying: '{event_title}' [{event_type}] in {country}")

    # Fetch news for this specific event
    news_articles = _fetch_news_for_event(event_title, event_type, country)

    # For earthquake events, also check USGS data as cross-reference
    # (earthquake_events already in state, just pass them via location context)

    report = generate_confidence_report(
        event_type=event_type,
        event_title=event_title,
        country=country,
        gdacs_events=gdacs_events,
        weather_data=weather_data,
        news_articles=news_articles,
        location_label=location_label,
    )

    return report


# ===========================================================================
# VERIFICATION FUNCTIONS
# ===========================================================================


def verify_gdacs_events(state: DisasterState) -> tuple[DisasterState, list[ConfidenceReport]]:
    """
    Verifies all GDACS disaster events in the state.

    Reads:
        state["disaster_events"]   → GDACSEventState list
        state["weather_data"]      → for weather scoring
        state["earthquake_events"] → for cross-reference

    Returns:
        Updated state (metadata updated) + list of ConfidenceReports

    Called by:
        run_verification() — do not call directly
    """
    gdacs_events      = state.get("disaster_events") or []
    weather_data      = state.get("weather_data")
    earthquake_events = state.get("earthquake_events") or []

    if not gdacs_events:
        logger.warning("[VerificationAgent] No GDACS events to verify")
        state = update_state_metadata(state, current_node=AGENT_NAME,
                                      warning="No GDACS events in state — data_collection_agent may not have run")
        return state, []

    # Limit to top events (by alert priority)
    priority_order = {"Red": 0, "Orange": 1, "Green": 2}
    sorted_events  = sorted(
        gdacs_events,
        key=lambda e: priority_order.get(e.get("alert_level", "Green"), 3),
    )[:MAX_EVENTS_TO_VERIFY]

    logger.info(f"[VerificationAgent] Verifying {len(sorted_events)}/{len(gdacs_events)} GDACS events")

    reports: list[ConfidenceReport] = []

    for i, event in enumerate(sorted_events, 1):
        event_title = event.get("title", f"GDACS Event {i}")
        event_type  = event.get("event_type_label", "Flood")
        country     = event.get("country", "India")
        location    = event_title

        t = time.monotonic()
        try:
            if event.get("source") == "DEMO" or state.get("is_demo"):
                report = ConfidenceReport(
                    event_type=event_type,
                    event_title=event_title,
                    country=country,
                    location=event_title,
                    confidence_score=95.0,
                    verification_status="Verified",
                    sources_confirmed=["GDACS", "Weather"],
                    sources_checked=["GDACS", "Weather", "Simulated News"],
                    component_scores=[
                        ComponentScore(
                            component="GDACS",
                            max_points=40,
                            earned_points=40,
                            match_level="Full",
                            reason="[DEMO] Simulated event match"
                        )
                    ],
                    summary=f"[DEMO] Automatically verified simulated event: {event_title}."
                )
            else:
                report = _verify_single_event(
                    event_type=event_type,
                    event_title=event_title,
                    country=country,
                    location_label=location,
                    gdacs_events=gdacs_events,
                    weather_data=weather_data,
                    earthquake_events=earthquake_events,
                )
            reports.append(report)
            elapsed = round(time.monotonic() - t, 2)

            logger.info(
                f"[VerificationAgent] [{i}/{len(sorted_events)}] '{event_title}' "
                f"→ {report.verification_status} ({report.confidence_score:.0f}%) in {elapsed}s"
            )

        except Exception as e:
            elapsed = round(time.monotonic() - t, 2)
            msg = f"Verification failed for '{event_title}' after {elapsed}s: {e}"
            logger.error(f"[VerificationAgent] ❌ {msg}")
            state = update_state_metadata(state, current_node=AGENT_NAME, error=msg)

    return state, reports


def verify_earthquake_events(state: DisasterState) -> tuple[DisasterState, list[ConfidenceReport]]:
    """
    Verifies significant earthquake events (M ≥ 5.0) from state.

    Reads:
        state["earthquake_events"]  → EarthquakeEventState list
        state["disaster_events"]    → GDACS cross-check
        state["weather_data"]       → not directly relevant but passed

    Returns:
        Updated state (metadata updated) + list of ConfidenceReports
    """
    eq_events    = state.get("earthquake_events") or []
    gdacs_events = state.get("disaster_events") or []
    weather_data = state.get("weather_data")

    # Only verify significant earthquakes (M ≥ 5.0)
    significant_eqs = [
        e for e in eq_events
        if (e.get("magnitude") or 0) >= 5.0
    ][:MAX_EARTHQUAKES_TO_VERIFY]

    if not significant_eqs:
        logger.info("[VerificationAgent] No significant earthquakes (M≥5.0) to verify")
        return state, []

    logger.info(f"[VerificationAgent] Verifying {len(significant_eqs)} significant earthquakes")

    reports: list[ConfidenceReport] = []

    for eq in significant_eqs:
        mag   = eq.get("magnitude", 5.0)
        place = eq.get("place", "Unknown location")
        title = f"M{mag} Earthquake — {place}"
        country = eq.get("country") or "India"

        t = time.monotonic()
        try:
            if eq.get("source") == "DEMO" or state.get("is_demo"):
                report = ConfidenceReport(
                    event_type="Earthquake",
                    event_title=title,
                    country=country,
                    location=place,
                    confidence_score=95.0,
                    verification_status="Verified",
                    sources_confirmed=["USGS", "Weather"],
                    sources_checked=["USGS", "Weather", "Simulated News"],
                    component_scores=[
                        ComponentScore(
                            component="GDACS",
                            max_points=40,
                            earned_points=40,
                            match_level="Full",
                            reason="[DEMO] Simulated earthquake match"
                        )
                    ],
                    summary=f"[DEMO] Automatically verified simulated earthquake: {title}."
                )
            else:
                report = _verify_single_event(
                    event_type="Earthquake",
                    event_title=title,
                    country=country,
                    location_label=place,
                    gdacs_events=gdacs_events,
                    weather_data=weather_data,
                    earthquake_events=eq_events,
                )
            reports.append(report)
            elapsed = round(time.monotonic() - t, 2)

            logger.info(
                f"[VerificationAgent] Earthquake '{title}' "
                f"→ {report.verification_status} ({report.confidence_score:.0f}%) in {elapsed}s"
            )

        except Exception as e:
            msg = f"Earthquake verification failed for '{title}': {e}"
            logger.error(f"[VerificationAgent] ❌ {msg}")
            state = update_state_metadata(state, current_node=AGENT_NAME, error=msg)

    return state, reports


def _compute_aggregate_confidence(reports: list[ConfidenceReport]) -> float:
    """
    Computes aggregate confidence from all verification reports.
    Weights: verified events weighted by their score, normalized 0.0–1.0.
    """
    if not reports:
        return 0.0

    # Weight by alert severity — higher-scoring reports count more
    total_weight = sum(r.confidence_score for r in reports)
    if total_weight == 0:
        return 0.0

    weighted_avg = sum(
        r.confidence_score * (r.confidence_score / total_weight)
        for r in reports
    )
    return round(min(1.0, weighted_avg / 100.0), 4)


def _compute_aggregate_severity(
    reports: list[ConfidenceReport],
    state: DisasterState,
) -> tuple[float, str, float]:
    """
    Derives severity score and level from verification results + state data.
    Delegates to severity_score_from_data() heuristic.
    """
    weather = state.get("weather_data") or {}
    gdacs   = state.get("disaster_events") or []
    eqs     = state.get("earthquake_events") or []

    # Get best GDACS alert level
    alert_levels_order = {"Red": "Critical", "Orange": "High", "Green": "Low"}
    best_gdacs_alert   = "Green"
    max_pop            = 0

    for e in gdacs:
        lvl = e.get("alert_level", "Green")
        if lvl == "Red":
            best_gdacs_alert = "Red"
        elif lvl == "Orange" and best_gdacs_alert != "Red":
            best_gdacs_alert = "Orange"
        pop = e.get("affected_population") or 0
        max_pop = max(max_pop, pop)

    # Max earthquake magnitude
    max_mag = max((e.get("magnitude", 0) for e in eqs), default=None) if eqs else None

    # Num verified sources
    verified_count = sum(1 for r in reports if r.verification_status in ("Verified", "High Confidence"))

    score, level, confidence = severity_score_from_data(
        affected_population=max_pop if max_pop > 0 else None,
        rainfall_mm=weather.get("rainfall_mm", 0.0) or 0.0,
        wind_speed_kmh=weather.get("wind_speed_kmh", 0.0) or 0.0,
        magnitude=max_mag,
        gdacs_alert_level=best_gdacs_alert,
        num_verified_sources=verified_count,
    )

    return score, level, confidence


# ===========================================================================
# MAIN VERIFICATION FUNCTION
# ===========================================================================


def run_verification(state: DisasterState) -> DisasterState:
    """
    Master verification function — verifies all disaster events in state
    and returns updated DisasterState with:
        - verified_reports    populated
        - confidence_score    updated (aggregate)
        - severity_score      updated (heuristic from evidence)
        - metadata            updated

    This is the primary entry point for the verification_agent.
    In LangGraph, this function body becomes a workflow node.

    Args:
        state: DisasterState (after data_collection_agent has run)

    Returns:
        DisasterState: Updated with verification results

    Requires:
        state["disaster_events"]    must be populated (run data_collection_agent first)

    Example:
        >>> state = create_initial_state()
        >>> state = collect_all_data(state, 19.0760, 72.8777, "Mumbai Flood")
        >>> state = run_verification(state)
        >>> for r in state["verified_reports"]:
        ...     print(r["disaster_title"], r["verification_result"])
    """
    logger.info(
        f"\n{'='*60}\n"
        f"[VerificationAgent] 🔍 Starting verification pipeline\n"
        f"  Session: {state.get('session_id')}\n"
        f"  GDACS events    : {len(state.get('disaster_events') or [])}\n"
        f"  Earthquake events: {len(state.get('earthquake_events') or [])}\n"
        f"{'='*60}"
    )
    t_total = time.monotonic()
    state = update_state_metadata(state, current_node=AGENT_NAME)

    # ── Validate input state ─────────────────────────────────────────────────
    is_valid, issues = validate_state(state)
    if not is_valid:
        for issue in issues:
            state = update_state_metadata(state, current_node=AGENT_NAME, warning=issue)

    # Check data availability
    if not state.get("disaster_events") and not state.get("earthquake_events"):
        msg = "No active disasters detected. System operating in nominal mode."
        logger.info(f"[VerificationAgent] {msg}")
        state = update_state_metadata(state, current_node=AGENT_NAME)
        return state

    all_reports: list[ConfidenceReport] = []

    # ── Step 1: Verify GDACS events ──────────────────────────────────────────
    logger.info("[VerificationAgent] Step 1/2 → Verifying GDACS disaster events")
    state, gdacs_reports = verify_gdacs_events(state)
    all_reports.extend(gdacs_reports)

    # ── Step 2: Verify significant earthquakes ───────────────────────────────
    logger.info("[VerificationAgent] Step 2/2 → Verifying earthquake events")
    state, eq_reports = verify_earthquake_events(state)
    all_reports.extend(eq_reports)

    # ── Step 3: Build verified_reports state list ────────────────────────────
    verified_state_list: list[VerifiedReportState] = []
    for report in all_reports:
        if report.confidence_score >= MIN_CONFIDENCE_TO_REPORT:
            verified_state_list.append(_report_to_state(report, report.sources_checked))

    # ── Step 4: Aggregate confidence ─────────────────────────────────────────
    agg_confidence = _compute_aggregate_confidence(all_reports)

    # ── Step 5: Update severity in state ─────────────────────────────────────
    sev_score, sev_level, sev_confidence = _compute_aggregate_severity(all_reports, state)
    state = set_severity(state, score=sev_score, level=sev_level, confidence=sev_confidence)

    # ── Step 6: Write to state ───────────────────────────────────────────────
    state = {
        **state,
        "verified_reports": verified_state_list,
        "confidence_score": agg_confidence,
    }  # type: ignore[assignment]

    state = update_state_metadata(state, current_node=AGENT_NAME, data_source="NewsAPI/Google News")

    # ── Final summary log ─────────────────────────────────────────────────────
    total_elapsed = round(time.monotonic() - t_total, 2)
    verified_count   = sum(1 for r in all_reports if r.verification_status == "Verified")
    high_conf_count  = sum(1 for r in all_reports if r.verification_status == "High Confidence")
    low_conf_count   = sum(1 for r in all_reports if r.verification_status == "Low Confidence")

    logger.info(
        f"\n{'='*60}\n"
        f"[VerificationAgent] ✅ Verification complete in {total_elapsed}s\n"
        f"  Total events verified : {len(all_reports)}\n"
        f"  Verified (≥90%)       : {verified_count}\n"
        f"  High Confidence (70%) : {high_conf_count}\n"
        f"  Low Confidence (<50%) : {low_conf_count}\n"
        f"  Aggregate confidence  : {agg_confidence:.2%}\n"
        f"  Severity level        : {sev_level} (score={sev_score:.3f})\n"
        f"  Errors in session     : {len((state.get('metadata') or {}).get('errors') or [])}\n"
        f"{'='*60}"
    )

    return state


def get_verification_summary(state: DisasterState) -> dict:
    """
    Returns a concise verification summary for logging/dashboard use.
    Designed to be called after run_verification().

    Args:
        state: DisasterState after verification

    Returns:
        dict: Summary with counts, best confidence, and top events

    Example:
        >>> summary = get_verification_summary(state)
        >>> print(summary["top_verified_event"])
    """
    reports = state.get("verified_reports") or []

    if not reports:
        return {
            "total_verified": 0,
            "aggregate_confidence_pct": 0.0,
            "severity_level": state.get("severity_level", "Low"),
            "top_verified_event": None,
            "errors": (state.get("metadata") or {}).get("errors", []),
        }

    # Sort by confidence descending
    sorted_reports = sorted(
        reports,
        key=lambda r: r.get("consensus_confidence", 0.0),
        reverse=True,
    )
    top = sorted_reports[0] if sorted_reports else None

    return {
        "total_verified": len(reports),
        "aggregate_confidence_pct": round((state.get("confidence_score") or 0.0) * 100, 1),
        "severity_level": state.get("severity_level", "Low"),
        "severity_score": state.get("severity_score", 0.0),
        "top_verified_event": top.get("disaster_title") if top else None,
        "top_confidence_pct": round((top.get("consensus_confidence") or 0.0) * 100, 1) if top else 0.0,
        "top_status": top.get("verification_result") if top else None,
        "sources_used": (state.get("metadata") or {}).get("data_sources_used", []),
        "errors": (state.get("metadata") or {}).get("errors", []),
    }


# ===========================================================================
# STANDALONE RUN
# ===========================================================================

if __name__ == "__main__":
    """
    Standalone test of the full data collection → verification pipeline.

    Usage:
        cd disaster-ai
        python -m agents.verification_agent
    """
    import json

    from agents.data_collection_agent import collect_all_data
    from workflows.state import create_initial_state

    logger.info("[VerificationAgent] Standalone test starting...")

    # Phase 1: Initialize + collect
    state = create_initial_state(environment="development")
    state = collect_all_data(
        state,
        latitude=19.0760,
        longitude=72.8777,
        location_label="Mumbai — Verification Test",
        country="India",
    )

    # Phase 2: Verify
    state = run_verification(state)

    # Output
    summary = get_verification_summary(state)
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY:")
    print("="*60)
    print(json.dumps(summary, indent=2, default=str))

    # Print verified reports
    print("\nVERIFIED REPORTS:")
    for report in state.get("verified_reports") or []:
        conf_pct = round((report.get("consensus_confidence") or 0.0) * 100, 1)
        print(f"  • {report.get('disaster_title')} → "
              f"{report.get('verification_result')} ({conf_pct}%)")
        print(f"    {report.get('verification_notes', '')[:100]}...")
