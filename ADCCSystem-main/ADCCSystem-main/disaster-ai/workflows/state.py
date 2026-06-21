"""
ADCC — LangGraph Shared State Architecture
==========================================
Defines the DisasterState TypedDict — the single shared state object
passed between all nodes in the LangGraph workflow.

Design Principles:
    - TypedDict based (LangGraph native format)
    - All fields Optional with safe defaults
    - Immutable field names (agents append/update, never overwrite raw data)
    - Compatible with all tool outputs (weather, gdacs, usgs, resource)
    - Ready for future: severity_agent, verification_agent, allocation_agent,
      replanning_agent, LangGraph graph.py

Architecture:
    data_collection_node  → populates weather_data, disaster_events, earthquake_events
    severity_node         → populates severity_score, severity_level, confidence_score
    verification_node     → populates verified_reports
    allocation_node       → populates allocation_plan, resources
    shelter_node          → populates shelter_plan
    replanning_node       → updates allocation_plan, recommendations
    command_center_node   → populates explanation, final recommendations

File Location:
    workflows/state.py

Used by:
    workflows/graph.py    → StateGraph(DisasterState)
    workflows/nodes.py    → each node receives and returns DisasterState
    agents/               → all agents read/write this state
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict


# ===========================================================================
# SUB-STATE TYPE ALIASES
# (These mirror the Pydantic model structures from tools/ but as plain dicts
#  so LangGraph can serialize/deserialize them without Pydantic overhead)
# ===========================================================================


# ── Weather ─────────────────────────────────────────────────────────────────
# Mirrors: tools/weather_tool.py → DisasterWeatherReport (dict form)
class WeatherStateData(TypedDict, total=False):
    """Subset of DisasterWeatherReport relevant for state."""
    latitude: float
    longitude: float
    location_label: Optional[str]

    # Current conditions
    temperature_c: float
    rainfall_mm: float
    humidity_percent: float
    wind_speed_kmh: float
    wind_direction_deg: float
    weather_description: str
    is_day: bool

    # Risk flags — set by weather_tool.py
    flood_risk: bool      # rainfall_mm >= 50
    cyclone_risk: bool    # wind_speed_kmh >= 120

    # Forecast summary
    forecast_days: int
    max_rainfall_mm: float
    max_wind_kmh: float
    flood_risk_hours: int  # hours with rainfall >= 50mm in forecast

    # Tool metadata
    risk_summary: str
    source: str           # "Open-Meteo"
    source_url: str
    fetched_at: str       # ISO datetime string


# ── GDACS Disaster Event ─────────────────────────────────────────────────────
# Mirrors: tools/gdacs_tool.py → GDACSEvent (dict form)
class GDACSEventState(TypedDict, total=False):
    event_id: str
    event_type: str          # EQ, TC, FL, VO, WF
    event_type_label: str    # "Flood", "Tropical Cyclone", etc.
    alert_level: str         # Red, Orange, Green
    severity_mapped: str     # Critical, High, Low (ADCC mapped)
    alert_score: Optional[float]
    country: str
    latitude: Optional[float]
    longitude: Optional[float]
    title: str
    description: Optional[str]
    url: str
    affected_population: Optional[int]
    event_date: Optional[str]
    source: str              # "GDACS"
    source_url: str


# ── USGS Earthquake Event ────────────────────────────────────────────────────
# Mirrors: tools/disaster_tool.py → EarthquakeEvent (dict form)
class EarthquakeEventState(TypedDict, total=False):
    usgs_id: str
    usgs_url: str
    magnitude: float
    magnitude_type: str
    depth_km: float
    depth_label: str         # "Shallow", "Intermediate", "Deep"
    latitude: float
    longitude: float
    place: str
    country: Optional[str]
    severity_mapped: str     # ADCC severity: Low/Medium/High/Critical
    event_time: str          # ISO datetime string
    event_time_ist: Optional[str]
    felt_reports: Optional[int]
    tsunami_risk: bool
    alert_level: Optional[str]
    significance: Optional[int]
    source: str              # "USGS"
    source_url: str


# ── Verified Report ──────────────────────────────────────────────────────────
# Created by verification_agent.py after cross-source validation
class VerifiedReportState(TypedDict, total=False):
    disaster_id: str         # UUID of Disaster in DB
    disaster_title: str
    sources_checked: list[str]    # ["GDACS", "USGS", "NewsAPI"]
    verification_result: str      # "Confirmed", "Denied", "Inconclusive"
    consensus_confidence: float   # 0.0–1.0 aggregate confidence
    verification_notes: str
    verified_at: str         # ISO datetime


# ── Resource State ───────────────────────────────────────────────────────────
# Mirrors: tools/resource_tool.py → ResourceRecord/ResourceSummary (dict form)
class ResourceStateData(TypedDict, total=False):
    # Summary counts
    total_resources: int
    available_count: int
    busy_count: int
    maintenance_count: int

    # Type breakdown
    boats_available: int
    ambulances_available: int
    medical_teams_available: int
    rescue_teams_available: int
    ndrf_units_available: int

    # Available resource list (for allocation agent)
    available_resources: list[dict[str, Any]]   # list of ResourceRecord dicts
    nearest_resources: list[dict[str, Any]]      # sorted by distance_km

    fetched_at: str


# ── Allocation Plan ──────────────────────────────────────────────────────────
# Created by allocation_agent.py
class AllocationPlanState(TypedDict, total=False):
    disaster_id: str
    disaster_title: str
    allocations: list[dict[str, Any]]   # [{"resource_id": ..., "resource_name": ..., "quantity": ..., "reason": ...}]
    total_resources_deployed: int
    estimated_coverage_pct: float        # 0–100
    gaps: list[str]                      # resource gaps identified
    plan_created_at: str
    plan_version: int                    # increments on replanning


# ── Shelter Plan ─────────────────────────────────────────────────────────────
# Created by shelter_agent.py
class ShelterPlanState(TypedDict, total=False):
    assigned_shelters: list[dict[str, Any]]  # [{"shelter_id": ..., "name": ..., "city": ..., "capacity": ..., "assigned_people": ...}]
    total_shelter_capacity: int
    total_people_assigned: int
    overflow_risk: bool                      # True if capacity < affected_population
    recommended_additional_shelters: list[str]
    plan_created_at: str


# ── Evacuation Plan ──────────────────────────────────────────────────────────
# Created by replanning_agent.py or allocation_agent.py
class EvacuationPlanState(TypedDict, total=False):
    evacuation_zones: list[str]              # zone names/areas to evacuate
    total_people_to_evacuate: int
    routes: list[dict[str, Any]]             # [{"from": ..., "to": ..., "distance_km": ..., "route_type": ...}]
    assembly_points: list[str]
    priority_zones: list[str]                # evacuate first
    estimated_time_hours: float
    plan_created_at: str


# ── Simulation Results ───────────────────────────────────────────────────────
# Produced by services/simulation_engine.py
class SimulationResultState(TypedDict, total=False):
    scenario_name: str
    rainfall_change: Optional[float]
    wind_speed_change: Optional[float]
    population_change: Optional[int]
    predicted_severity: str
    result_summary: str               # JSON or text from simulation engine
    simulated_at: str


# ── Active Alert ─────────────────────────────────────────────────────────────
class AlertState(TypedDict, total=False):
    alert_id: str
    title: str
    severity: str
    message: str
    source: Optional[str]
    source_type: Optional[str]
    confidence_score: Optional[float]
    created_at: str


# ── Session Metadata ─────────────────────────────────────────────────────────
class MetadataState(TypedDict, total=False):
    session_id: str
    created_at: str
    last_updated_at: str
    current_node: str                 # which LangGraph node is running
    nodes_visited: list[str]          # execution trace
    errors: list[str]                 # error messages from any node
    warnings: list[str]
    data_sources_used: list[str]      # ["Open-Meteo", "GDACS", "USGS"]
    workflow_version: str
    environment: str                  # "development", "production"


# ===========================================================================
# MAIN STATE: DisasterState
# The single TypedDict passed between ALL LangGraph nodes.
# ===========================================================================


class DisasterState(TypedDict, total=False):
    """
    Shared state for the ADCC LangGraph workflow.

    LangGraph Usage:
        from langgraph.graph import StateGraph
        graph = StateGraph(DisasterState)

    Node Signature:
        def my_node(state: DisasterState) -> DisasterState:
            # read from state
            weather = state.get("weather_data")
            # update state
            return {**state, "severity_score": 0.87}

    Field Ownership (which agent/node writes each field):
    ┌─────────────────────────┬──────────────────────────────────┐
    │ Field                   │ Written by                       │
    ├─────────────────────────┼──────────────────────────────────┤
    │ session_id              │ init_state()                     │
    │ timestamp               │ init_state()                     │
    │ weather_data            │ data_collection_agent            │
    │ disaster_events         │ data_collection_agent (GDACS)    │
    │ earthquake_events       │ data_collection_agent (USGS)     │
    │ verified_reports        │ verification_agent               │
    │ resources               │ data_collection_agent            │
    │ active_alerts           │ data_collection_agent            │
    │ severity_score          │ severity_agent                   │
    │ severity_level          │ severity_agent                   │
    │ confidence_score        │ severity_agent / confidence_eng  │
    │ allocation_plan         │ allocation_agent                 │
    │ shelter_plan            │ shelter_agent                    │
    │ evacuation_plan         │ replanning_agent                 │
    │ route_plan              │ route_planning_agent             │
    │ recommendations         │ command_center / replanning      │
    │ explanation             │ command_center                   │
    │ simulation_results      │ simulation_engine                │
    │ metadata                │ all nodes (append-only)          │
    │ supervisor_decision     │ supervisor_agent                 │
    │ supervisor_iterations   │ supervisor_agent                 │
    │ next_agents             │ supervisor_agent                 │
    │ agents_completed        │ supervisor_agent                 │
    │ notification_sent       │ notification_agent               │
    │ new_events_detected     │ supervisor_agent / replanning    │
    └─────────────────────────┴──────────────────────────────────┘
    """

    # ── Session Identity ─────────────────────────────────────────────────────
    session_id: str
    """UUID string — unique ID for this workflow run."""

    timestamp: str
    """ISO 8601 UTC timestamp of when this session was initialized."""

    latitude: Optional[float]
    longitude: Optional[float]
    location_label: Optional[str]
    country: Optional[str]

    # ── Raw Data (from tools/) ───────────────────────────────────────────────
    weather_data: Optional[WeatherStateData]
    """
    Current + forecast weather for the disaster zone.
    Set by: data_collection_agent.py via weather_tool.get_disaster_weather()
    """

    disaster_events: list[GDACSEventState]
    """
    List of active GDACS disaster alerts.
    Set by: data_collection_agent.py via gdacs_tool.get_active_disasters()
    """

    earthquake_events: list[EarthquakeEventState]
    """
    List of recent USGS earthquake events.
    Set by: data_collection_agent.py via disaster_tool.get_recent_earthquakes()
    """

    # ── Verification ─────────────────────────────────────────────────────────
    verified_reports: list[VerifiedReportState]
    """
    Cross-verified disaster reports from verification_agent.py.
    Set by: verification_agent.py after checking GDACS + USGS + NewsAPI
    """

    # ── Resources ────────────────────────────────────────────────────────────
    resources: Optional[ResourceStateData]
    """
    Current resource availability summary + nearest resources list.
    Set by: data_collection_agent.py via resource_tool.get_resource_summary()
    """

    # ── Alerts ───────────────────────────────────────────────────────────────
    active_alerts: list[AlertState]
    """
    Active system/external alerts from GDACS, USGS, NDMA.
    Set by: data_collection_agent.py
    """

    # ── Severity Assessment ───────────────────────────────────────────────────
    severity_score: float
    """
    Computed severity score 0.0–1.0.
    Set by: severity_agent.py
    0.0–0.25 → Low | 0.25–0.50 → Medium | 0.50–0.75 → High | 0.75–1.0 → Critical
    """

    severity_level: str
    """
    Human-readable severity: "Low", "Medium", "High", "Critical"
    Set by: severity_agent.py
    """

    confidence_score: float
    """
    Data confidence score 0.0–1.0 (how reliable is the input data).
    Set by: severity_agent.py using confidence_engine.py
    """

    # ── Plans (from agents/) ─────────────────────────────────────────────────
    allocation_plan: Optional[AllocationPlanState]
    """
    Resource allocation decisions from allocation_agent.py.
    Updated by: replanning_agent.py on situation change.
    """

    shelter_plan: Optional[ShelterPlanState]
    """
    Shelter assignment plan from shelter_agent.py.
    """

    evacuation_plan: Optional[EvacuationPlanState]
    """
    Evacuation routing plan.
    Set by: replanning_agent.py using route_tool.py
    """

    # ── Output (from command_center/) ────────────────────────────────────────
    recommendations: list[str]
    """
    Human-readable action recommendations from command_center or replanning agent.
    E.g.: ["Deploy 3 NDRF units to Mumbai", "Activate 2 overflow shelters"]
    """

    explanation: str
    """
    Full natural-language explanation of the situation and response plan.
    Generated by: agents/command_center.py using Gemini.
    """

    replanning_actions: list[dict]
    """
    List of dynamic actions triggered during replanning.
    """

    is_demo: bool
    """
    True if executing in Demo Mode.
    """

    # ── Route Plan ───────────────────────────────────────────────────────────
    route_plan: Optional[dict]
    """
    Evacuation route plan from route_planning_agent.py.
    Contains primary route + alternatives per zone.
    """

    # ── Supervisor Control Fields ─────────────────────────────────────────────
    supervisor_decision: Optional[dict]
    """
    The last SupervisorDecision emitted by supervisor_agent.py.
    Shape: {next_agents, reasoning, needs_more_data, confidence_threshold_met, is_done}
    """

    supervisor_iterations: int
    """
    Safety loop counter — how many times the supervisor has been invoked.
    Max 10 iterations; forced END if exceeded.
    """

    next_agents: list[str]
    """
    Agents queued to run next, as chosen by the supervisor.
    Supports multiple entries for parallel fan-out (e.g. ['allocation', 'shelter']).
    """

    agents_completed: list[str]
    """
    Tracks which agents have successfully completed in this session.
    Appended to by each agent's node wrapper.
    """

    notification_sent: bool
    """
    True once the notification_agent has dispatched alerts.
    Gates against duplicate notifications.
    """

    new_events_detected: bool
    """
    True when new incoming disaster events are detected mid-cycle.
    Triggers dynamic replanning by the supervisor.
    """

    # ── Simulation ────────────────────────────────────────────────────────────
    simulation_results: list[SimulationResultState]
    """
    Digital Twin simulation scenario results.
    Set by: services/simulation_engine.py
    """

    # ── Metadata ─────────────────────────────────────────────────────────────
    metadata: MetadataState
    """
    Session tracking, node trace, errors, data sources used.
    Updated by every node as execution progresses.
    """


# ===========================================================================
# STATE FACTORY & HELPERS
# ===========================================================================


def create_initial_state(
    session_id: Optional[str] = None,
    environment: str = "development",
) -> DisasterState:
    """
    Creates a fresh DisasterState with safe defaults.

    Args:
        session_id:  Optional custom session ID. Auto-generated UUID if None.
        environment: "development" or "production"

    Returns:
        DisasterState: Initialized state ready for the first workflow node.

    Usage:
        state = create_initial_state()
        # Pass to LangGraph: graph.invoke(state)

    Example:
        >>> state = create_initial_state(environment="production")
        >>> print(state["session_id"])
        'a1b2c3d4-...'
    """
    from loguru import logger

    sid = session_id or str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    state: DisasterState = {
        # Session identity
        "session_id":  sid,
        "timestamp":   now_iso,
        "latitude":    None,
        "longitude":   None,
        "location_label": None,
        "country":     None,

        # Raw data (empty — populated by data_collection_agent)
        "weather_data":       None,
        "disaster_events":    [],
        "earthquake_events":  [],
        "verified_reports":   [],
        "resources":          None,
        "active_alerts":      [],

        # Severity (populated by severity_agent)
        "severity_score":  0.0,
        "severity_level":  "Low",
        "confidence_score": 0.0,

        # Plans (populated by respective agents)
        "allocation_plan":  None,
        "shelter_plan":     None,
        "evacuation_plan":  None,
        "route_plan":       None,

        # Output (populated by command_center)
        "recommendations": [],
        "explanation":     "",
        "replanning_actions": [],
        "is_demo":          False,

        # Supervisor control (populated by supervisor_agent)
        "supervisor_decision":    None,
        "supervisor_iterations":  0,
        "next_agents":            [],
        "agents_completed":       [],
        "notification_sent":      False,
        "new_events_detected":    False,

        # Simulation
        "simulation_results": [],

        # Metadata
        "metadata": {
            "session_id":         sid,
            "created_at":         now_iso,
            "last_updated_at":    now_iso,
            "current_node":       "init",
            "nodes_visited":      ["init"],
            "errors":             [],
            "warnings":           [],
            "data_sources_used":  [],
            "workflow_version":   "1.0.0",
            "environment":        environment,
        },
    }

    logger.info(f"[State] Initialized DisasterState | session_id={sid} | env={environment}")
    return state


def update_state_metadata(
    state: DisasterState,
    current_node: str,
    data_source: Optional[str] = None,
    error: Optional[str] = None,
    warning: Optional[str] = None,
) -> DisasterState:
    """
    Updates the metadata section of DisasterState.
    Called at the start/end of every workflow node.

    Args:
        state:        Current DisasterState
        current_node: Name of the node currently executing
        data_source:  If a new API was called, add its name
        error:        Error message to log (if any)
        warning:      Warning message to log (if any)

    Returns:
        Updated DisasterState with modified metadata

    Usage (in a workflow node):
        state = update_state_metadata(state, "severity_node", data_source="GDACS")

    Example:
        >>> state = update_state_metadata(state, "verification_node", error="NewsAPI timeout")
    """
    from loguru import logger

    now_iso = datetime.now(timezone.utc).isoformat()

    # Deep copy metadata to avoid mutation
    meta = dict(state.get("metadata") or {})
    nodes_visited: list[str] = list(meta.get("nodes_visited") or [])
    errors: list[str]        = list(meta.get("errors") or [])
    warnings: list[str]      = list(meta.get("warnings") or [])
    sources: list[str]       = list(meta.get("data_sources_used") or [])

    # Update fields
    meta["current_node"]     = current_node
    meta["last_updated_at"]  = now_iso

    if current_node not in nodes_visited:
        nodes_visited.append(current_node)
    meta["nodes_visited"] = nodes_visited

    if data_source and data_source not in sources:
        sources.append(data_source)
    meta["data_sources_used"] = sources

    if error:
        error_entry = f"[{current_node}] {error}"
        errors.append(error_entry)
        logger.error(f"[State] {error_entry}")
    meta["errors"] = errors

    if warning:
        warning_entry = f"[{current_node}] {warning}"
        warnings.append(warning_entry)
        logger.warning(f"[State] {warning_entry}")
    meta["warnings"] = warnings

    return {**state, "metadata": meta}  # type: ignore[return-value]


def validate_state(state: DisasterState) -> tuple[bool, list[str]]:
    """
    Validates that DisasterState has minimum required fields for agent processing.

    Args:
        state: DisasterState to validate

    Returns:
        tuple[bool, list[str]]:
            - bool: True if valid, False if validation failed
            - list[str]: List of validation error messages

    Usage:
        is_valid, errors = validate_state(state)
        if not is_valid:
            logger.error(f"State invalid: {errors}")

    Example:
        >>> is_valid, errors = validate_state(state)
        >>> print(is_valid, errors)
        True []
    """
    from loguru import logger

    issues: list[str] = []

    # Required base fields
    if not state.get("session_id"):
        issues.append("Missing session_id")

    if not state.get("timestamp"):
        issues.append("Missing timestamp")

    # Severity score range check
    severity_score = state.get("severity_score", 0.0)
    if not isinstance(severity_score, (int, float)):
        issues.append(f"severity_score must be numeric, got {type(severity_score)}")
    elif not 0.0 <= severity_score <= 1.0:
        issues.append(f"severity_score {severity_score} out of range [0.0, 1.0]")

    # Confidence score range check
    confidence_score = state.get("confidence_score", 0.0)
    if not isinstance(confidence_score, (int, float)):
        issues.append(f"confidence_score must be numeric, got {type(confidence_score)}")
    elif not 0.0 <= confidence_score <= 1.0:
        issues.append(f"confidence_score {confidence_score} out of range [0.0, 1.0]")

    # Severity level enum check
    valid_levels = {"Low", "Medium", "High", "Critical"}
    severity_level = state.get("severity_level", "Low")
    if severity_level not in valid_levels:
        issues.append(f"Invalid severity_level '{severity_level}'. Must be one of {valid_levels}")

    # Data presence warnings (not errors — data may not yet be collected)
    if not state.get("weather_data"):
        logger.debug("[State] weather_data is empty — data_collection_agent not yet run")

    if not state.get("disaster_events"):
        logger.debug("[State] disaster_events is empty — no GDACS events fetched yet")

    is_valid = len(issues) == 0

    if is_valid:
        logger.debug(f"[State] Validation passed for session {state.get('session_id')}")
    else:
        logger.warning(f"[State] Validation failed: {issues}")

    return is_valid, issues


def set_severity(
    state: DisasterState,
    score: float,
    level: str,
    confidence: float,
) -> DisasterState:
    """
    Updates severity fields in state — convenience wrapper for severity_agent.py.

    Args:
        state:      Current DisasterState
        score:      Severity score 0.0–1.0
        level:      Severity level: "Low", "Medium", "High", "Critical"
        confidence: Confidence score 0.0–1.0

    Returns:
        Updated DisasterState

    Example:
        >>> state = set_severity(state, score=0.82, level="Critical", confidence=0.91)
    """
    from loguru import logger

    # Clamp values to valid range
    score      = max(0.0, min(1.0, score))
    confidence = max(0.0, min(1.0, confidence))

    valid_levels = {"Low", "Medium", "High", "Critical"}
    if level not in valid_levels:
        logger.warning(f"[State] Invalid severity_level '{level}', defaulting to 'Medium'")
        level = "Medium"

    logger.info(f"[State] Severity set: {level} (score={score:.2f}, confidence={confidence:.2f})")

    return {
        **state,
        "severity_score":   score,
        "severity_level":   level,
        "confidence_score": confidence,
    }  # type: ignore[return-value]


def severity_score_from_data(
    affected_population: Optional[int] = None,
    rainfall_mm: float = 0.0,
    wind_speed_kmh: float = 0.0,
    magnitude: Optional[float] = None,
    gdacs_alert_level: str = "Green",
    num_verified_sources: int = 0,
) -> tuple[float, str, float]:
    """
    Heuristic severity score calculator.
    Used by severity_agent.py before full Gemini analysis is available.

    Args:
        affected_population: Estimated affected people
        rainfall_mm:         Current hourly rainfall (mm)
        wind_speed_kmh:      Wind speed (km/h)
        magnitude:           Earthquake magnitude (if applicable)
        gdacs_alert_level:   GDACS alert: "Red", "Orange", "Green"
        num_verified_sources: Number of sources that confirmed the event

    Returns:
        tuple[float, str, float]:
            (severity_score 0.0–1.0, severity_level str, confidence_score 0.0–1.0)

    Example:
        >>> score, level, conf = severity_score_from_data(
        ...     affected_population=500000,
        ...     rainfall_mm=80.0,
        ...     gdacs_alert_level="Red",
        ...     num_verified_sources=3
        ... )
        >>> print(score, level, conf)
        0.91 Critical 0.85
    """
    score = 0.0
    weights = {
        "population":  0.30,
        "weather":     0.25,
        "gdacs":       0.25,
        "magnitude":   0.20,
    }

    # Population factor (max score at 1M affected)
    pop_score = 0.0
    if affected_population:
        pop_score = min(affected_population / 1_000_000, 1.0)
    score += pop_score * weights["population"]

    # Weather factor
    weather_score = 0.0
    if rainfall_mm >= 100:
        weather_score = 1.0
    elif rainfall_mm >= 50:
        weather_score = 0.75
    elif rainfall_mm >= 20:
        weather_score = 0.50
    if wind_speed_kmh >= 180:
        weather_score = max(weather_score, 1.0)
    elif wind_speed_kmh >= 120:
        weather_score = max(weather_score, 0.80)
    elif wind_speed_kmh >= 80:
        weather_score = max(weather_score, 0.50)
    score += weather_score * weights["weather"]

    # GDACS alert factor
    gdacs_score = {"Red": 1.0, "Orange": 0.65, "Green": 0.20}.get(gdacs_alert_level, 0.2)
    score += gdacs_score * weights["gdacs"]

    # Earthquake magnitude factor
    mag_score = 0.0
    if magnitude:
        if magnitude >= 7.0:
            mag_score = 1.0
        elif magnitude >= 6.0:
            mag_score = 0.75
        elif magnitude >= 5.0:
            mag_score = 0.50
        elif magnitude >= 4.0:
            mag_score = 0.25
    score += mag_score * weights["magnitude"]

    # Clamp final score
    score = round(min(1.0, max(0.0, score)), 4)

    # Map score to level
    if score >= 0.75:
        level = "Critical"
    elif score >= 0.50:
        level = "High"
    elif score >= 0.25:
        level = "Medium"
    else:
        level = "Low"

    # Confidence: based on number of verified sources
    confidence = min(0.3 + (num_verified_sources * 0.2), 1.0)
    confidence = round(confidence, 4)

    return score, level, confidence


def get_state_summary(state: DisasterState) -> dict[str, Any]:
    """
    Returns a concise summary dict of the current state for logging/debugging.
    Does NOT return full data — only key metrics.

    Args:
        state: Current DisasterState

    Returns:
        dict: Summary with key metrics

    Example:
        >>> summary = get_state_summary(state)
        >>> print(summary)
        {'session_id': '...', 'severity': 'Critical', 'events': 5, ...}
    """
    return {
        "session_id":            state.get("session_id"),
        "timestamp":             state.get("timestamp"),
        "severity_level":        state.get("severity_level"),
        "severity_score":        state.get("severity_score"),
        "confidence_score":      state.get("confidence_score"),
        "disaster_events_count": len(state.get("disaster_events") or []),
        "earthquake_events_count": len(state.get("earthquake_events") or []),
        "verified_reports_count": len(state.get("verified_reports") or []),
        "active_alerts_count":   len(state.get("active_alerts") or []),
        "recommendations_count": len(state.get("recommendations") or []),
        "has_weather_data":      state.get("weather_data") is not None,
        "has_allocation_plan":   state.get("allocation_plan") is not None,
        "has_shelter_plan":      state.get("shelter_plan") is not None,
        "nodes_visited":         (state.get("metadata") or {}).get("nodes_visited", []),
        "errors":                (state.get("metadata") or {}).get("errors", []),
        "data_sources_used":     (state.get("metadata") or {}).get("data_sources_used", []),
    }


# ===========================================================================
# TYPE ALIASES (for cleaner agent code)
# ===========================================================================

# Agents can import these for type hints
StateUpdate = dict[str, Any]
"""
Return type for LangGraph nodes — a partial DisasterState dict.

Usage in nodes:
    def my_node(state: DisasterState) -> StateUpdate:
        return {"severity_score": 0.85, "severity_level": "Critical"}
"""
