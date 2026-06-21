"""
ADCC — Confidence Engine
=========================
Computes a structured confidence score for disaster event reports by
cross-referencing multiple independent data sources.

Scoring Model (total = 100 points):
    GDACS Match      → 40 pts  (strongest signal — official global alert)
    Weather Match    → 30 pts  (physical conditions support the disaster type)
    News Match       → 20 pts  (media coverage confirms the event)
    Historical Match → 10 pts  (region historically affected by this type)

Thresholds:
    ≥ 90  → Verified
    70–89 → High Confidence
    50–69 → Medium Confidence
    < 50  → Low Confidence

Used by:
    agents/verification_agent.py → calls calculate_confidence() per event

Functions:
    calculate_confidence()          → ConfidenceResult
    determine_verification_status() → str
    generate_confidence_report()    → ConfidenceReport
"""

from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field


# ===========================================================================
# SCORING CONSTANTS
# ===========================================================================

SCORE_GDACS_FULL       = 40
SCORE_GDACS_PARTIAL    = 25
SCORE_GDACS_NONE       = 0

SCORE_WEATHER_FULL     = 30
SCORE_WEATHER_PARTIAL  = 18
SCORE_WEATHER_NONE     = 0

SCORE_NEWS_FULL        = 20
SCORE_NEWS_PARTIAL_HIGH= 15
SCORE_NEWS_PARTIAL_LOW = 8
SCORE_NEWS_NONE        = 0

SCORE_HISTORY_FULL     = 10
SCORE_HISTORY_NONE     = 0

# Thresholds
THRESHOLD_VERIFIED     = 90
THRESHOLD_HIGH         = 70
THRESHOLD_MEDIUM       = 50

# Weather thresholds per disaster type
WEATHER_THRESHOLDS: dict[str, dict[str, float]] = {
    "Flood":     {"rainfall_min_mm": 20.0, "rainfall_high_mm": 50.0},
    "Cyclone":   {"wind_min_kmh": 80.0, "wind_high_kmh": 120.0},
    "Heatwave":  {"temp_min_c": 40.0, "temp_high_c": 45.0},
    "Earthquake":{},
    "Wildfire":  {"temp_min_c": 35.0, "humidity_max": 30.0, "wind_min_kmh": 30.0},
    "Landslide": {"rainfall_min_mm": 30.0, "rainfall_high_mm": 60.0},
    "Tsunami":   {},
}

# India historical risk map
HISTORICAL_RISK_MAP: dict[str, list[str]] = {
    "assam":          ["Flood"],
    "bihar":          ["Flood"],
    "west bengal":    ["Flood", "Cyclone"],
    "odisha":         ["Flood", "Cyclone"],
    "kerala":         ["Flood", "Landslide"],
    "uttarakhand":    ["Flood", "Landslide"],
    "himachal":       ["Landslide", "Flood"],
    "andaman":        ["Cyclone", "Tsunami"],
    "andhra":         ["Cyclone", "Flood"],
    "tamil nadu":     ["Cyclone", "Flood"],
    "gujarat":        ["Cyclone", "Earthquake"],
    "kashmir":        ["Earthquake"],
    "jammu":          ["Earthquake"],
    "manipur":        ["Earthquake"],
    "sikkim":         ["Earthquake", "Landslide"],
    "mumbai":         ["Flood"],
    "chennai":        ["Flood", "Cyclone"],
    "kolkata":        ["Flood", "Cyclone"],
    "delhi":          ["Heatwave", "Flood"],
}


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================


class ComponentScore(BaseModel):
    """Score and reasoning for a single scoring component."""
    component:     str
    max_points:    int
    earned_points: float
    match_level:   str    # "Full", "Partial", "None"
    reason:        str


class ConfidenceResult(BaseModel):
    """Raw confidence calculation output."""
    total_score:          float
    verification_status:  str
    components:           list[ComponentScore]
    computed_at:          datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConfidenceReport(BaseModel):
    """Full structured verification report for one disaster event."""
    event_title:          str
    event_type:           str
    location:             str
    confidence_score:     float
    verification_status:  str
    sources_confirmed:    list[str]
    sources_checked:      list[str]
    component_scores:     list[ComponentScore]
    summary:              str
    computed_at:          datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ===========================================================================
# COMPONENT SCORERS
# ===========================================================================


def _score_gdacs(event_type: str, gdacs_events: list[dict]) -> ComponentScore:
    """Scores GDACS match: 40pts (Red/Orange), 25pts (Green), 0pts (none)."""
    type_map: dict[str, list[str]] = {
        "Flood":      ["FL", "Flood"],
        "Cyclone":    ["TC", "Tropical Cyclone"],
        "Earthquake": ["EQ", "Earthquake"],
        "Wildfire":   ["WF", "Wild Fire"],
        "Tsunami":    ["TS", "Tsunami"],
        "Landslide":  ["FL"],
        "Heatwave":   ["DR"],
    }
    target_codes = type_map.get(event_type, [event_type])

    if not gdacs_events:
        return ComponentScore(
            component="GDACS", max_points=SCORE_GDACS_FULL,
            earned_points=SCORE_GDACS_NONE, match_level="None",
            reason="No GDACS events in state",
        )

    matching = [
        e for e in gdacs_events
        if e.get("event_type") in target_codes
        or e.get("event_type_label", "").lower() in [c.lower() for c in target_codes]
    ]

    if not matching:
        return ComponentScore(
            component="GDACS", max_points=SCORE_GDACS_FULL,
            earned_points=SCORE_GDACS_NONE, match_level="None",
            reason=f"No GDACS {event_type} event among {len(gdacs_events)} active events",
        )

    red_orange = [e for e in matching if e.get("alert_level") in ("Red", "Orange")]
    if red_orange:
        best = red_orange[0]
        return ComponentScore(
            component="GDACS", max_points=SCORE_GDACS_FULL,
            earned_points=SCORE_GDACS_FULL, match_level="Full",
            reason=f"GDACS confirmed: '{best.get('title')}' [{best.get('alert_level')}]",
        )
    else:
        best = matching[0]
        return ComponentScore(
            component="GDACS", max_points=SCORE_GDACS_FULL,
            earned_points=SCORE_GDACS_PARTIAL, match_level="Partial",
            reason=f"GDACS {event_type} found (Green alert only): '{best.get('title')}'",
        )


def _score_weather(event_type: str, weather_data: Optional[dict]) -> ComponentScore:
    """Scores weather match based on physical conditions vs disaster type."""
    if not weather_data:
        return ComponentScore(
            component="Weather", max_points=SCORE_WEATHER_FULL,
            earned_points=SCORE_WEATHER_NONE, match_level="None",
            reason="No weather data in state",
        )

    t    = WEATHER_THRESHOLDS.get(event_type, {})
    rain = weather_data.get("rainfall_mm", 0.0) or 0.0
    wind = weather_data.get("wind_speed_kmh", 0.0) or 0.0
    temp = weather_data.get("temperature_c", 25.0) or 25.0
    hum  = weather_data.get("humidity_percent", 50.0) or 50.0

    if event_type in ("Earthquake", "Tsunami"):
        return ComponentScore(
            component="Weather", max_points=SCORE_WEATHER_FULL,
            earned_points=SCORE_WEATHER_PARTIAL, match_level="Partial",
            reason=f"Weather not directly relevant for {event_type}",
        )

    if event_type == "Flood":
        if rain >= t.get("rainfall_high_mm", 50.0) or weather_data.get("flood_risk"):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_FULL, match_level="Full",
                reason=f"Heavy rainfall: {rain}mm/hr — flood conditions confirmed")
        elif rain >= t.get("rainfall_min_mm", 20.0):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_PARTIAL, match_level="Partial",
                reason=f"Moderate rainfall: {rain}mm/hr")

    elif event_type == "Cyclone":
        if wind >= t.get("wind_high_kmh", 120.0) or weather_data.get("cyclone_risk"):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_FULL, match_level="Full",
                reason=f"Cyclone-level winds: {wind}km/h")
        elif wind >= t.get("wind_min_kmh", 80.0):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_PARTIAL, match_level="Partial",
                reason=f"Strong winds: {wind}km/h (below cyclone threshold)")

    elif event_type == "Heatwave":
        if temp >= t.get("temp_high_c", 45.0):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_FULL, match_level="Full",
                reason=f"Extreme heat: {temp}°C")
        elif temp >= t.get("temp_min_c", 40.0):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_PARTIAL, match_level="Partial",
                reason=f"High temperature: {temp}°C")

    elif event_type == "Wildfire":
        if (temp >= t.get("temp_min_c", 35.0)
                and hum <= t.get("humidity_max", 30.0)
                and wind >= t.get("wind_min_kmh", 30.0)):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_FULL, match_level="Full",
                reason=f"Wildfire conditions: Temp={temp}°C, Humidity={hum}%, Wind={wind}km/h")
        elif temp >= t.get("temp_min_c", 35.0):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_PARTIAL, match_level="Partial",
                reason=f"High temp ({temp}°C) but not all wildfire conditions met")

    elif event_type == "Landslide":
        if rain >= t.get("rainfall_high_mm", 60.0):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_FULL, match_level="Full",
                reason=f"Extreme rainfall {rain}mm/hr — landslide risk high")
        elif rain >= t.get("rainfall_min_mm", 30.0):
            return ComponentScore(component="Weather", max_points=SCORE_WEATHER_FULL,
                earned_points=SCORE_WEATHER_PARTIAL, match_level="Partial",
                reason=f"Moderate rainfall {rain}mm/hr")

    return ComponentScore(
        component="Weather", max_points=SCORE_WEATHER_FULL,
        earned_points=SCORE_WEATHER_NONE, match_level="None",
        reason=f"Weather does not support {event_type} (Rain={rain}mm Wind={wind}km/h Temp={temp}°C)",
    )


def _score_news(
    event_type: str,
    event_title: str,
    country: str,
    news_articles: list[dict],
) -> ComponentScore:
    """Scores news: 20pts (3+ articles), 15pts (2), 8pts (1), 0pts (none)."""
    if not news_articles:
        return ComponentScore(
            component="News", max_points=SCORE_NEWS_FULL,
            earned_points=SCORE_NEWS_NONE, match_level="None",
            reason="No news articles available",
        )

    title_words  = {w.lower() for w in event_title.split() if len(w) > 3}
    country_low  = country.lower()

    matching = []
    for art in news_articles:
        text = ((art.get("title") or "") + " " + (art.get("description") or "")).lower()
        type_match    = art.get("disaster_type") == event_type
        title_match   = any(w in text for w in title_words)
        country_match = country_low in text or art.get("country", "").lower() == country_low

        if (type_match or title_match) and country_match:
            matching.append(art)
        elif type_match and not matching:
            matching.append(art)

    n = len(matching)
    if n >= 3:
        return ComponentScore(component="News", max_points=SCORE_NEWS_FULL,
            earned_points=SCORE_NEWS_FULL, match_level="Full",
            reason=f"{n} news articles confirm {event_type}: '{matching[0].get('title','')[:60]}'")
    elif n == 2:
        return ComponentScore(component="News", max_points=SCORE_NEWS_FULL,
            earned_points=SCORE_NEWS_PARTIAL_HIGH, match_level="Partial",
            reason=f"2 articles confirm: '{matching[0].get('title','')[:60]}'")
    elif n == 1:
        return ComponentScore(component="News", max_points=SCORE_NEWS_FULL,
            earned_points=SCORE_NEWS_PARTIAL_LOW, match_level="Partial",
            reason=f"1 article confirms: '{matching[0].get('title','')[:60]}'")
    else:
        return ComponentScore(component="News", max_points=SCORE_NEWS_FULL,
            earned_points=SCORE_NEWS_NONE, match_level="None",
            reason=f"No matching articles for {event_type} in {country} ({len(news_articles)} total checked)")


def _score_historical(event_type: str, location_text: str) -> ComponentScore:
    """Scores historical susceptibility: 10pts (known region), 5pts (India generic), 0pts (none)."""
    loc = location_text.lower()

    for region, types in HISTORICAL_RISK_MAP.items():
        if region in loc and event_type in types:
            return ComponentScore(
                component="Historical", max_points=SCORE_HISTORY_FULL,
                earned_points=SCORE_HISTORY_FULL, match_level="Full",
                reason=f"'{region.title()}' historically susceptible to {event_type}",
            )

    india_common = ["Flood", "Cyclone", "Earthquake"]
    if event_type in india_common and "india" in loc:
        return ComponentScore(
            component="Historical", max_points=SCORE_HISTORY_FULL,
            earned_points=5, match_level="Partial",
            reason=f"India has general susceptibility to {event_type}",
        )

    return ComponentScore(
        component="Historical", max_points=SCORE_HISTORY_FULL,
        earned_points=SCORE_HISTORY_NONE, match_level="None",
        reason=f"No historical {event_type} pattern for '{location_text}'",
    )


# ===========================================================================
# PUBLIC FUNCTIONS
# ===========================================================================


def determine_verification_status(score: float) -> str:
    """
    Maps confidence score (0–100) to verification status string.

    Returns:
        "Verified" (≥90) | "High Confidence" (70–89) |
        "Medium Confidence" (50–69) | "Low Confidence" (<50)

    Example:
        >>> determine_verification_status(94.0)
        'Verified'
    """
    if score >= THRESHOLD_VERIFIED:
        return "Verified"
    elif score >= THRESHOLD_HIGH:
        return "High Confidence"
    elif score >= THRESHOLD_MEDIUM:
        return "Medium Confidence"
    else:
        return "Low Confidence"


def calculate_confidence(
    event_type: str,
    event_title: str,
    country: str,
    gdacs_events: Optional[list[dict]] = None,
    weather_data: Optional[dict] = None,
    news_articles: Optional[list[dict]] = None,
    location_label: Optional[str] = None,
) -> ConfidenceResult:
    """
    Calculates composite confidence score (0–100) for a disaster event.

    Args:
        event_type:     "Flood", "Cyclone", "Earthquake", "Wildfire", etc.
        event_title:    Full event title for keyword matching
        country:        Country of occurrence
        gdacs_events:   GDACSEventState dicts from DisasterState
        weather_data:   WeatherStateData dict from DisasterState
        news_articles:  NewsArticle dicts from news_tool
        location_label: Location string for historical matching

    Returns:
        ConfidenceResult: Score, status, component breakdown

    Example:
        >>> result = calculate_confidence("Flood", "Mumbai Flooding", "India",
        ...     gdacs_events=state["disaster_events"],
        ...     weather_data=state["weather_data"])
        >>> print(result.total_score, result.verification_status)
    """
    logger.info(f"[ConfidenceEngine] Scoring '{event_title}' [{event_type}] — {country}")

    location   = location_label or f"{event_title}, {country}"
    components = [
        _score_gdacs(event_type, gdacs_events or []),
        _score_weather(event_type, weather_data),
        _score_news(event_type, event_title, country, news_articles or []),
        _score_historical(event_type, location),
    ]

    total  = round(min(100.0, max(0.0, sum(c.earned_points for c in components))), 2)
    status = determine_verification_status(total)

    logger.info(
        f"[ConfidenceEngine] {event_type} → {total:.1f}/100 [{status}] | "
        + " | ".join(f"{c.component}={c.earned_points}/{c.max_points}" for c in components)
    )

    return ConfidenceResult(total_score=total, verification_status=status, components=components)


def generate_confidence_report(
    event_type: str,
    event_title: str,
    country: str,
    gdacs_events: Optional[list[dict]] = None,
    weather_data: Optional[dict] = None,
    news_articles: Optional[list[dict]] = None,
    location_label: Optional[str] = None,
) -> ConfidenceReport:
    """
    Generates a full ConfidenceReport with score, source breakdown, and narrative.
    Primary function called by verification_agent.py per disaster event.

    Returns:
        ConfidenceReport: Complete verification report

    Example:
        >>> report = generate_confidence_report(
        ...     "Flood", "Bihar River Flood", "India",
        ...     gdacs_events=state["disaster_events"],
        ...     weather_data=state["weather_data"],
        ...     news_articles=[a.model_dump() for a in news.articles],
        ... )
        >>> print(report.confidence_score, report.verification_status)
        >>> print(report.summary)
    """
    result   = calculate_confidence(event_type, event_title, country,
                                    gdacs_events, weather_data, news_articles, location_label)
    score    = result.total_score
    status   = result.verification_status
    location = location_label or f"{event_title}, {country}"

    source_map = {
        "GDACS":      "GDACS",
        "Weather":    "Open-Meteo",
        "News":       "NewsAPI/Google News",
        "Historical": "Historical Risk DB",
    }
    sources_checked   = list(source_map.values())
    sources_confirmed = [
        source_map[c.component]
        for c in result.components
        if c.match_level in ("Full", "Partial")
    ]

    # Narrative summary
    confirmed_str = ", ".join(sources_confirmed) if sources_confirmed else "none"
    if score >= THRESHOLD_VERIFIED:
        summary = (
            f"[VERIFIED] '{event_title}' confirmed at {score:.0f}% confidence. "
            f"Independent sources agree: {confirmed_str}. Immediate response recommended."
        )
    elif score >= THRESHOLD_HIGH:
        summary = (
            f"[HIGH CONFIDENCE] '{event_title}' likely real ({score:.0f}%). "
            f"Confirmed by: {confirmed_str}. Proceed with response planning."
        )
    elif score >= THRESHOLD_MEDIUM:
        summary = (
            f"[MEDIUM CONFIDENCE] '{event_title}' possible but not fully confirmed ({score:.0f}%). "
            f"Supporting: {confirmed_str}. Continue monitoring before full deployment."
        )
    else:
        summary = (
            f"[LOW CONFIDENCE] '{event_title}' cannot be reliably confirmed ({score:.0f}%). "
            f"Insufficient evidence. Do not deploy resources — manual verification needed."
        )

    report = ConfidenceReport(
        event_title=event_title, event_type=event_type, location=location,
        confidence_score=score, verification_status=status,
        sources_confirmed=sources_confirmed, sources_checked=sources_checked,
        component_scores=result.components, summary=summary,
    )

    logger.success(f"[ConfidenceEngine] Report ready: '{event_title}' → {status} ({score:.0f}%)")
    return report
