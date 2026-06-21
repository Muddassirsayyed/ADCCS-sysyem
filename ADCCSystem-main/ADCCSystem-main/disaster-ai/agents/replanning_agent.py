"""
ADCC — Dynamic Replanning Agent
================================
Monitors changing environmental, sensor, and resource parameters to automatically
trigger updates to existing response plans (reallocation and resheltering).

Triggers:
    1. Rainfall Increase:
       - If rainfall > 50 mm/hr, increases flood risk, deploys 2 additional boats.
    2. Shelter Capacity Full:
       - If overflow_risk is True in shelter plan, opens a temporary camp and reassigns people.
    3. Resource Deficit:
       - If resource coverage drops below 80%, requests mutual aid and escalates alerts.
    4. Earthquake Aftershock:
       - If any verified earthquake magnitude >= 5.0, recalculates severity and deploys 1 medical team.

Position in Pipeline:
    [shelter_agent]          ← completes initial shelter assignments
         ↓
    [replanning_agent]       ← THIS FILE
         ↓
    [command_center]         (Future orchestrator phase)
"""

import time
from datetime import datetime, timezone
from typing import Any, Optional
from loguru import logger
from pydantic import BaseModel, Field

from workflows.state import (
    DisasterState,
    StateUpdate,
    update_state_metadata,
    validate_state,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "replanning_agent"


# ===========================================================================
# PYDANTIC VALIDATION MODELS
# ===========================================================================

class ReplanningActionRecord(BaseModel):
    """Details of a single action taken during replanning."""
    trigger: str = Field(..., description="Trigger event name")
    action: str = Field(..., description="Action taken by the agent")
    reason: str = Field(..., description="Reason/justification for the action")


class ReplanningActionsOutput(BaseModel):
    """Normalized output containing all actions taken during a replanning session."""
    actions: list[ReplanningActionRecord] = Field(..., description="List of replanning actions taken")


# ===========================================================================
# AGENT INTERNAL HELPERS
# ===========================================================================

def _get_allocated_quantities(allocations: list[dict]) -> dict[str, int]:
    """
    Returns a dictionary of resource_id -> quantity already allocated
    to prevent double-allocating in-use resources.
    """
    allocated_qtys = {}
    for alloc in allocations:
        res_id = alloc.get("resource_id")
        if res_id:
            allocated_qtys[res_id] = allocated_qtys.get(res_id, 0) + alloc.get("quantity", 0)
    return allocated_qtys


# ===========================================================================
# DEDICATED AGENT FUNCTIONS
# ===========================================================================

def detect_trigger_events(state: DisasterState) -> list[dict]:
    """
    Evaluates current state conditions (weather, plans, events) to detect replanning triggers.
    
    Returns:
        list[dict]: List of detected trigger events with trigger, action, and reason.
    """
    triggers = []
    
    # 1. Rainfall Increase Trigger (rainfall >= 50 mm/hr)
    weather = state.get("weather_data") or {}
    rain = weather.get("rainfall_mm", 0.0) or 0.0
    if rain >= 50.0:
        triggers.append({
            "type": "rainfall_increase",
            "trigger": "Rainfall Increase",
            "action": "Deploy 2 Additional Boats",
            "reason": f"Heavy rainfall of {rain} mm/hr detected. Flood risk increased by 25%."
        })

    # 2. Shelter Capacity Full Trigger
    shelter_plan = state.get("shelter_plan") or {}
    unassigned = shelter_plan.get("unassigned_population", 0) or 0
    if shelter_plan.get("overflow_risk") or unassigned > 0:
        triggers.append({
            "type": "shelter_full",
            "trigger": "Shelter Capacity Full",
            "action": "Open Temporary Relief Camp Delta",
            "reason": f"Vacant shelter capacity is exhausted. {unassigned} people remain unassigned."
        })

    # 3. Resource Deficit Trigger (coverage < 80%)
    alloc_plan = state.get("allocation_plan") or {}
    coverage = alloc_plan.get("estimated_coverage_pct", 100.0) or 100.0
    if coverage < 80.0:
        triggers.append({
            "type": "resource_deficit",
            "trigger": "Resource Deficit",
            "action": "Request Mutual Aid Support",
            "reason": f"Resource deployment coverage has dropped below safety limits to {coverage:.1f}%."
        })

    # 4. Earthquake Aftershock Trigger (verified magnitude >= 5.0)
    eq_events = state.get("earthquake_events") or []
    verified_reports = state.get("verified_reports") or []
    
    # Check if any verified reports are earthquakes with mag >= 5.0
    verified_eq_titles = {
        r.get("disaster_title") for r in verified_reports
        if "earthquake" in r.get("disaster_title", "").lower()
        and r.get("verification_result") in ("Verified", "High Confidence", "Confirmed")
    }

    high_mag_aftershock = False
    aftershock_mag = 0.0
    aftershock_place = ""

    for eq in eq_events:
        mag = eq.get("magnitude", 0.0)
        place = eq.get("place", "")
        title = f"M{mag} Earthquake — {place}"
        if (title in verified_eq_titles or any(place in vt for vt in verified_eq_titles)) and mag >= 5.0:
            high_mag_aftershock = True
            aftershock_mag = mag
            aftershock_place = place
            break

    if high_mag_aftershock:
        triggers.append({
            "type": "earthquake_aftershock",
            "trigger": "Earthquake Aftershock",
            "action": "Trigger 1 Additional Medical Team",
            "reason": f"High magnitude aftershock M{aftershock_mag} verified at '{aftershock_place}'."
        })

    logger.info(f"[ReplanningAgent] Detected {len(triggers)} replanning triggers in current state.")
    return triggers


def generate_reallocation_plan(
    state: DisasterState,
    triggers: list[dict],
    current_plan: dict,
) -> dict:
    """
    Modifies the current allocation plan by deploying additional resources.
    Uses reservation-aware matching to avoid double-allocating resources.
    """
    # Clone current plan to prevent in-place mutation
    updated_plan = dict(current_plan)
    allocations = list(updated_plan.get("allocations") or [])
    gaps = list(updated_plan.get("gaps") or [])

    resources_state = state.get("resources") or {}
    available_pool = resources_state.get("nearest_resources") or resources_state.get("available_resources") or []
    
    if not available_pool:
        logger.warning("[ReplanningAgent] No resource pool available for reallocation.")
        return updated_plan

    # Track currently locked resources and quantities
    allocated_qtys = _get_allocated_quantities(allocations)
    
    total_added = 0
    now_iso = datetime.now(timezone.utc).isoformat()

    # Process reallocation triggers
    for trig in triggers:
        res_type = ""
        qty_needed = 0
        
        if trig["type"] == "rainfall_increase":
            res_type = "Boat"
            qty_needed = 2
        elif trig["type"] == "earthquake_aftershock":
            res_type = "Medical Team"
            qty_needed = 1
            
        if qty_needed > 0:
            logger.info(f"[ReplanningAgent] Trigger '{trig['trigger']}' requires deploying {qty_needed} additional {res_type}(s).")
            remaining_needed = qty_needed
            
            # Match available pool resources
            for res in available_pool:
                if remaining_needed <= 0:
                    break
                    
                if res.get("resource_type") == res_type:
                    total_qty = res.get("quantity", 0)
                    used_qty = allocated_qtys.get(str(res.get("id")), 0)
                    available_qty = max(0, total_qty - used_qty)
                    
                    if available_qty <= 0:
                        continue
                        
                    to_alloc = min(remaining_needed, available_qty)
                    
                    # Merge with existing allocation if present, otherwise append
                    found = False
                    for alloc in allocations:
                        if alloc.get("resource_id") == str(res.get("id")):
                            alloc["quantity"] = alloc.get("quantity", 0) + to_alloc
                            alloc["reason"] = alloc.get("reason", "") + f" (Added {to_alloc} additional units during replanning)."
                            found = True
                            break
                            
                    if not found:
                        allocations.append({
                            "resource_id": str(res.get("id")),
                            "resource_name": res.get("resource_name"),
                            "quantity": to_alloc,
                            "reason": f"Allocated {to_alloc} additional {res_type} in response to {trig['trigger']} trigger."
                        })

                    allocated_qtys[str(res.get("id"))] = allocated_qtys.get(str(res.get("id")), 0) + to_alloc
                    remaining_needed -= to_alloc
                    total_added += to_alloc

            if remaining_needed > 0:
                deficit_msg = f"Deficit of {remaining_needed} additional {res_type}(s) during replanning"
                gaps.append(deficit_msg)
                logger.warning(f"[ReplanningAgent] Allocation Gap: Could not satisfy {remaining_needed} {res_type}(s).")

    # Update counts and recalculate coverage
    # Get original requirements count
    original_total = updated_plan.get("total_resources_deployed", 0)
    updated_total = original_total + total_added
    
    # Calculate updated coverage
    # If there was a deficit, coverage drops. We estimate based on updated numbers
    # (Total Deployed / Total Needed)
    # Total Needed = Total Deployed + Deficits
    total_gaps_count = 0
    for g in gaps:
        try:
            # Extract digits from gap message
            digits = "".join([c for c in g if c.isdigit()])
            if digits:
                total_gaps_count += int(digits)
        except Exception:
            total_gaps_count += 1

    total_needed = updated_total + total_gaps_count
    updated_coverage = (float(updated_total) / float(total_needed)) * 100.0 if total_needed > 0 else 100.0

    updated_plan["allocations"] = allocations
    updated_plan["gaps"] = gaps
    updated_plan["total_resources_deployed"] = updated_total
    updated_plan["estimated_coverage_pct"] = round(updated_coverage, 2)
    updated_plan["plan_version"] = updated_plan.get("plan_version", 1) + 1
    updated_plan["plan_created_at"] = now_iso

    return updated_plan


def generate_resheltering_plan(
    state: DisasterState,
    triggers: list[dict],
    current_plan: dict,
) -> dict:
    """
    Modifies the current shelter plan by opening temporary emergency relief camps
    and reassigning the unassigned overflow population.
    """
    updated_plan = dict(current_plan)
    assigned_shelters = list(updated_plan.get("assigned_shelters") or [])
    unassigned = updated_plan.get("unassigned_population", 0)

    # Check if shelter capacity trigger is active
    has_capacity_trigger = any(t["type"] == "shelter_full" for t in triggers)
    
    if has_capacity_trigger and unassigned > 0:
        logger.info(f"[ReplanningAgent] Triggering alternate shelters for {unassigned} unassigned evacuees.")
        
        # Open Temporary Relief Camp Delta with capacity 1000
        camp_capacity = 1000
        assigned_to_camp = min(unassigned, camp_capacity)
        
        camp_record = {
            "shelter_id": "temp-camp-delta",
            "name": "Temporary Relief Camp Delta",
            "city": "Disaster Zone City",
            "capacity": camp_capacity,
            "assigned_people": assigned_to_camp,
            "distance_km": 5.0
        }
        
        assigned_shelters.append(camp_record)
        
        # Recalculate plan variables
        updated_unassigned = max(0, unassigned - assigned_to_camp)
        updated_assigned = updated_plan.get("assigned_population", 0) + assigned_to_camp
        
        updated_plan["assigned_shelters"] = assigned_shelters
        updated_plan["assigned_population"] = updated_assigned
        updated_plan["unassigned_population"] = updated_unassigned
        updated_plan["overflow_risk"] = updated_unassigned > 0
        updated_plan["plan_created_at"] = datetime.now(timezone.utc).isoformat()
        
        # Update shelter assignments list for example schema
        shelter_assignments = list(updated_plan.get("shelter_assignments") or [])
        shelter_assignments.append({
            "shelter": "Temporary Relief Camp Delta",
            "assigned": assigned_to_camp
        })
        updated_plan["shelter_assignments"] = shelter_assignments
        
        # Remove trigger recommendations since camp has been opened
        recomm = list(updated_plan.get("recommended_additional_shelters") or [])
        if "Open temporary shelters" in recomm:
            recomm.remove("Open temporary shelters")
        updated_plan["recommended_additional_shelters"] = recomm

        logger.success(f"[ReplanningAgent] Resheltered {assigned_to_camp} evacuees at Temporary Relief Camp Delta.")

    return updated_plan


def generate_recommendations(triggers: list[dict]) -> list[str]:
    """
    Generates tailored dashboard advisory statements based on triggered replanning events.
    """
    recs = []
    for trig in triggers:
        recs.append(f"Replanning Node: {trig['action']} due to trigger '{trig['trigger']}'.")
        
        if trig["type"] == "resource_deficit":
            recs.append("Mitigation: Escalate emergency response level. Mobilize state reserve resource units.")
        elif trig["type"] == "rainfall_increase":
            recs.append("Mitigation: Alert rescue units of elevated flash-flood risks. Prepare water evacuations.")

    return recs


def evaluate_current_plan(
    state: DisasterState,
    triggers: list[dict],
) -> tuple[Optional[dict], Optional[dict]]:
    """
    Core logic evaluating current plans against triggers.
    Runs reallocation and resheltering workflows.
    
    Returns:
        tuple[Optional[dict], Optional[dict]]: (updated_allocation_plan, updated_shelter_plan)
    """
    # 1. Allocation plan updates
    alloc_plan = state.get("allocation_plan")
    updated_alloc = None
    if alloc_plan:
        has_alloc_trigger = any(t["type"] in ("rainfall_increase", "earthquake_aftershock", "resource_deficit") for t in triggers)
        if has_alloc_trigger:
            updated_alloc = generate_reallocation_plan(state, triggers, alloc_plan)
            
    # 2. Shelter plan updates
    shelter_plan = state.get("shelter_plan")
    updated_shelter = None
    if shelter_plan:
        has_shelter_trigger = any(t["type"] == "shelter_full" for t in triggers)
        if has_shelter_trigger:
            updated_shelter = generate_resheltering_plan(state, triggers, shelter_plan)

    return updated_alloc, updated_shelter


def update_state(
    state: DisasterState,
    updated_alloc: Optional[dict],
    updated_shelter: Optional[dict],
    replanning_actions: list[dict],
    recommendations: list[str],
) -> DisasterState:
    """
    Saves updated plans, registers actions in metadata, and appends advisories.
    """
    state_recs = state.get("recommendations") or []
    combined_recs = list(state_recs)
    for r in recommendations:
        if r not in combined_recs:
            combined_recs.append(r)

    # Save to state
    state = {
        **state,
        "recommendations": combined_recs,
    }  # type: ignore[assignment]

    if updated_alloc:
        state["allocation_plan"] = updated_alloc
    if updated_shelter:
        state["shelter_plan"] = updated_shelter

    # Append triggers/actions directly in the metadata trace
    meta = dict(state.get("metadata") or {})
    warnings = list(meta.get("warnings") or [])
    
    for action in replanning_actions:
        warnings.append(f"[ReplanningTrigger] {action['trigger']} -> Action: {action['action']} (Reason: {action['reason']})")
    meta["warnings"] = warnings

    state = {
        **state,
        "metadata": meta,
        "replanning_actions": replanning_actions,  # Custom agent outputs field
    }  # type: ignore[assignment]

    state = update_state_metadata(state, current_node=AGENT_NAME)
    return state


# ===========================================================================
# MASTER NODE
# ===========================================================================

def run_dynamic_replanning(state: DisasterState) -> DisasterState:
    """
    Master dynamic replanning function — monitors conditions and executes updates.
    Acts as a node in the LangGraph workflow structure.
    """
    logger.info(
        f"\n{'='*60}\n"
        f"[ReplanningAgent] 🔄 Starting Dynamic Replanning Node\n"
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

    # 2. Trigger detection
    triggers = detect_trigger_events(state)
    
    # Check if any triggers fired
    if not triggers:
        logger.info("[ReplanningAgent] No replanning triggers active. Plans remain unchanged.")
        state = update_state_metadata(state, current_node=AGENT_NAME)
        return state

    # Validate trigger output format via Pydantic
    try:
        validated = ReplanningActionsOutput(actions=[ReplanningActionRecord(**t) for t in triggers])
        logger.info(f"[ReplanningAgent] Verified trigger records: {len(validated.actions)} actions compiled.")
    except Exception as e:
        logger.error(f"[ReplanningAgent] Pydantic trigger validation failed: {e}")

    # 3. Apply trigger-specific state changes before plan evaluation
    # 3.1. Rainfall Increase -> Increase flood risk
    has_rainfall_trigger = any(t["type"] == "rainfall_increase" for t in triggers)
    if has_rainfall_trigger:
        weather = state.get("weather_data") or {}
        updated_weather = dict(weather)
        updated_weather["flood_risk"] = True
        state = {**state, "weather_data": updated_weather}  # type: ignore[assignment]
        logger.info("[ReplanningAgent] Rainfall threshold exceeded: Set weather_data['flood_risk'] = True.")

    # 3.2. Resource Deficit -> Increase emergency response level (escalate severity_level)
    has_resource_deficit = any(t["type"] == "resource_deficit" for t in triggers)
    if has_resource_deficit:
        current_level = state.get("severity_level", "Low")
        escalation_map = {
            "Low": "Medium",
            "Medium": "High",
            "High": "Critical",
            "Critical": "Critical"
        }
        new_level = escalation_map.get(current_level, "High")
        if new_level != current_level:
            state = {**state, "severity_level": new_level}  # type: ignore[assignment]
            logger.info(f"[ReplanningAgent] Resource deficit trigger: Escalated severity_level from {current_level} to {new_level}.")

    # 3.3. Earthquake Aftershock -> Recalculate severity
    has_aftershock_trigger = any(t["type"] == "earthquake_aftershock" for t in triggers)
    if has_aftershock_trigger:
        logger.info("[ReplanningAgent] Earthquake aftershock trigger detected: Recalculating severity...")
        try:
            from agents.severity_agent import run_severity_assessment
            state = run_severity_assessment(state)
        except Exception as e:
            logger.error(f"[ReplanningAgent] Severity recalculation failed: {e}")

    # 4. Evaluate plans
    updated_alloc, updated_shelter = evaluate_current_plan(state, triggers)

    # 5. Compile recommendations
    recs = generate_recommendations(triggers)

    # 6. Save updates to state
    state = update_state(
        state=state,
        updated_alloc=updated_alloc,
        updated_shelter=updated_shelter,
        replanning_actions=triggers,
        recommendations=recs,
    )

    elapsed = round(time.monotonic() - t_start, 3)
    logger.success(f"[ReplanningAgent] ✅ Dynamic replanning complete in {elapsed}s. Updated plans pushed.")
    return state


# ===========================================================================
# STANDALONE RUN
# ===========================================================================

if __name__ == "__main__":
    """
    Standalone test run of the Dynamic Replanning Agent.
    Usage:
        cd disaster-ai
        $env:PYTHONPATH="."; python agents/replanning_agent.py
    """
    import json
    from workflows.state import create_initial_state, WeatherStateData, ResourceStateData

    logger.info("[ReplanningAgent] Standalone test starting...")

    # Build initial mock state
    state = create_initial_state(environment="development")
    
    # 1. Weather data: Rainfall = 55.0 mm/hr (triggers Rainfall Increase)
    state["weather_data"] = WeatherStateData(
        rainfall_mm=55.0,
        flood_risk=True
    )

    # 2. Mock allocation plan with low coverage (triggers Resource Deficit)
    state["allocation_plan"] = {
        "disaster_title": "Mumbai Flood Disaster",
        "allocations": [
            {"resource_id": "boat-1", "resource_name": "Rescue Boat A", "quantity": 2, "reason": "Flood rescue"}
        ],
        "total_resources_deployed": 2,
        "estimated_coverage_pct": 50.0,  # Below 80%!
        "gaps": ["Deficit of 2 Boat(s)"],
        "plan_version": 1,
    }

    # 3. Mock shelter plan with overflow (triggers Shelter Capacity Full)
    state["shelter_plan"] = {
        "overflow_risk": True,
        "unassigned_population": 400,
        "assigned_population": 800,
        "affected_population": 1200,
        "assigned_shelters": [
            {"shelter_id": "s-1", "name": "Shelter A", "city": "Mumbai", "capacity": 800, "assigned_people": 800}
        ],
        "shelter_assignments": [
            {"shelter": "Shelter A", "assigned": 800}
        ],
        "recommended_additional_shelters": ["Open temporary shelters"]
    }

    # 4. Earthquake Aftershock (triggers Earthquake Aftershock)
    state["earthquake_events"] = [
        {"usgs_id": "eq-1", "magnitude": 5.4, "place": "Mumbai Region, India", "severity_mapped": "High"}
    ]
    state["verified_reports"] = [
        {
            "disaster_title": "M5.4 Earthquake — Mumbai Region, India",
            "verification_result": "Verified",
            "consensus_confidence": 0.95
        }
    ]

    # Mock resources pool (with extra boats and medical team)
    state["resources"] = ResourceStateData(
        total_resources=15,
        available_count=10,
        nearest_resources=[
            {"id": "boat-1", "resource_name": "Rescue Boat A", "resource_type": "Boat", "quantity": 2}, # Already fully in use
            {"id": "boat-2", "resource_name": "Rescue Boat B", "resource_type": "Boat", "quantity": 4}, # vacant pool
            {"id": "med-1", "resource_name": "Emergency Medical Team A", "resource_type": "Medical Team", "quantity": 2}, # vacant pool
        ]
    )

    # Run the replanning agent
    updated_state = run_dynamic_replanning(state)
    actions = updated_state.get("replanning_actions")

    print("\n" + "="*60)
    print("STANDALONE REPLANNING RESULTS:")
    print("="*60)
    print("Replanning Actions Taken:")
    print(json.dumps(actions, indent=2))
    
    print("\nUpdated Allocation Plan:")
    print(json.dumps(updated_state.get("allocation_plan"), indent=2))

    print("\nUpdated Shelter Plan:")
    print(json.dumps(updated_state.get("shelter_plan"), indent=2))
