"""
ADCC — Data Collection Agent
==============================
First agent in the ADCC pipeline. Responsible ONLY for fetching raw data
from all external sources and populating the DisasterState.

Responsibilities:
    ✅ Fetch weather data           (Open-Meteo via weather_tool.py)
    ✅ Fetch active disasters       (GDACS via gdacs_tool.py)
    ✅ Fetch recent earthquakes     (USGS via disaster_tool.py)
    ✅ Fetch resource availability  (PostgreSQL via resource_tool.py)
    ✅ Update DisasterState fields
    ✅ Update state metadata (nodes_visited, data_sources_used, errors)

NOT responsible for:
    ❌ Severity analysis   → severity_agent.py
    ❌ Verification        → verification_agent.py
    ❌ Resource allocation → allocation_agent.py
    ❌ AI reasoning        → command_center.py
    ❌ Gemini calls        → not in this phase
    ❌ LangGraph graph     → not in this phase

Position in Pipeline:
    [create_initial_state]
         ↓
    [data_collection_agent]  ← THIS FILE
         ↓
    [severity_agent]         (Phase 5)
         ↓
    [verification_agent]     (Phase 5)
         ↓
    [allocation_agent]       (Phase 5)
         ↓
    [command_center]         (Phase 5)

Usage (standalone):
    from agents.data_collection_agent import collect_all_data
    from workflows.state import create_initial_state

    state = create_initial_state()
    state = collect_all_data(
        state,
        latitude=19.0760,
        longitude=72.8777,
        location_label="Mumbai Flood Zone",
    )
    print(state["weather_data"])
    print(state["disaster_events"])

Usage (future LangGraph node):
    def data_collection_node(state: DisasterState) -> StateUpdate:
        return collect_all_data(state, lat=..., lon=...)
"""

import time
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from tools.disaster_tool import (
    EarthquakeResponse,
    get_india_earthquakes,
    get_recent_earthquakes,
)
from tools.gdacs_tool import (
    GDACSResponse,
    get_active_disasters,
    get_disaster_by_country,
)
from tools.resource_tool import (
    ResourceSummary,
    get_available_resources,
    get_resource_summary,
    get_resources_near,
)
from tools.weather_tool import (
    DisasterWeatherReport,
    get_disaster_weather,
)
from workflows.state import (
    DisasterState,
    EarthquakeEventState,
    GDACSEventState,
    ResourceStateData,
    StateUpdate,
    WeatherStateData,
    create_initial_state,
    get_state_summary,
    update_state_metadata,
    validate_state,
)

# ---------------------------------------------------------------------------
# Agent constants
# ---------------------------------------------------------------------------

AGENT_NAME = "data_collection_agent"

# Default query params — can be overridden per call
DEFAULT_EARTHQUAKE_MIN_MAG = 4.0
DEFAULT_EARTHQUAKE_DAYS    = 7
DEFAULT_GDACS_EVENT_TYPES  = ["EQ", "FL", "TC", "VO", "WF"]
DEFAULT_GDACS_ALERT_LEVELS = ["Red", "Orange", "Green"]
DEFAULT_RESOURCE_RADIUS_KM = 300.0


# ===========================================================================
# NORMALIZERS
# (Convert tool Pydantic model → plain dict for DisasterState storage)
# ===========================================================================

def _normalize_weather(report: DisasterWeatherReport) -> WeatherStateData:
    """
    Converts DisasterWeatherReport (Pydantic) → WeatherStateData (TypedDict).
    Flattens the nested current/forecast structure into a flat state dict.
    """
    current  = report.current
    forecast = report.forecast_7day

    return WeatherStateData(
        latitude=report.latitude,
        longitude=report.longitude,
        location_label=report.location_label,

        # Current conditions
        temperature_c=current.temperature_c,
        rainfall_mm=current.rainfall_mm,
        humidity_percent=current.humidity_percent,
        wind_speed_kmh=current.wind_speed_kmh,
        wind_direction_deg=current.wind_direction_deg,
        weather_description=current.weather_description,
        is_day=current.is_day,

        # Risk flags
        flood_risk=current.flood_risk,
        cyclone_risk=current.cyclone_risk,

        # Forecast summary
        forecast_days=forecast.days_requested,
        max_rainfall_mm=forecast.max_rainfall_mm,
        max_wind_kmh=forecast.max_wind_kmh,
        flood_risk_hours=forecast.flood_risk_hours,

        # Agent output
        risk_summary=report.risk_summary,
        source="Open-Meteo",
        source_url="https://open-meteo.com",
        fetched_at=report.fetched_at.isoformat(),
    )


def _normalize_gdacs_event(event) -> GDACSEventState:
    """Converts GDACSEvent (Pydantic) → GDACSEventState (TypedDict)."""
    return GDACSEventState(
        event_id=event.event_id,
        event_type=event.event_type,
        event_type_label=event.event_type_label,
        alert_level=event.alert_level,
        severity_mapped=event.severity_mapped,
        alert_score=event.alert_score,
        country=event.country,
        latitude=event.latitude,
        longitude=event.longitude,
        title=event.title,
        description=event.description,
        url=event.url,
        affected_population=event.affected_population,
        event_date=event.event_date,
        source="GDACS",
        source_url="https://www.gdacs.org",
    )


def _normalize_earthquake(eq) -> EarthquakeEventState:
    """Converts EarthquakeEvent (Pydantic) → EarthquakeEventState (TypedDict)."""
    return EarthquakeEventState(
        usgs_id=eq.usgs_id,
        usgs_url=eq.usgs_url,
        magnitude=eq.magnitude,
        magnitude_type=eq.magnitude_type,
        depth_km=eq.depth_km,
        depth_label=eq.depth_label,
        latitude=eq.latitude,
        longitude=eq.longitude,
        place=eq.place,
        country=eq.country,
        severity_mapped=eq.severity_mapped,
        event_time=eq.event_time.isoformat(),
        event_time_ist=eq.event_time_ist,
        felt_reports=eq.felt_reports,
        tsunami_risk=eq.tsunami_risk,
        alert_level=eq.alert_level,
        significance=eq.significance,
        source="USGS",
        source_url=eq.source_url,
    )


def _normalize_resources(
    summary: ResourceSummary,
    nearest: list,
    available: list,
) -> ResourceStateData:
    """
    Converts ResourceSummary + resource lists → ResourceStateData (TypedDict).
    """
    return ResourceStateData(
        total_resources=summary.total_resources,
        available_count=summary.available_count,
        busy_count=summary.busy_count,
        maintenance_count=summary.maintenance_count,
        boats_available=summary.boats_available,
        ambulances_available=summary.ambulances_available,
        medical_teams_available=summary.medical_teams_available,
        rescue_teams_available=summary.rescue_teams_available,
        ndrf_units_available=summary.ndrf_units_available,
        available_resources=[r.model_dump() for r in available],
        nearest_resources=[r.model_dump() for r in nearest],
        fetched_at=summary.fetched_at.isoformat(),
    )


# ===========================================================================
# INDIVIDUAL COLLECTION FUNCTIONS
# ===========================================================================


def collect_weather_data(
    state: DisasterState,
    latitude: float,
    longitude: float,
    location_label: Optional[str] = None,
) -> DisasterState:
    """
    Fetches current + 7-day forecast weather for the disaster zone
    and stores the result in state["weather_data"].

    Args:
        state:          Current DisasterState
        latitude:       Disaster zone latitude (WGS84)
        longitude:      Disaster zone longitude (WGS84)
        location_label: Optional human label (e.g. "Mumbai Flood Zone")

    Returns:
        Updated DisasterState with weather_data populated

    State Changes:
        state["weather_data"]       ← WeatherStateData
        state["metadata"]           ← current_node, data_sources_used updated

    On Error:
        weather_data stays None, error logged in state["metadata"]["errors"]

    Example:
        >>> state = collect_weather_data(state, 19.0760, 72.8777, "Mumbai")
        >>> print(state["weather_data"]["temperature_c"])
    """
    state = update_state_metadata(state, current_node=f"{AGENT_NAME}:collect_weather")
    logger.info(f"[DataAgent] Collecting weather data for ({latitude:.4f}, {longitude:.4f})")
    t_start = time.monotonic()

    try:
        report: DisasterWeatherReport = get_disaster_weather(
            latitude=latitude,
            longitude=longitude,
            location_label=location_label,
        )

        weather_state = _normalize_weather(report)
        elapsed = round(time.monotonic() - t_start, 2)

        logger.success(
            f"[DataAgent] ✅ Weather collected in {elapsed}s | "
            f"Temp={weather_state['temperature_c']}°C | "
            f"Rain={weather_state['rainfall_mm']}mm | "
            f"FloodRisk={weather_state['flood_risk']}"
        )

        state = update_state_metadata(state, current_node=AGENT_NAME, data_source="Open-Meteo")
        return {**state, "weather_data": weather_state}  # type: ignore[return-value]

    except Exception as e:
        elapsed = round(time.monotonic() - t_start, 2)
        msg = f"Weather data collection failed after {elapsed}s: {e}"
        logger.error(f"[DataAgent] ❌ {msg}")
        state = update_state_metadata(state, current_node=AGENT_NAME, error=msg)
        return state  # weather_data stays None


def collect_disaster_data(
    state: DisasterState,
    event_types: Optional[list[str]] = None,
    alert_levels: Optional[list[str]] = None,
    country: Optional[str] = None,
    limit: int = 50,
) -> DisasterState:
    """
    Fetches active disaster events from GDACS and stores them in
    state["disaster_events"].

    Args:
        state:        Current DisasterState
        event_types:  GDACS event type codes (default: EQ, FL, TC, VO, WF)
        alert_levels: Alert levels to include (default: Red, Orange, Green)
        country:      If set, filter by country name (e.g. "India")
        limit:        Max events to fetch (default 50)

    Returns:
        Updated DisasterState with disaster_events populated

    State Changes:
        state["disaster_events"]    ← list[GDACSEventState]
        state["metadata"]           ← data_sources_used = ["GDACS"]

    On Error:
        disaster_events stays [], error logged in metadata

    Example:
        >>> state = collect_disaster_data(state, country="India", limit=20)
        >>> print(len(state["disaster_events"]), "events fetched")
    """
    state = update_state_metadata(state, current_node=f"{AGENT_NAME}:collect_gdacs")
    logger.info(f"[DataAgent] Collecting GDACS disaster data (country={country or 'global'}, limit={limit})")
    t_start = time.monotonic()

    try:
        if country:
            gdacs_result: GDACSResponse = get_disaster_by_country(
                country_name=country,
                event_types=event_types or DEFAULT_GDACS_EVENT_TYPES,
                limit=limit,
            )
        else:
            gdacs_result: GDACSResponse = get_active_disasters(
                event_types=event_types or DEFAULT_GDACS_EVENT_TYPES,
                alert_levels=alert_levels or DEFAULT_GDACS_ALERT_LEVELS,
                limit=limit,
            )

        events = [_normalize_gdacs_event(e) for e in gdacs_result.events]
        elapsed = round(time.monotonic() - t_start, 2)

        # Preserve pre-existing live/demo events
        existing_events = state.get("disaster_events") or []
        injected_events = [e for e in existing_events if e.get("source") in ("LIVE", "DEMO")]
        combined_events = injected_events + events

        # Count by alert level for logging
        red    = sum(1 for e in combined_events if e.get("alert_level") == "Red")
        orange = sum(1 for e in combined_events if e.get("alert_level") == "Orange")

        logger.success(
            f"[DataAgent] ✅ GDACS data collected in {elapsed}s | "
            f"Total={len(combined_events)} | Red={red} | Orange={orange}"
        )

        state = update_state_metadata(state, current_node=AGENT_NAME, data_source="GDACS")
        return {**state, "disaster_events": combined_events}  # type: ignore[return-value]

    except Exception as e:
        elapsed = round(time.monotonic() - t_start, 2)
        msg = f"GDACS data collection failed after {elapsed}s: {e}"
        logger.error(f"[DataAgent] ❌ {msg}")
        state = update_state_metadata(state, current_node=AGENT_NAME, error=msg)
        return {**state, "disaster_events": []}  # type: ignore[return-value]


def collect_earthquake_data(
    state: DisasterState,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: float = 500.0,
    minmagnitude: float = DEFAULT_EARTHQUAKE_MIN_MAG,
    days: int = DEFAULT_EARTHQUAKE_DAYS,
    india_only: bool = True,
) -> DisasterState:
    """
    Fetches recent earthquake events from USGS and stores them in
    state["earthquake_events"].

    Strategy:
        - If latitude/longitude provided → get_earthquakes_near() (location-specific)
        - If india_only=True            → get_india_earthquakes() (India bounding box)
        - Else                          → get_recent_earthquakes() (global)

    Args:
        state:         Current DisasterState
        latitude:      Optional centre latitude for location-specific query
        longitude:     Optional centre longitude for location-specific query
        radius_km:     Radius for location-specific query (default 500km)
        minmagnitude:  Minimum magnitude (default 4.0)
        days:          Look-back days (default 7)
        india_only:    If True and no lat/lon given, restrict to India (default True)

    Returns:
        Updated DisasterState with earthquake_events populated

    State Changes:
        state["earthquake_events"]  ← list[EarthquakeEventState]
        state["metadata"]           ← data_sources_used = ["USGS"]

    Example:
        >>> state = collect_earthquake_data(state, latitude=19.07, longitude=72.87, radius_km=300)
        >>> print(state["earthquake_events"][0]["magnitude"])
    """
    state = update_state_metadata(state, current_node=f"{AGENT_NAME}:collect_usgs")

    if latitude is not None and longitude is not None:
        logger.info(
            f"[DataAgent] Collecting USGS earthquakes near ({latitude:.4f}, {longitude:.4f}) "
            f"radius={radius_km}km M≥{minmagnitude}"
        )
    elif india_only:
        logger.info(f"[DataAgent] Collecting USGS India earthquakes M≥{minmagnitude} past {days} days")
    else:
        logger.info(f"[DataAgent] Collecting USGS global earthquakes M≥{minmagnitude} past {days} days")

    t_start = time.monotonic()

    try:
        if latitude is not None and longitude is not None:
            from tools.disaster_tool import get_earthquakes_near
            result: EarthquakeResponse = get_earthquakes_near(
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
                days=days,
                minmagnitude=minmagnitude,
            )
        elif india_only:
            result: EarthquakeResponse = get_india_earthquakes(
                days=days,
                minmagnitude=minmagnitude,
            )
        else:
            result: EarthquakeResponse = get_recent_earthquakes(
                minmagnitude=minmagnitude,
                days=days,
            )

        events = [_normalize_earthquake(eq) for eq in result.events]
        elapsed = round(time.monotonic() - t_start, 2)

        # Preserve pre-existing live/demo events
        existing_eqs = state.get("earthquake_events") or []
        injected_eqs = [e for e in existing_eqs if e.get("source") in ("LIVE", "DEMO")]
        combined_eqs = injected_eqs + events

        # Count significant events
        significant = sum(1 for e in combined_eqs if e.get("magnitude", 0) >= 5.5)
        tsunami_risk = sum(1 for e in combined_eqs if e.get("tsunami_risk", False))

        logger.success(
            f"[DataAgent] ✅ USGS data collected in {elapsed}s | "
            f"Total={len(combined_eqs)} | M≥5.5={significant} | TsunamiRisk={tsunami_risk}"
        )

        state = update_state_metadata(state, current_node=AGENT_NAME, data_source="USGS")
        return {**state, "earthquake_events": combined_eqs}  # type: ignore[return-value]

    except Exception as e:
        elapsed = round(time.monotonic() - t_start, 2)
        msg = f"USGS earthquake data collection failed after {elapsed}s: {e}"
        logger.error(f"[DataAgent] ❌ {msg}")
        state = update_state_metadata(state, current_node=AGENT_NAME, error=msg)
        return {**state, "earthquake_events": []}  # type: ignore[return-value]


def collect_resource_data(
    state: DisasterState,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    radius_km: float = DEFAULT_RESOURCE_RADIUS_KM,
) -> DisasterState:
    """
    Fetches resource availability from PostgreSQL and stores in
    state["resources"].

    Args:
        state:      Current DisasterState
        latitude:   Optional disaster zone lat (for nearest-resource sort)
        longitude:  Optional disaster zone lon (for nearest-resource sort)
        radius_km:  Search radius for nearest resources (default 300km)

    Returns:
        Updated DisasterState with resources populated

    State Changes:
        state["resources"]      ← ResourceStateData with summary + lists
        state["metadata"]       ← data_sources_used = ["PostgreSQL-Resources"]

    On Error:
        resources stays None, error logged in metadata

    Example:
        >>> state = collect_resource_data(state, latitude=19.07, longitude=72.87)
        >>> print(state["resources"]["available_count"])
    """
    state = update_state_metadata(state, current_node=f"{AGENT_NAME}:collect_resources")
    logger.info(f"[DataAgent] Collecting resource data (radius={radius_km}km)")
    t_start = time.monotonic()

    try:
        # Get overall summary
        summary: ResourceSummary = get_resource_summary()

        # Get all available resources
        available = get_available_resources()

        # Get nearest resources if location provided
        nearest = []
        if latitude is not None and longitude is not None:
            nearest = get_resources_near(
                latitude=latitude,
                longitude=longitude,
                radius_km=radius_km,
                status="Available",
            )
            logger.info(f"[DataAgent] Found {len(nearest)} resources within {radius_km}km of disaster zone")

        resource_state = _normalize_resources(summary, nearest, available)
        elapsed = round(time.monotonic() - t_start, 2)

        logger.success(
            f"[DataAgent] ✅ Resources collected in {elapsed}s | "
            f"Available={summary.available_count}/{summary.total_resources} | "
            f"Boats={summary.boats_available} | NDRF={summary.ndrf_units_available} | "
            f"Nearest={len(nearest)}"
        )

        state = update_state_metadata(state, current_node=AGENT_NAME, data_source="PostgreSQL-Resources")
        return {**state, "resources": resource_state}  # type: ignore[return-value]

    except Exception as e:
        elapsed = round(time.monotonic() - t_start, 2)
        msg = f"Resource data collection failed after {elapsed}s: {e}"
        logger.error(f"[DataAgent] ❌ {msg}")
        state = update_state_metadata(state, current_node=AGENT_NAME, error=msg)
        return state  # resources stays None


# ===========================================================================
# MAIN COLLECTION FUNCTION
# ===========================================================================


def collect_all_data(
    state: DisasterState,
    latitude: float,
    longitude: float,
    location_label: Optional[str] = None,
    country: Optional[str] = "India",
    earthquake_radius_km: float = 500.0,
    resource_radius_km: float = DEFAULT_RESOURCE_RADIUS_KM,
    earthquake_min_mag: float = DEFAULT_EARTHQUAKE_MIN_MAG,
    earthquake_days: int = DEFAULT_EARTHQUAKE_DAYS,
    gdacs_event_types: Optional[list[str]] = None,
    gdacs_alert_levels: Optional[list[str]] = None,
    skip_weather: bool = False,
    skip_gdacs: bool = False,
    skip_usgs: bool = False,
    skip_resources: bool = False,
) -> DisasterState:
    """
    Master data collection function — calls all 4 individual collectors
    in sequence and returns a fully populated DisasterState.

    This is the primary entry point for the data_collection_agent.
    In LangGraph, this function body will become a workflow node.

    Args:
        state:                 Current DisasterState (from create_initial_state())
        latitude:              Disaster zone latitude
        longitude:             Disaster zone longitude
        location_label:        Optional human label (e.g. "Mumbai Flood Zone")
        country:               Country for GDACS filtering (default "India")
        earthquake_radius_km:  USGS radius for location-specific search (default 500km)
        resource_radius_km:    DB radius for nearest-resource search (default 300km)
        earthquake_min_mag:    Min USGS magnitude (default 4.0)
        earthquake_days:       USGS look-back window in days (default 7)
        gdacs_event_types:     GDACS event type filter (default all)
        gdacs_alert_levels:    GDACS alert level filter (default all)
        skip_weather:          Set True to skip weather collection
        skip_gdacs:            Set True to skip GDACS collection
        skip_usgs:             Set True to skip USGS collection
        skip_resources:        Set True to skip resource collection

    Returns:
        DisasterState: Fully populated state with:
            - weather_data       (if not skipped)
            - disaster_events    (if not skipped)
            - earthquake_events  (if not skipped)
            - resources          (if not skipped)
            - metadata updated with all sources used and any errors

    State is always returned even if some collections fail — partial data
    is better than no data for disaster response.

    Example:
        >>> from workflows.state import create_initial_state
        >>> state = create_initial_state()
        >>> state = collect_all_data(
        ...     state,
        ...     latitude=19.0760,
        ...     longitude=72.8777,
        ...     location_label="Mumbai Coastal Flood",
        ...     country="India",
        ... )
        >>> from workflows.state import get_state_summary
        >>> print(get_state_summary(state))
    """
    logger.info(
        f"\n{'='*60}\n"
        f"[DataAgent] 🚀 Starting full data collection\n"
        f"  Location : {location_label or f'({latitude}, {longitude})'}\n"
        f"  Session  : {state.get('session_id')}\n"
        f"{'='*60}"
    )
    t_total_start = time.monotonic()

    # Mark agent start in metadata
    state = update_state_metadata(state, current_node=AGENT_NAME)

    if state.get("is_demo"):
        logger.info("[DataAgent] 🚀 Demo Mode Active. Injecting pre-seeded scenario state.")
        state = update_state_metadata(state, current_node=AGENT_NAME, data_source="Demo Telemetry")
        if not skip_resources:
            state = collect_resource_data(state, latitude=latitude, longitude=longitude, radius_km=resource_radius_km)
        return state

    # ── 1. Weather ────────────────────────────────────────────────────────────
    if not skip_weather:
        logger.info("[DataAgent] Step 1/4 → Weather data")
        state = collect_weather_data(
            state,
            latitude=latitude,
            longitude=longitude,
            location_label=location_label,
        )
    else:
        logger.info("[DataAgent] Step 1/4 → Weather data (SKIPPED)")

    # ── 2. GDACS Disasters ────────────────────────────────────────────────────
    if not skip_gdacs:
        logger.info("[DataAgent] Step 2/4 → GDACS disaster data")
        state = collect_disaster_data(
            state,
            event_types=gdacs_event_types,
            alert_levels=gdacs_alert_levels,
            country=country,
        )
    else:
        logger.info("[DataAgent] Step 2/4 → GDACS data (SKIPPED)")

    # ── 3. USGS Earthquakes ───────────────────────────────────────────────────
    if not skip_usgs:
        logger.info("[DataAgent] Step 3/4 → USGS earthquake data")
        state = collect_earthquake_data(
            state,
            latitude=latitude,
            longitude=longitude,
            radius_km=earthquake_radius_km,
            minmagnitude=earthquake_min_mag,
            days=earthquake_days,
            india_only=(country is not None and country.lower() == "india"),
        )
    else:
        logger.info("[DataAgent] Step 3/4 → USGS data (SKIPPED)")

    # ── 4. Resources ──────────────────────────────────────────────────────────
    if not skip_resources:
        logger.info("[DataAgent] Step 4/4 → Resource availability data")
        state = collect_resource_data(
            state,
            latitude=latitude,
            longitude=longitude,
            radius_km=resource_radius_km,
        )
    else:
        logger.info("[DataAgent] Step 4/4 → Resource data (SKIPPED)")

    # ── Validation ────────────────────────────────────────────────────────────
    is_valid, validation_errors = validate_state(state)
    if not is_valid:
        for err in validation_errors:
            state = update_state_metadata(state, current_node=AGENT_NAME, warning=f"Validation: {err}")

    # ── Final summary log ─────────────────────────────────────────────────────
    total_elapsed = round(time.monotonic() - t_total_start, 2)
    summary = get_state_summary(state)
    error_count = len((state.get("metadata") or {}).get("errors") or [])

    logger.info(
        f"\n{'='*60}\n"
        f"[DataAgent] ✅ Data collection complete in {total_elapsed}s\n"
        f"  Weather data   : {'✅' if state.get('weather_data') else '❌ FAILED'}\n"
        f"  Disaster events: {summary['disaster_events_count']} fetched\n"
        f"  Earthquakes    : {summary['earthquake_events_count']} fetched\n"
        f"  Resources      : {(state.get('resources') or {}).get('available_count', '❌ FAILED')} available\n"
        f"  Errors         : {error_count}\n"
        f"  Sources used   : {summary['data_sources_used']}\n"
        f"{'='*60}"
    )

    return state


# ===========================================================================
# STANDALONE RUN (for testing without LangGraph)
# ===========================================================================

if __name__ == "__main__":
    """
    Run data collection agent standalone for testing.

    Usage:
        cd disaster-ai
        python -m agents.data_collection_agent
    """
    import json

    logger.info("[DataAgent] Running standalone test...")

    # Initialize fresh state
    state = create_initial_state(environment="development")

    # Collect all data for Mumbai
    state = collect_all_data(
        state,
        latitude=19.0760,
        longitude=72.8777,
        location_label="Mumbai — Test Run",
        country="India",
    )

    # Print summary
    summary = get_state_summary(state)
    print("\n" + "="*60)
    print("FINAL STATE SUMMARY:")
    print("="*60)
    print(json.dumps(summary, indent=2, default=str))

    # Print weather risk
    weather = state.get("weather_data")
    if weather:
        print(f"\nWeather Risk: {weather.get('risk_summary')}")

    # Print first disaster event
    events = state.get("disaster_events") or []
    if events:
        print(f"\nFirst GDACS Event: {events[0].get('title')} [{events[0].get('alert_level')}]")

    # Print first earthquake
    eqs = state.get("earthquake_events") or []
    if eqs:
        print(f"\nFirst Earthquake: M{eqs[0].get('magnitude')} — {eqs[0].get('place')}")

    # Print resource summary
    resources = state.get("resources")
    if resources:
        print(f"\nResources: {resources.get('available_count')}/{resources.get('total_resources')} available")
