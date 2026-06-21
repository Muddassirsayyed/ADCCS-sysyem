"""
ADCC — Shelter Assignment Agent
================================
Automatically assigns affected disaster populations to available emergency 
shelters using a nearest-first greedy matching algorithm with capacity safety.

Position in Pipeline:
    [allocation_agent]       ← allocates logistics and teams
         ↓
    [shelter_agent]          ← THIS FILE
         ↓
    [replanning_agent]       (Future phase)
"""

import math
import time
from datetime import datetime, timezone
from typing import Any, Optional
from loguru import logger
from pydantic import BaseModel, Field

from database.models import Shelter
from database.postgres import SessionLocal
from workflows.state import (
    DisasterState,
    StateUpdate,
    update_state_metadata,
    validate_state,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "shelter_agent"


# ===========================================================================
# PYDANTIC VALIDATION MODELS
# ===========================================================================

class ShelterAssignmentRecord(BaseModel):
    """Assignment details for a single shelter."""
    shelter: str = Field(..., description="Name of the shelter")
    assigned: int = Field(..., description="Number of people assigned to this shelter")


class ShelterPlanOutput(BaseModel):
    """Normalized output for the shelter assignment plan."""
    affected_population: int = Field(..., description="Total affected population requiring shelter")
    assigned_population: int = Field(..., description="Total population successfully assigned")
    unassigned_population: int = Field(..., description="Total population that cannot be housed due to capacity deficits")
    shelter_assignments: list[ShelterAssignmentRecord] = Field(..., description="Details of assignments per shelter")


# ===========================================================================
# MATH HELPERS
# ===========================================================================

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes the great-circle distance between two GPS coordinates using the Haversine formula.
    """
    R = 6371.0  # Earth's radius in kilometers
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ===========================================================================
# DEDICATED AGENT FUNCTIONS
# ===========================================================================

def get_available_shelters() -> list[Shelter]:
    """
    Queries all emergency shelters from the PostgreSQL database.
    Only returns shelters with remaining positive capacity.
    """
    db = SessionLocal()
    try:
        # Fetch shelters where capacity > occupied
        shelters = db.query(Shelter).filter(Shelter.capacity > Shelter.occupied).all()
        logger.info(f"[ShelterAgent] Loaded {len(shelters)} shelters with vacant slots from database.")
        return shelters
    except Exception as e:
        logger.error(f"[ShelterAgent] Database query failed in get_available_shelters: {e}")
        return []
    finally:
        db.close()


def calculate_remaining_capacity(shelter: Any) -> int:
    """
    Calculates the remaining vacant capacity of a shelter.
    Handles both SQLAlchemy ORM objects and dictionaries safely.
    """
    if isinstance(shelter, dict):
        capacity = shelter.get("capacity", 0)
        occupied = shelter.get("occupied", 0)
    else:
        capacity = getattr(shelter, "capacity", 0)
        occupied = getattr(shelter, "occupied", 0)
    
    return max(0, capacity - occupied)


def find_nearest_shelters(
    disaster_lat: float,
    disaster_lon: float,
    shelters: list[Any],
) -> list[tuple[Any, float]]:
    """
    Calculates distance for all shelters relative to disaster coordinates.
    Sorts shelters by distance (nearest first).
    
    Returns:
        list[tuple[Any, float]]: List of tuples containing (shelter_object, distance_km)
    """
    shelter_distances = []
    
    for s in shelters:
        if isinstance(s, dict):
            s_lat = s.get("latitude")
            s_lon = s.get("longitude")
        else:
            s_lat = getattr(s, "latitude", None)
            s_lon = getattr(s, "longitude", None)

        if s_lat is not None and s_lon is not None:
            dist = _haversine_km(disaster_lat, disaster_lon, s_lat, s_lon)
            shelter_distances.append((s, dist))
        else:
            # If coordinates are missing, sort them as far away
            shelter_distances.append((s, 9999.0))

    # Sort by distance (nearest first)
    shelter_distances.sort(key=lambda x: x[1])
    return shelter_distances


def assign_population_to_shelters(
    population: int,
    sorted_shelters_with_dist: list[tuple[Any, float]],
) -> tuple[list[dict], int, int]:
    """
    Greedily assigns affected population to shelters.
    Obeys nearest first, avoids over-allocation, and caps assignments by available capacity.
    
    Returns:
        tuple[list[dict], int, int]: (assignments list, assigned_population, unassigned_population)
    """
    assignments: list[dict] = []
    remaining_to_assign = population
    
    for shelter, dist in sorted_shelters_with_dist:
        if remaining_to_assign <= 0:
            break
            
        vacant_capacity = calculate_remaining_capacity(shelter)
        if vacant_capacity <= 0:
            continue
            
        assigned_qty = min(remaining_to_assign, vacant_capacity)
        
        # Extract shelter details
        if isinstance(shelter, dict):
            s_id = str(shelter.get("id", ""))
            s_name = shelter.get("name", "Unknown Shelter")
            s_city = shelter.get("city", "")
            s_cap = shelter.get("capacity", 0)
        else:
            s_id = str(getattr(shelter, "id", ""))
            s_name = getattr(shelter, "name", "Unknown Shelter")
            s_city = getattr(shelter, "city", "")
            s_cap = getattr(shelter, "capacity", 0)

        assignments.append({
            "shelter_id": s_id,
            "name": s_name,
            "city": s_city,
            "capacity": s_cap,
            "assigned_people": assigned_qty,
            "distance_km": round(dist, 2)
        })
        
        remaining_to_assign -= assigned_qty

    assigned_total = population - remaining_to_assign
    return assignments, assigned_total, remaining_to_assign


def generate_shelter_plan(state: DisasterState) -> Optional[dict]:
    """
    Determines the total affected population from verified events, loads
    available shelters, sorts by distance, and runs assignment logic.
    """
    verified_reports = state.get("verified_reports") or []
    if not verified_reports:
        logger.warning("[ShelterAgent] No verified reports found in state. Skipping shelter assignment.")
        return None

    # Get primary confirmed report
    confirmed_reports = [
        r for r in verified_reports 
        if r.get("verification_result") in ("Verified", "High Confidence", "Medium Confidence", "Confirmed")
    ]
    if not confirmed_reports:
        logger.warning("[ShelterAgent] No confirmed verified reports. Skipping shelter assignment.")
        return None

    sorted_reports = sorted(
        confirmed_reports,
        key=lambda r: r.get("consensus_confidence", 0.0),
        reverse=True
    )
    primary_report = sorted_reports[0]
    primary_title = primary_report.get("disaster_title", "")

    # Retrieve coordinates and population from raw event list
    disaster_lat = 0.0
    disaster_lon = 0.0
    affected_population = 0

    gdacs_events = state.get("disaster_events") or []
    for event in gdacs_events:
        if event.get("title") == primary_title:
            disaster_lat = event.get("latitude") or 0.0
            disaster_lon = event.get("longitude") or 0.0
            affected_population = event.get("affected_population") or 0
            break

    eq_events = state.get("earthquake_events") or []
    for eq in eq_events:
        place = eq.get("place", "")
        mag = eq.get("magnitude", 0.0)
        title_with_mag = f"M{mag} Earthquake — {place}"
        if title_with_mag == primary_title or place in primary_title:
            disaster_lat = eq.get("latitude") or 0.0
            disaster_lon = eq.get("longitude") or 0.0
            
            # Estimate population impact for earthquakes if missing
            if mag >= 7.0:
                affected_population = 500000
            elif mag >= 6.0:
                affected_population = 100000
            elif mag >= 5.0:
                affected_population = 20000
            else:
                affected_population = 5000
            break

    if affected_population <= 0:
        logger.warning(f"[ShelterAgent] Affected population count is 0 or invalid for event '{primary_title}'. Skipping shelter assignment.")
        return None

    # Load shelters from DB
    shelters = get_available_shelters()
    if not shelters:
        logger.error("[ShelterAgent] No vacant shelters found in database!")
        return {
            "assigned_shelters": [],
            "total_shelter_capacity": 0,
            "total_people_assigned": 0,
            "overflow_risk": True,
            "recommended_additional_shelters": ["Open temporary shelters", "Request district support", "Activate emergency camps"],
            "plan_created_at": datetime.now(timezone.utc).isoformat(),
            "affected_population": affected_population,
            "assigned_population": 0,
            "unassigned_population": affected_population,
            "shelter_assignments": []
        }

    # Find nearest shelters
    sorted_shelters = find_nearest_shelters(disaster_lat, disaster_lon, shelters)

    # Perform assignment
    assignments, assigned_total, unassigned_total = assign_population_to_shelters(affected_population, sorted_shelters)
    
    total_capacity = sum(calculate_remaining_capacity(s) for s in shelters)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Build recommendations if capacity is insufficient
    recommended_additional = []
    if unassigned_total > 0:
        recommended_additional = [
            "Open temporary shelters",
            "Request district support",
            "Activate emergency camps"
        ]

    # Populate final plan dict matching both state schema and prompt requirements
    plan = {
        # workflows/state.py schema
        "assigned_shelters": assignments,
        "total_shelter_capacity": total_capacity,
        "total_people_assigned": assigned_total,
        "overflow_risk": unassigned_total > 0,
        "recommended_additional_shelters": recommended_additional,
        "plan_created_at": now_iso,
        
        # Pydantic / output example schema
        "affected_population": affected_population,
        "assigned_population": assigned_total,
        "unassigned_population": unassigned_total,
        "shelter_assignments": [
            {"shelter": a["name"], "assigned": a["assigned_people"]}
            for a in assignments
        ]
    }

    # Validate output schema via Pydantic
    try:
        validated = ShelterPlanOutput(**plan)
        logger.info(f"[ShelterAgent] Plan validated successfully. Coverage={validated.assigned_population}/{validated.affected_population}")
    except Exception as e:
        logger.error(f"[ShelterAgent] Plan Pydantic validation failed: {e}")

    return plan


def generate_recommendations(plan: dict, severity_level: str) -> list[str]:
    """
    Generates actionable recommendations based on assignment coverage results.
    """
    recs = []
    unassigned = plan.get("unassigned_population", 0)

    if unassigned > 0:
        recs.append(f"WARNING: Shelter capacity is INSUFFICIENT. {unassigned} people remain unassigned.")
        recs.append("Action: Open temporary shelters immediately to mitigate overflow risk.")
        recs.append("Action: Request district support for emergency tents and resources.")
        recs.append("Action: Activate emergency camps in safe surrounding sectors.")
    else:
        recs.append(f"Shelter assignment complete: 100% of affected population ({plan.get('affected_population')}) assigned to shelters.")

    if severity_level == "Critical":
        recs.append("Establish secure transport corridors between hazard zone and relief shelters.")

    return recs


def update_state(
    state: DisasterState,
    plan: Optional[dict],
    recommendations: list[str],
) -> DisasterState:
    """
    Updates state['shelter_plan'] and appends new recommendations.
    """
    state_recs = state.get("recommendations") or []
    combined_recs = list(state_recs)
    for r in recommendations:
        if r not in combined_recs:
            combined_recs.append(r)

    state = {
        **state,
        "shelter_plan": plan,
        "recommendations": combined_recs,
    }  # type: ignore[assignment]

    state = update_state_metadata(state, current_node=AGENT_NAME, data_source="PostgreSQL-Shelters")
    return state


# ===========================================================================
# MASTER NODE
# ===========================================================================

def run_shelter_assignment(state: DisasterState) -> DisasterState:
    """
    Master shelter assignment function — coordinates assignment flow.
    Acts as a node in the LangGraph shared workflow.
    """
    logger.info(
        f"\n{'='*60}\n"
        f"[ShelterAgent] ⛺ Starting Shelter Assignment Node\n"
        f"  Session: {state.get('session_id')}\n"
        f"{'='*60}"
    )
    t_start = time.monotonic()

    # 1. State validation
    state = update_state_metadata(state, current_node=AGENT_NAME)
    is_valid, issues = validate_state(state)
    if not is_valid:
        for issue in issues:
            state = update_state_metadata(state, current_node=AGENT_NAME, warning=issue)

    # 2. Run plan generation
    plan = generate_shelter_plan(state)

    # 3. Compile recommendations
    recs = []
    if plan:
        severity_level = state.get("severity_level", "Medium")
        recs = generate_recommendations(plan, severity_level)

    # 4. Save to state
    state = update_state(state, plan, recs)

    elapsed = round(time.monotonic() - t_start, 3)
    if plan:
        logger.success(
            f"[ShelterAgent] ✅ Shelter assignment complete in {elapsed}s\n"
            f"  Assigned   : {plan['assigned_population']} / {plan['affected_population']} people\n"
            f"  Unassigned : {plan['unassigned_population']} people\n"
            f"  Overflow   : {plan['overflow_risk']}\n"
        )
    else:
        logger.warning(f"[ShelterAgent] ⚠️ No shelter assignment plan generated in {elapsed}s.")

    return state


# ===========================================================================
# STANDALONE RUN
# ===========================================================================

if __name__ == "__main__":
    """
    Standalone test run of the Shelter Assignment Agent.
    Usage:
        cd disaster-ai
        $env:PYTHONPATH="."; python agents/shelter_agent.py
    """
    import json
    from workflows.state import create_initial_state, VerifiedReportState, GDACSEventState

    logger.info("[ShelterAgent] Standalone test starting...")

    # Build mock state
    state = create_initial_state(environment="development")
    state["severity_level"] = "Critical"

    # Add mock verified reports
    state["verified_reports"] = [
        VerifiedReportState(
            disaster_title="Guwahati Brahmaputra River Flood",
            verification_result="Verified",
            consensus_confidence=0.96,
        )
    ]

    # Add mock raw event with coordinates and population (1200 affected)
    state["disaster_events"] = [
        GDACSEventState(
            title="Guwahati Brahmaputra River Flood",
            latitude=26.1445,
            longitude=91.7362,
            affected_population=1200,
        )
    ]

    # Mock shelters (distance calculated relative to Guwahati lat=26.14, lon=91.73)
    mock_shelters = [
        {"id": "s-1", "name": "Shelter A", "city": "Guwahati", "capacity": 500, "occupied": 0, "latitude": 26.15, "longitude": 91.74},
        {"id": "s-2", "name": "Shelter B", "city": "Guwahati", "capacity": 400, "occupied": 0, "latitude": 26.16, "longitude": 91.75},
        {"id": "s-3", "name": "Shelter C", "city": "Guwahati", "capacity": 600, "occupied": 0, "latitude": 26.17, "longitude": 91.76},
    ]

    # Run direct testing
    logger.info("Executing assign_population_to_shelters direct test...")
    # Compute mock distances
    sorted_shelters_dist = find_nearest_shelters(26.1445, 91.7362, mock_shelters)
    assignments, assigned_total, unassigned_total = assign_population_to_shelters(1200, sorted_shelters_dist)

    print("\n" + "="*60)
    print("DIRECT ASSIGNMENT TEST (1200 affected):")
    print("="*60)
    print(f"Assigned   : {assigned_total}")
    print(f"Unassigned : {unassigned_total}")
    print("Breakdown:")
    for a in assignments:
        print(f"  * {a['name']} (Capacity: {a['capacity']}) -> Assigned: {a['assigned_people']} (dist={a['distance_km']}km)")
