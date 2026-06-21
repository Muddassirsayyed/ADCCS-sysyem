"""
ADCC — Route Planning Agent
============================
Standalone agent that computes evacuation routes for affected populations
using OpenRouteService (with geometric fallback if API unavailable).

Previously this logic was embedded inside replanning_agent.py. Extracting it
into a first-class agent allows the Supervisor to invoke it independently after
allocation and shelter plans are confirmed.

Responsibilities:
    ✅ Compute primary evacuation route from disaster zone to nearest shelter
    ✅ Generate alternative routes for resilience (if primary is blocked)
    ✅ Plan routes for each active disaster event separately
    ✅ Estimate travel time and ETA for responders
    ✅ Store consolidated route_plan in DisasterState

NOT responsible for:
    ❌ Shelter assignment  → shelter_agent.py
    ❌ Resource allocation → allocation_agent.py
    ❌ Notifications       → notification_agent.py

Position in Graph (supervisor-driven):
    supervisor → route_planning_agent → supervisor
"""

import time
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from workflows.state import (
    DisasterState,
    StateUpdate,
    EvacuationPlanState,
    update_state_metadata,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "route_planning_agent"

# Default safe zone / regional emergency hub (used when no shelter coords available)
DEFAULT_SAFE_ZONE_COORDS = [19.0760, 72.8777]   # Mumbai
DEFAULT_SAFE_ZONE_NAME   = "Regional Emergency Hub"

# Routing profile per disaster type
DISASTER_PROFILE_MAP = {
    "Flood":            "driving-hgv",    # Heavy vehicles for rescue boats
    "Earthquake":       "driving-car",    # Standard vehicles
    "Cyclone":          "driving-hgv",    # HGV for evacuation
    "Tropical Cyclone": "driving-hgv",
    "Tsunami":          "foot-walking",   # Coastal — may need walking routes
    "Wildfire":         "driving-car",
}
DEFAULT_PROFILE = "driving-car"


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================

def _get_disaster_coords(state: DisasterState) -> tuple[list[float], str]:
    """
    Extracts the primary disaster location coordinates from state.

    Returns:
        tuple[list[float], str]: ([latitude, longitude], disaster_type)
    """
    # Try GDACS events first
    events = state.get("disaster_events") or []
    for event in events:
        lat = event.get("latitude")
        lon = event.get("longitude")
        if lat is not None and lon is not None:
            return [lat, lon], event.get("event_type_label", "Unknown")

    # Try earthquake events
    eq_events = state.get("earthquake_events") or []
    for eq in eq_events:
        lat = eq.get("latitude")
        lon = eq.get("longitude")
        if lat is not None and lon is not None:
            return [lat, lon], "Earthquake"

    # Fall back to weather data location
    weather = state.get("weather_data")
    if weather:
        lat = weather.get("latitude")
        lon = weather.get("longitude")
        if lat is not None and lon is not None:
            return [lat, lon], "Weather"

    logger.warning("[RoutePlanningAgent] No disaster coordinates found — using default location.")
    return DEFAULT_SAFE_ZONE_COORDS, "Unknown"


def _get_shelter_coords(state: DisasterState) -> tuple[list[float], str]:
    """
    Gets the primary shelter coordinates for routing destination.

    Returns:
        tuple[list[float], str]: ([lat, lon], shelter_name)
    """
    shelter_plan = state.get("shelter_plan") or {}
    shelters = shelter_plan.get("assigned_shelters") or []

    for shelter in shelters:
        lat = shelter.get("latitude") or shelter.get("lat")
        lon = shelter.get("longitude") or shelter.get("lon")
        if lat is not None and lon is not None:
            return [lat, lon], shelter.get("name", "Primary Shelter")

    logger.warning("[RoutePlanningAgent] No shelter coordinates in plan — using default safe zone.")
    return DEFAULT_SAFE_ZONE_COORDS, DEFAULT_SAFE_ZONE_NAME


def _plan_single_route(
    start_coords: list[float],
    end_coords: list[float],
    disaster_type: str,
) -> dict[str, Any]:
    """
    Calls route_tool.get_evacuation_routes() or get_route() and returns
    a normalized route dict for inclusion in route_plan.
    """
    try:
        from tools.route_tool import get_route

        profile = DISASTER_PROFILE_MAP.get(disaster_type, DEFAULT_PROFILE)

        # Call get_route
        route = get_route(
            start_coords=start_coords,
            end_coords=end_coords,
            profile=profile,
        )
        return {
            "distance_km":      route.distance_km,
            "duration_minutes": route.duration_minutes,
            "eta":              route.eta,
            "provider":         route.provider,
            "route_coordinates": route.route_coordinates,
            "alternatives":     [
                {
                    "distance_km":      alt.distance_km,
                    "duration_minutes": alt.duration_minutes,
                    "eta":              alt.eta,
                }
                for alt in route.alternative_routes
            ],
            "profile": profile,
        }

    except Exception as e:
        logger.error(f"[RoutePlanningAgent] Route calculation failed: {e}")
        return {
            "error":            str(e),
            "distance_km":      0.0,
            "duration_minutes": 0.0,
            "eta":              datetime.now(timezone.utc).isoformat(),
            "provider":         "Error",
            "route_coordinates": [],
            "alternatives":     [],
            "profile":          DEFAULT_PROFILE,
        }


# ===========================================================================
# MAIN AGENT ENTRY POINT
# ===========================================================================

def run_route_planning(state: DisasterState) -> DisasterState:
    """
    Main Route Planning Agent entry point. Called by LangGraph route_planning_node.

    Steps:
    1. Extract disaster zone coordinates from state
    2. Extract shelter / safe zone coordinates from shelter_plan
    3. Call route_tool to compute primary + alternative evacuation routes
    4. Build evacuation zones list from active events
    5. Store consolidated route_plan in state
    6. Mark agent completed and return updated state

    Args:
        state: Current DisasterState

    Returns:
        Updated DisasterState with route_plan populated
    """
    from agents.supervisor_agent import mark_agent_completed

    t_start = time.time()
    logger.info("[RoutePlanningAgent] ─── Starting evacuation route planning ───")

    # ── Guard: already planned ────────────────────────────────────────────────
    if state.get("route_plan") is not None:
        logger.info("[RoutePlanningAgent] Route plan already exists. Skipping.")
        return mark_agent_completed(
            update_state_metadata(state, AGENT_NAME),
            AGENT_NAME,
        )

    state = update_state_metadata(state, AGENT_NAME)

    # ── Get coordinates ───────────────────────────────────────────────────────
    disaster_coords, disaster_type = _get_disaster_coords(state)
    shelter_coords, shelter_name   = _get_shelter_coords(state)

    logger.info(
        f"[RoutePlanningAgent] Disaster @ {disaster_coords} → "
        f"Shelter '{shelter_name}' @ {shelter_coords} "
        f"| Type: {disaster_type}"
    )

    # ── Compute routes ────────────────────────────────────────────────────────
    route_data = _plan_single_route(disaster_coords, shelter_coords, disaster_type)

    # ── Build evacuation zones list ───────────────────────────────────────────
    evacuation_zones: list[str] = []
    events = state.get("disaster_events") or []
    for evt in events:
        zone = evt.get("country") or evt.get("title") or "Unknown Zone"
        if zone not in evacuation_zones:
            evacuation_zones.append(zone)
    if not evacuation_zones:
        weather = state.get("weather_data") or {}
        zone = weather.get("location_label") or "Primary Zone"
        evacuation_zones.append(zone)

    # ── Estimate people to evacuate ───────────────────────────────────────────
    total_people = 0
    for evt in events:
        pop = evt.get("affected_population") or 0
        total_people += int(pop)
    if total_people == 0 and state.get("shelter_plan"):
        total_people = (state.get("shelter_plan") or {}).get("total_people_assigned", 0)

    # ── Assemble route_plan ───────────────────────────────────────────────────
    now_iso = datetime.now(timezone.utc).isoformat()
    elapsed = round(time.time() - t_start, 2)

    route_plan: dict[str, Any] = {
        "primary_route": {
            "from":             "Disaster Zone",
            "to":               shelter_name,
            "disaster_type":    disaster_type,
            "start_coords":     disaster_coords,
            "end_coords":       shelter_coords,
            **route_data,
        },
        "evacuation_zones":         evacuation_zones,
        "total_people_to_evacuate": total_people,
        "assembly_points":          [shelter_name],
        "priority_zones":           evacuation_zones[:1],   # first zone is highest priority
        "estimated_time_hours":     round(route_data.get("duration_minutes", 0) / 60, 2),
        "plan_created_at":          now_iso,
        "planning_time_seconds":    elapsed,
    }

    # ── Also update EvacuationPlanState for backward compatibility ────────────
    evacuation_plan: EvacuationPlanState = {
        "evacuation_zones":         evacuation_zones,
        "total_people_to_evacuate": total_people,
        "routes": [
            {
                "from":         "Disaster Zone",
                "to":           shelter_name,
                "distance_km":  route_data.get("distance_km", 0),
                "route_type":   route_data.get("profile", DEFAULT_PROFILE),
            }
        ],
        "assembly_points":        [shelter_name],
        "priority_zones":         evacuation_zones[:1],
        "estimated_time_hours":   round(route_data.get("duration_minutes", 0) / 60, 2),
        "plan_created_at":        now_iso,
    }

    summary_rec = (
        f"[RoutePlanningAgent] Evacuation route planned: "
        f"{route_data.get('distance_km', 0):.1f} km, "
        f"~{route_data.get('duration_minutes', 0):.0f} min to {shelter_name}. "
        f"Zones: {', '.join(evacuation_zones)}. ({elapsed}s)"
    )
    existing_recs = list(state.get("recommendations") or [])
    existing_recs.append(summary_rec)

    logger.success(
        f"[RoutePlanningAgent] Route planned in {elapsed}s | "
        f"{route_data.get('distance_km', 0):.1f} km to {shelter_name} | "
        f"Provider: {route_data.get('provider', 'Unknown')}"
    )

    updated: DisasterState = {
        **state,
        "route_plan":      route_plan,
        "evacuation_plan": evacuation_plan,
        "recommendations": existing_recs,
    }

    return mark_agent_completed(
        update_state_metadata(updated, AGENT_NAME, data_source="OpenRouteService"),
        AGENT_NAME,
    )
