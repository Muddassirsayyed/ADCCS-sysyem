"""
ADCC — Agentic LangGraph Orchestration Layer
=============================================
Defines the agentic StateGraph structure for the Autonomous Disaster Command Center.

ARCHITECTURE CHANGE (v2.0):
    OLD: Fixed linear pipeline
        START → collect_data → verification → severity → allocation → shelter → replanning → END

    NEW: Supervisor-driven agentic loop with conditional edges and parallel fan-out
        START → supervisor ──(conditional)──→ [agent(s)] ──→ supervisor ──(loop)──→ ... → END

Key Design Principles:
    1. Supervisor is the single router — no hardcoded agent sequences.
    2. Conditional edges read supervisor_decision.next_agents from state.
    3. Parallel fan-out: allocation + shelter run simultaneously on High/Critical.
    4. Each agent reports back to the Supervisor for re-evaluation.
    5. Max 10 supervisor iterations as a safety guard.
    6. New events mid-cycle trigger dynamic replanning.

Graph Nodes:
    supervisor      → Supervisor Agent (router)
    collect_data    → Data Collection Agent
    verification    → Verification Agent
    severity        → Severity Assessment Agent
    allocation      → Resource Allocation Agent
    shelter         → Shelter Assignment Agent
    route_planning  → Route Planning Agent
    notification    → Notification Agent
    replanning      → Dynamic Replanning Agent

Routing Flow:
    START
      ↓
    supervisor ──→ collect_data ──┐
    supervisor ──→ verification ──┤
    supervisor ──→ severity ──────┤──→ supervisor (loop)
    supervisor ──→ allocation ────┤
    supervisor ──→ shelter ───────┤
    supervisor ──→ route_planning ┤
    supervisor ──→ notification ──┤
    supervisor ──→ replanning ────┘
    supervisor ──→ END
"""

from loguru import logger
from langgraph.graph import StateGraph, START, END

from workflows.state import DisasterState, create_initial_state
from workflows.nodes import (
    supervisor_node,
    collect_data_node,
    verification_node,
    severity_node,
    allocation_node,
    shelter_node,
    route_planning_node,
    notification_node,
    replanning_node,
)
from agents.supervisor_agent import supervisor_route


# ===========================================================================
# ROUTING MAP
# ===========================================================================

# Maps routing target strings (from supervisor_decision.next_agents) to node names.
# Must include all valid agent names + the END sentinel.
ROUTING_MAP: dict[str, str] = {
    "collect_data":   "collect_data",
    "verification":   "verification",
    "severity":       "severity",
    "allocation":     "allocation",
    "shelter":        "shelter",
    "route_planning": "route_planning",
    "notification":   "notification",
    "replanning":     "replanning",
    "__end__":        END,
}


# ===========================================================================
# GRAPH BUILDER
# ===========================================================================

def build_graph():
    """
    Constructs and compiles the ADCC agentic LangGraph StateGraph.

    Architecture:
        - All agent nodes register back-edges to the supervisor.
        - The supervisor uses conditional edges to fan-out to one or more agents.
        - Parallel execution is achieved via LangGraph's native fan-out when
          supervisor_route returns a list.

    Returns:
        CompiledStateGraph: The compiled agentic workflow.
    """
    logger.info("[ADCCGraph v2] Building agentic StateGraph with Supervisor routing...")

    builder = StateGraph(DisasterState)

    # ── 1. Register all nodes ────────────────────────────────────────────────
    builder.add_node("supervisor",     supervisor_node)
    builder.add_node("collect_data",   collect_data_node)
    builder.add_node("verification",   verification_node)
    builder.add_node("severity",       severity_node)
    builder.add_node("allocation",     allocation_node)
    builder.add_node("shelter",        shelter_node)
    builder.add_node("route_planning", route_planning_node)
    builder.add_node("notification",   notification_node)
    builder.add_node("replanning",     replanning_node)

    # ── 2. Entry point: START → supervisor ───────────────────────────────────
    builder.add_edge(START, "supervisor")

    # ── 3. Conditional edge: supervisor → [agent(s)] or END ─────────────────
    # supervisor_route() reads state["supervisor_decision"]["next_agents"] and
    # returns either a single node name, a list (parallel), or "__end__".
    builder.add_conditional_edges(
        "supervisor",
        supervisor_route,
        ROUTING_MAP,
    )

    # ── 4. All agents report back to supervisor ───────────────────────────────
    for agent_node in [
        "collect_data",
        "verification",
        "severity",
        "allocation",
        "shelter",
        "route_planning",
        "notification",
        "replanning",
    ]:
        builder.add_edge(agent_node, "supervisor")

    # ── 5. Compile ────────────────────────────────────────────────────────────
    graph = builder.compile()
    logger.success("[ADCCGraph v2] Agentic LangGraph workflow compiled successfully.")
    return graph


# ===========================================================================
# EXECUTION HELPER
# ===========================================================================

def run_graph(initial_state: dict) -> dict:
    """
    Executes the ADCC agentic StateGraph with the provided initial state.

    The Supervisor Agent is the entry point and dynamically routes through
    agents based on goals, confidence, and changing conditions.

    Args:
        initial_state: dict with input parameters:
            - latitude, longitude: Disaster zone coordinates
            - location_label:      Human-readable location name
            - country:             Country name
            - session_id:          Optional custom session ID
            - environment:         "development" | "production"

    Returns:
        dict: Normalized response with execution results and final state.

    Example:
        result = run_graph({
            "latitude": 26.14,
            "longitude": 91.74,
            "location_label": "Guwahati Flood Zone",
            "country": "India",
        })
        print(result["severity"])    # "Critical"
        print(result["supervisor_iterations"])
    """
    logger.info("[ADCCGraph v2] Executing agentic workflow...")

    try:
        # Initialize full state with safe defaults
        state = create_initial_state(
            session_id=initial_state.get("session_id"),
            environment=initial_state.get("environment", "development"),
        )

        # Merge input fields (coordinates, label, etc.)
        state.update(initial_state)

        # Compile and invoke agentic graph
        graph = build_graph()
        final_state = graph.invoke(state)

        # ── Extract result metrics ────────────────────────────────────────────
        alloc_plan = final_state.get("allocation_plan")
        resources_allocated = (
            alloc_plan is not None
            and len(alloc_plan.get("allocations") or []) > 0
        )

        shelter_plan = final_state.get("shelter_plan")
        shelters_assigned = (
            shelter_plan is not None
            and len(shelter_plan.get("assigned_shelters") or []) > 0
        )

        route_plan = final_state.get("route_plan")
        routes_planned = route_plan is not None

        # Convert confidence score (0.0–1.0) to percentage
        confidence_val = final_state.get("confidence_score", 0.0)
        confidence_pct = (
            int(round(confidence_val * 100))
            if 0.0 <= confidence_val <= 1.0
            else int(round(confidence_val))
        )

        supervisor_iterations = final_state.get("supervisor_iterations", 0)
        agents_completed      = final_state.get("agents_completed", [])
        notification_sent     = final_state.get("notification_sent", False)

        logger.success(
            f"[ADCCGraph v2] Workflow complete | "
            f"Severity: {final_state.get('severity_level')} | "
            f"Iterations: {supervisor_iterations} | "
            f"Agents: {set(agents_completed)}"
        )

        return {
            "status":                "success",
            "severity":              final_state.get("severity_level", "Low"),
            "confidence":            confidence_pct,
            "resources_allocated":   resources_allocated,
            "shelters_assigned":     shelters_assigned,
            "routes_planned":        routes_planned,
            "notification_sent":     notification_sent,
            "supervisor_iterations": supervisor_iterations,
            "agents_completed":      list(set(agents_completed)),
            "recommendations":       final_state.get("recommendations", []),
            "state":                 final_state,
        }

    except Exception as e:
        logger.error(f"[ADCCGraph v2] Exception during agentic workflow: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status":                "error",
            "error_message":         str(e),
            "severity":              "Unknown",
            "confidence":            0,
            "resources_allocated":   False,
            "shelters_assigned":     False,
            "routes_planned":        False,
            "notification_sent":     False,
            "supervisor_iterations": 0,
            "agents_completed":      [],
        }


# ===========================================================================
# STANDALONE VERIFICATION
# ===========================================================================

if __name__ == "__main__":
    """
    Standalone agentic workflow verification.
    Usage:
        cd disaster-ai
        $env:PYTHONPATH="."; python workflows/graph.py
    """
    import json

    logger.info("[ADCCGraph v2] Standalone agentic workflow test starting...")

    test_input = {
        "latitude":       26.1445,
        "longitude":      91.7362,
        "location_label": "Guwahati Flood Zone",
        "country":        "India",
    }

    result = run_graph(test_input)

    print("\n" + "=" * 70)
    print("ADCC AGENTIC WORKFLOW RESULT (v2.0 — Supervisor Architecture)")
    print("=" * 70)
    safe_result = {k: v for k, v in result.items() if k != "state"}
    print(json.dumps(safe_result, indent=2))

    print("\nSupervisor Iterations:   ", result.get("supervisor_iterations"))
    print("Agents Completed:        ", result.get("agents_completed"))
    print("Nodes Visited (metadata):", (
        result.get("state", {})
        .get("metadata", {})
        .get("nodes_visited", [])
    ))

    if result.get("state"):
        decision = result["state"].get("supervisor_decision") or {}
        print("\nFinal Supervisor Decision:")
        print(f"  next_agents:  {decision.get('next_agents')}")
        print(f"  is_done:      {decision.get('is_done')}")
        print(f"  priority:     {decision.get('priority')}")
        print(f"  reasoning:    {decision.get('reasoning', '')[:120]}")
