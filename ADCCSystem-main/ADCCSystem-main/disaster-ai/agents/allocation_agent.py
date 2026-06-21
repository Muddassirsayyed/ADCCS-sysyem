"""
ADCC — Resource Allocation Agent
=================================
Automatically allocates available physical resources from the database 
based on verified disaster type and severity levels.

Position in Pipeline:
    [severity_agent]         ← calculates severity levels
         ↓
    [allocation_agent]       ← THIS FILE
         ↓
    [replanning_agent]       (Future phase)
"""

import time
from datetime import datetime, timezone
from typing import Any, Optional
from loguru import logger

from workflows.state import (
    DisasterState,
    StateUpdate,
    AllocationPlanState,
    update_state_metadata,
    validate_state,
)

# ---------------------------------------------------------------------------
# Constants & Rules Mapping
# ---------------------------------------------------------------------------

AGENT_NAME = "allocation_agent"

# Deterministic resource allocation rules based on disaster type and severity
ALLOCATION_RULES: dict[str, dict[str, dict[str, int]]] = {
    "Flood": {
        "Low":      {"Boat": 1},
        "Medium":   {"Boat": 2, "Ambulance": 1},
        "High":     {"Boat": 3, "Ambulance": 2, "Medical Team": 1},
        "Critical": {"Boat": 5, "Ambulance": 3, "Medical Team": 2, "NDRF Unit": 1},
    },
    "Earthquake": {
        "Low":      {},
        "Medium":   {"Ambulance": 2},
        "High":     {"Ambulance": 3, "Medical Team": 2},
        "Critical": {"Ambulance": 4, "Medical Team": 3, "Rescue Team": 2, "NDRF Unit": 1},
    },
    "Cyclone": {
        "Low":      {},
        "Medium":   {},
        "High":     {"Boat": 2, "Ambulance": 2, "NDRF Unit": 1},
        "Critical": {"Boat": 4, "Ambulance": 3, "NDRF Unit": 2},
    }
}


# ===========================================================================
# DEDICATED AGENT FUNCTIONS
# ===========================================================================

def analyze_disaster_type(disaster_title: str) -> str:
    """
    Parses a disaster title to extract its primary category (Flood, Earthquake, Cyclone).
    Defaults to 'Flood' if no matching keywords are found.
    """
    title_lower = disaster_title.lower()
    if "flood" in title_lower or "rain" in title_lower or "waterlogging" in title_lower:
        return "Flood"
    elif "cyclone" in title_lower or "storm" in title_lower or "hurricane" in title_lower:
        return "Cyclone"
    elif "earthquake" in title_lower or "seismic" in title_lower or "quake" in title_lower:
        return "Earthquake"
    
    logger.warning(f"[AllocationAgent] Could not determine disaster type from title: '{disaster_title}'. Defaulting to 'Flood'.")
    return "Flood"


def calculate_resource_needs(disaster_type: str, severity_level: str) -> dict[str, int]:
    """
    Returns the required quantities of physical resources based on deterministic rules.
    """
    type_rules = ALLOCATION_RULES.get(disaster_type)
    if not type_rules:
        logger.warning(f"[AllocationAgent] No allocation rules for type '{disaster_type}'. Using empty requirements.")
        return {}

    needs = type_rules.get(severity_level)
    if needs is None:
        logger.debug(f"[AllocationAgent] No rules specified for type '{disaster_type}' at severity '{severity_level}'.")
        return {}

    return needs


def check_resource_availability(
    needed: dict[str, int],
    available_pool: list[dict],
    disaster_type: str,
    severity_level: str,
) -> tuple[list[dict], list[str], float]:
    """
    Matches requirements against the available/nearest pool.
    Selects closest resources first (relying on pre-sorted nearest_resources).
    
    Returns:
        tuple[list[dict], list[str], float]: (allocations, gaps, coverage_pct)
    """
    allocations: list[dict] = []
    gaps: list[str] = []
    
    if not needed:
        return allocations, gaps, 100.0

    allocated_count = 0
    needed_count = sum(needed.values())

    for res_type, needed_qty in needed.items():
        remaining_needed = needed_qty
        
        # Traverse available pool to match resource type
        for res in available_pool:
            if remaining_needed <= 0:
                break
                
            r_type = res.get("resource_type")
            if r_type and r_type.lower() == res_type.lower():
                qty_available = res.get("quantity", 0)
                if qty_available <= 0:
                    continue
                
                allocated_qty = min(remaining_needed, qty_available)
                if allocated_qty > 0:
                    allocations.append({
                        "resource_id": str(res.get("id")),
                        "resource_name": res.get("resource_name"),
                        "quantity": allocated_qty,
                        "reason": (
                            f"Deployed {allocated_qty} {res_type}(s) to support verified "
                            f"{severity_level} {disaster_type} response operations."
                        )
                    })
                    remaining_needed -= allocated_qty
                    allocated_count += allocated_qty

        if remaining_needed > 0:
            deficit_msg = f"Deficit of {remaining_needed} {res_type}(s)"
            gaps.append(deficit_msg)
            logger.warning(f"[AllocationAgent] Resource Deficit: Need {remaining_needed} more {res_type}(s)!")

    coverage_pct = (float(allocated_count) / float(needed_count)) * 100.0 if needed_count > 0 else 100.0
    return allocations, gaps, round(coverage_pct, 2)


def generate_allocation_plan(state: DisasterState) -> Optional[AllocationPlanState]:
    """
    Selects the primary verified report and compiles the resource allocation decisions.
    
    Returns:
        Optional[AllocationPlanState]: Structured allocation plan or None if no confirmed reports
    """
    verified_reports = state.get("verified_reports") or []
    if not verified_reports:
        logger.warning("[AllocationAgent] No verified disaster reports. Skipping allocation plan.")
        return None

    # Filter verified events with high/medium/critical status
    active_reports = [
        r for r in verified_reports
        if r.get("verification_result") in ("Verified", "High Confidence", "Medium Confidence", "Confirmed")
    ]

    if not active_reports:
        logger.warning("[AllocationAgent] No confirmed/verified disasters to allocate resources for.")
        return None

    # Pick the top primary report based on confidence level
    sorted_reports = sorted(
        active_reports,
        key=lambda r: r.get("consensus_confidence", 0.0),
        reverse=True
    )
    primary_report = sorted_reports[0]
    
    disaster_title = primary_report.get("disaster_title", "Unknown Disaster")
    disaster_id = primary_report.get("disaster_id", "")
    
    # 1. Analyze type and check severity
    disaster_type = analyze_disaster_type(disaster_title)
    severity_level = state.get("severity_level", "Medium")

    # 2. Get resource requirements
    needed = calculate_resource_needs(disaster_type, severity_level)
    logger.info(f"[AllocationAgent] Resource requirements for '{disaster_title}' ({disaster_type} - {severity_level}): {needed}")

    # 3. Pull resource pool from state (prefer pre-sorted nearest_resources)
    resources_state = state.get("resources") or {}
    available_pool = resources_state.get("nearest_resources") or resources_state.get("available_resources") or []
    
    if not available_pool:
        logger.warning("[AllocationAgent] No available resources found in state.")

    # 4. Check matching and coverage
    allocations, gaps, coverage = check_resource_availability(
        needed=needed,
        available_pool=available_pool,
        disaster_type=disaster_type,
        severity_level=severity_level,
    )

    total_deployed = sum(a["quantity"] for a in allocations)
    now_iso = datetime.now(timezone.utc).isoformat()

    plan = AllocationPlanState(
        disaster_id=disaster_id,
        disaster_title=disaster_title,
        allocations=allocations,
        total_resources_deployed=total_deployed,
        estimated_coverage_pct=coverage,
        gaps=gaps,
        plan_created_at=now_iso,
        plan_version=1,
    )

    return plan


def generate_recommendations(plan: AllocationPlanState, severity_level: str) -> list[str]:
    """
    Generates actionable allocation dashboard recommendations.
    """
    recs = []
    
    disaster_title = plan.get("disaster_title", "Disaster Zone")
    coverage = plan.get("estimated_coverage_pct", 100.0)
    gaps = plan.get("gaps") or []

    if coverage >= 100.0:
        recs.append(f"Successfully allocated 100% of required safety resources to {disaster_title}.")
    elif coverage >= 50.0:
        recs.append(f"Partial resource allocation complete ({coverage}% coverage) for {disaster_title}. Deficits present.")
    else:
        recs.append(f"CRITICAL RESOURCE DEFICIT ({coverage}% coverage) for {disaster_title}! Urgent action required.")

    # Specific gap mitigation recommendations
    for gap in gaps:
        recs.append(f"Mitigation: Request mutual aid from adjacent districts to resolve '{gap}'.")

    if severity_level == "Critical":
        recs.append(f"Deploy all allocated resources to {disaster_title} under emergency transport escort.")

    return recs


def update_state(
    state: DisasterState,
    plan: Optional[AllocationPlanState],
    recommendations: list[str],
) -> DisasterState:
    """
    Saves the allocation plan and appends recommendations to state.
    """
    state_recs = state.get("recommendations") or []
    # Merge existing recommendations with new allocation advisories
    combined_recs = list(state_recs)
    for r in recommendations:
        if r not in combined_recs:
            combined_recs.append(r)

    state = {
        **state,
        "allocation_plan": plan,
        "recommendations": combined_recs,
    }  # type: ignore[assignment]

    state = update_state_metadata(state, current_node=AGENT_NAME, data_source="PostgreSQL-Resources")
    return state


# ===========================================================================
# MASTER ENTRY POINT
# ===========================================================================

def run_resource_allocation(state: DisasterState) -> DisasterState:
    """
    Master allocation agent function — determines resource assignments
    and returns updated DisasterState.
    Suitable as a node in the LangGraph execution flow.
    """
    logger.info(
        f"\n{'='*60}\n"
        f"[AllocationAgent] 🚁 Starting Resource Allocation Node\n"
        f"  Session: {state.get('session_id')}\n"
        f"{'='*60}"
    )
    t_start = time.monotonic()

    # 1. Validate state
    state = update_state_metadata(state, current_node=AGENT_NAME)
    is_valid, issues = validate_state(state)
    if not is_valid:
        for issue in issues:
            state = update_state_metadata(state, current_node=AGENT_NAME, warning=issue)

    # 2. Compile allocation plan
    plan = generate_allocation_plan(state)

    # 3. Generate recommendations if plan exists
    recs = []
    if plan:
        severity_level = state.get("severity_level", "Medium")
        recs = generate_recommendations(plan, severity_level)

    # 4. Save to state
    state = update_state(state, plan, recs)

    elapsed = round(time.monotonic() - t_start, 3)
    
    if plan:
        logger.success(
            f"[AllocationAgent] ✅ Allocation complete in {elapsed}s\n"
            f"  Disaster Title : {plan['disaster_title']}\n"
            f"  Deployed Count : {plan['total_resources_deployed']} units\n"
            f"  Coverage       : {plan['estimated_coverage_pct']}%\n"
            f"  Gaps Count     : {len(plan['gaps'])}\n"
        )
    else:
        logger.warning(f"[AllocationAgent] ⚠️ No resource allocation plan generated in {elapsed}s.")

    return state


# ===========================================================================
# STANDALONE RUN
# ===========================================================================

if __name__ == "__main__":
    """
    Standalone test run of the Resource Allocation Agent.
    Usage:
        cd disaster-ai
        $env:PYTHONPATH="."; python agents/allocation_agent.py
    """
    import json
    from workflows.state import create_initial_state, VerifiedReportState, ResourceStateData

    logger.info("[AllocationAgent] Standalone test starting...")

    # Build fresh mock state
    state = create_initial_state(environment="development")
    state["severity_level"] = "Critical"
    state["severity_score"] = 0.90

    # Add mock verified reports
    state["verified_reports"] = [
        VerifiedReportState(
            disaster_title="Mumbai suburban flood incident",
            verification_result="Verified",
            consensus_confidence=0.95,
        )
    ]

    # Add mock resources near Mumbai
    state["resources"] = ResourceStateData(
        total_resources=50,
        available_count=20,
        nearest_resources=[
            {"id": "res-boat-1", "resource_name": "Rescue Boat A", "resource_type": "Boat", "quantity": 2},
            {"id": "res-boat-2", "resource_name": "Rescue Boat B", "resource_type": "Boat", "quantity": 2},
            # We need 5 boats, so 2+2=4. Deficit of 1 boat.
            {"id": "res-amb-1", "resource_name": "Ambulance A", "resource_type": "Ambulance", "quantity": 4},
            # We need 3 ambulances. Satisfied by res-amb-1 (allocates 3).
            {"id": "res-med-1", "resource_name": "Medical Team Alpha", "resource_type": "Medical Team", "quantity": 1},
            # We need 2 medical teams. Deficit of 1 team.
            {"id": "res-ndrf-1", "resource_name": "NDRF 5th Bn Unit-A", "resource_type": "NDRF Unit", "quantity": 1},
            # We need 1 NDRF unit. Satisfied by res-ndrf-1 (allocates 1).
        ]
    )

    # Run allocation
    updated_state = run_resource_allocation(state)
    plan = updated_state.get("allocation_plan")

    print("\n" + "="*60)
    print("STANDALONE ALLOCATION PLAN RESULTS:")
    print("="*60)
    if plan:
        print(f"Target Incident: {plan['disaster_title']}")
        print(f"Coverage       : {plan['estimated_coverage_pct']}%")
        print(f"Total Deployed : {plan['total_resources_deployed']}")
        print("\nAllocated Units:")
        for alloc in plan["allocations"]:
            print(f"  • {alloc['resource_name']} (Qty: {alloc['quantity']})")
            print(f"    Reason: {alloc['reason']}")
        print("\nGaps Identified:")
        for gap in plan["gaps"]:
            print(f"  • {gap}")
        print("\nAdvisories:")
        for rec in updated_state.get("recommendations", []):
            print(f"  * {rec}")
    else:
        print("No plan generated.")
