"""
ADCC — Supervisor Agent
========================
The central orchestrator of the Autonomous Disaster Command Center.

Architecture Role:
    The Supervisor Agent is the ENTRY POINT and ROUTER of the entire system.
    Every other agent reports back to the Supervisor after completing its work.
    The Supervisor then Observes → Thinks → Decides → Acts.

Decision Strategy:
    1. Rule-Based Fast Path (primary):
       Deterministic routing rules cover 90% of scenarios without LLM latency.
    2. Gemini LLM Fallback (secondary):
       For ambiguous states, the Supervisor uses Gemini with structured output
       to reason about the situation and choose the best next agent(s).

Supported Agents (routing targets):
    - "collect_data"    → Data Collection Agent
    - "verification"    → Verification Agent
    - "severity"        → Severity Assessment Agent
    - "allocation"      → Resource Allocation Agent
    - "shelter"         → Shelter Assignment Agent
    - "route_planning"  → Route Planning Agent
    - "notification"    → Notification Agent
    - "replanning"      → Dynamic Replanning Agent
    - "__end__"         → Signals workflow completion

Iterative Loop (max 10 iterations):
    Observe current state → Think about what's missing → Decide next agent(s)
    → Act (route to agent) → Re-evaluate after agent completes

Position in Graph:
    START → supervisor ←──────────────────────────────────────┐
                ↓                                              │
         [route to agent(s)]                                   │
                ↓                                              │
          [agent executes]──────────────────────────────────── ┘
                                (loop until done or max iter)
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger
from pydantic import BaseModel, Field

from workflows.state import (
    DisasterState,
    StateUpdate,
    update_state_metadata,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "supervisor_agent"
MAX_ITERATIONS = 10
CONFIDENCE_THRESHOLD = 0.40   # Below this → request more data collection
HIGH_SEVERITY_THRESHOLD = 0.50  # Above this → trigger parallel allocation+shelter

# All valid routing targets (must match node names in graph.py)
VALID_AGENTS = {
    "collect_data",
    "verification",
    "severity",
    "allocation",
    "shelter",
    "route_planning",
    "notification",
    "replanning",
    "__end__",
}


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================

class SupervisorDecision(BaseModel):
    """
    Structured output from the Supervisor Agent after each evaluation.

    Attributes:
        next_agents:               Which agent(s) to invoke next. Multiple = parallel.
        reasoning:                 Chain-of-thought explanation for the decision.
        needs_more_data:           True if confidence is too low to act.
        confidence_threshold_met:  True if confidence_score >= CONFIDENCE_THRESHOLD.
        is_done:                   True if all required tasks are complete.
        priority:                  "low", "medium", "high", "critical"
        iteration:                 Which supervisor iteration this decision came from.
    """
    next_agents: list[str] = Field(
        ...,
        description="List of agent names to invoke next. Use ['__end__'] to terminate."
    )
    reasoning: str = Field(
        ...,
        description="Chain-of-thought explanation for why these agents were chosen."
    )
    needs_more_data: bool = Field(
        False,
        description="True if data confidence is too low — triggers re-collection."
    )
    confidence_threshold_met: bool = Field(
        False,
        description="True if confidence_score >= 0.40."
    )
    is_done: bool = Field(
        False,
        description="True when all required tasks are complete and workflow can end."
    )
    priority: str = Field(
        "medium",
        description="Situation priority: low, medium, high, critical."
    )
    iteration: int = Field(
        0,
        description="Supervisor loop iteration number."
    )


# ===========================================================================
# RULE-BASED FAST PATH
# ===========================================================================

def _rule_based_decision(state: DisasterState, iteration: int) -> Optional[SupervisorDecision]:
    """
    Deterministic routing rules that cover the majority of scenarios.
    Returns a SupervisorDecision if a rule matches, or None for LLM fallback.

    Rules are evaluated in priority order (most critical first).
    """
    completed_list = state.get("agents_completed") or []
    
    collect_count = sum(1 for a in completed_list if a == "collect_data")
    verify_count = sum(1 for a in completed_list if a == "verification")
    severity_count = sum(1 for a in completed_list if a == "severity")
    allocation_count = sum(1 for a in completed_list if a == "allocation")
    shelter_count = sum(1 for a in completed_list if a == "shelter")
    route_count = sum(1 for a in completed_list if a in ("route_planning", "route_planning_agent"))
    notification_count = sum(1 for a in completed_list if a in ("notification", "notification_agent"))
    replanning_count = sum(1 for a in completed_list if a == "replanning")

    confidence = state.get("confidence_score", 0.0)
    severity_score = state.get("severity_score", 0.0)
    severity_level = state.get("severity_level", "Low")
    has_weather = state.get("weather_data") is not None
    has_events = bool(state.get("disaster_events") or state.get("earthquake_events"))
    has_verified = bool(state.get("verified_reports"))
    notification_sent = state.get("notification_sent", False) or notification_count > 0
    new_events = state.get("new_events_detected", False)

    # ── RULE 0: Safety guard — too many iterations ──────────────────────────
    if iteration >= MAX_ITERATIONS:
        logger.warning(f"[Supervisor] MAX_ITERATIONS ({MAX_ITERATIONS}) reached. Forcing END.")
        return SupervisorDecision(
            next_agents=["__end__"],
            reasoning=f"Safety guard: maximum iteration limit ({MAX_ITERATIONS}) reached. Terminating.",
            is_done=True,
            iteration=iteration,
        )

    # ── RULE 1: No data yet — collect first ─────────────────────────────────
    if collect_count == 0:
        return SupervisorDecision(
            next_agents=["collect_data"],
            reasoning="Initial data collection (weather, GDACS alerts, USGS earthquakes, and resource stocks) must run first.",
            needs_more_data=True,
            confidence_threshold_met=False,
            iteration=iteration,
        )

    # ── RULE 2: New events mid-cycle — replan ───────────────────────────────
    if new_events and severity_count > 0 and replanning_count == 0:
        return SupervisorDecision(
            next_agents=["replanning"],
            reasoning=(
                "New disaster events detected mid-cycle. "
                "Existing plans may be outdated — triggering dynamic replanning."
            ),
            confidence_threshold_met=confidence >= CONFIDENCE_THRESHOLD,
            priority="high",
            iteration=iteration,
        )

    # ── RULE 3: Data collected but confidence too low — retry collection ────
    if has_events and confidence < CONFIDENCE_THRESHOLD and collect_count > 0 and verify_count == collect_count:
        # Only retry once
        if collect_count < 2:
            return SupervisorDecision(
                next_agents=["collect_data"],
                reasoning=(
                    f"Confidence score is {confidence:.2f} (below threshold {CONFIDENCE_THRESHOLD}). "
                    "Re-running data collection to obtain more reliable information."
                ),
                needs_more_data=True,
                confidence_threshold_met=False,
                iteration=iteration,
            )

    # ── RULE 4: Data ready but not verified ─────────────────────────────────
    if (has_weather or has_events) and verify_count < collect_count:
        return SupervisorDecision(
            next_agents=["verification"],
            reasoning="Data collected but not yet verified across sources. Running verification.",
            confidence_threshold_met=confidence >= CONFIDENCE_THRESHOLD,
            iteration=iteration,
        )

    # ── RULE 5: Verified but no severity assessment ──────────────────────────
    if (has_verified or verify_count > 0) and severity_count < verify_count:
        return SupervisorDecision(
            next_agents=["severity"],
            reasoning="Verification complete. Running severity assessment to quantify disaster impact.",
            confidence_threshold_met=confidence >= CONFIDENCE_THRESHOLD,
            iteration=iteration,
        )

    # ── RULE 6: Severity assessed — parallel allocation + shelter ───────────
    if severity_count > 0 and allocation_count < severity_count and shelter_count < severity_count:
        if severity_level in ("High", "Critical") or severity_score >= HIGH_SEVERITY_THRESHOLD:
            return SupervisorDecision(
                next_agents=["allocation", "shelter"],
                reasoning=(
                    f"Severity is {severity_level} (score={severity_score:.2f}). "
                    "Deploying allocation and shelter planning in parallel for maximum speed."
                ),
                confidence_threshold_met=True,
                priority="critical" if severity_level == "Critical" else "high",
                iteration=iteration,
            )
        else:
            # Low/Medium — sequential is fine
            return SupervisorDecision(
                next_agents=["allocation"],
                reasoning=(
                    f"Severity is {severity_level} (score={severity_score:.2f}). "
                    "Running resource allocation."
                ),
                confidence_threshold_met=confidence >= CONFIDENCE_THRESHOLD,
                priority="medium",
                iteration=iteration,
            )

    # ── RULE 7: Allocation done but no shelter yet ───────────────────────────
    if allocation_count >= severity_count and shelter_count < severity_count:
        return SupervisorDecision(
            next_agents=["shelter"],
            reasoning="Resource allocation complete. Running shelter assignment for affected population.",
            confidence_threshold_met=True,
            priority="high",
            iteration=iteration,
        )

    # ── RULE 8: Plans exist but no evacuation routes ─────────────────────────
    if allocation_count >= severity_count and shelter_count >= severity_count and route_count < severity_count:
        return SupervisorDecision(
            next_agents=["route_planning"],
            reasoning=(
                "Allocation and shelter plans are ready. "
                "Planning evacuation routes for safe population movement."
            ),
            confidence_threshold_met=True,
            priority="high",
            iteration=iteration,
        )

    # ── RULE 9: All plans ready — send notifications ─────────────────────────
    if allocation_count >= severity_count and shelter_count >= severity_count and route_count >= severity_count and notification_count < severity_count:
        return SupervisorDecision(
            next_agents=["notification"],
            reasoning=(
                "All response plans are finalized (allocation, shelter, routes). "
                "Dispatching emergency notifications to population and responders."
            ),
            confidence_threshold_met=True,
            priority=severity_level.lower(),
            iteration=iteration,
        )

    # ── RULE 10: Notifications sent — check replanning need ──────────────────
    if notification_count >= severity_count and new_events and replanning_count < severity_count:
        return SupervisorDecision(
            next_agents=["replanning"],
            reasoning=(
                "Notifications sent but new events detected. "
                "Running replanning to adapt to changed conditions."
            ),
            confidence_threshold_met=True,
            priority="high",
            iteration=iteration,
        )

    # ── RULE 11: All tasks complete ──────────────────────────────────────────
    all_core_done = (
        allocation_count >= severity_count and shelter_count >= severity_count and route_count >= severity_count
        and (notification_sent or notification_count >= severity_count)
        and (replanning_count >= severity_count or not new_events)
    )
    if all_core_done and severity_count > 0:
        return SupervisorDecision(
            next_agents=["__end__"],
            reasoning=(
                "All required tasks completed: data collected, verified, severity assessed, "
                "resources allocated, shelters assigned, routes planned, notifications sent. "
                "Workflow complete."
            ),
            confidence_threshold_met=True,
            is_done=True,
            priority=severity_level.lower(),
            iteration=iteration,
        )

    # No rule matched — fall through to LLM
    return None


# ===========================================================================
# LLM FALLBACK
# ===========================================================================

def _llm_decision(state: DisasterState, iteration: int) -> SupervisorDecision:
    """
    Uses Google Gemini via LangChain to make a routing decision for
    ambiguous states that don't match the rule-based fast path.

    Returns a SupervisorDecision with Gemini's reasoning.
    Falls back to safe default ('collect_data') on any LLM failure.
    """
    logger.info("[Supervisor] Rule-based path produced no match. Invoking Gemini LLM fallback...")

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment.")

        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",
            google_api_key=api_key,
            temperature=0.1,
        )

        # Build a concise state summary for the LLM prompt
        completed = list(state.get("agents_completed") or [])
        severity_level = state.get("severity_level", "Unknown")
        severity_score = state.get("severity_score", 0.0)
        confidence = state.get("confidence_score", 0.0)
        has_weather = state.get("weather_data") is not None
        has_events = bool(state.get("disaster_events") or state.get("earthquake_events"))
        has_verified = bool(state.get("verified_reports"))
        has_allocation = "allocation" in completed or state.get("allocation_plan") is not None
        has_shelter = "shelter" in completed or state.get("shelter_plan") is not None
        has_route = "route_planning" in completed or state.get("route_plan") is not None
        notification_sent = state.get("notification_sent", False)
        new_events = state.get("new_events_detected", False)

        state_summary = {
            "iteration": iteration,
            "agents_completed": completed,
            "confidence_score": round(confidence, 2),
            "severity_level": severity_level,
            "severity_score": round(severity_score, 2),
            "has_weather_data": has_weather,
            "has_disaster_events": has_events,
            "has_verified_reports": has_verified,
            "has_allocation_plan": has_allocation,
            "has_shelter_plan": has_shelter,
            "has_route_plan": has_route,
            "notification_sent": notification_sent,
            "new_events_detected": new_events,
        }

        system_prompt = """You are the Supervisor Agent for the ADCC (Autonomous Disaster Command Center).
Your task is to analyze the current disaster response state and decide which agent(s) to run next.

Available agents:
- "collect_data"   → Fetches weather, GDACS events, USGS earthquakes, resources
- "verification"   → Cross-checks data across multiple sources for confidence
- "severity"       → Calculates disaster severity score and level (Low/Medium/High/Critical)
- "allocation"     → Allocates physical resources (ambulances, boats, NDRF units)
- "shelter"        → Assigns affected population to shelter locations
- "route_planning" → Plans evacuation routes for safe population movement
- "notification"   → Sends SMS/WhatsApp/email alerts to responders and population
- "replanning"     → Dynamically updates plans when conditions change
- "__end__"        → Terminates the workflow (use ONLY when all tasks are done)

Rules:
1. Always start with collect_data if no data exists.
2. Run verification before severity assessment.
3. Run severity before allocation/shelter.
4. When severity is High or Critical, run allocation + shelter in PARALLEL (return both in next_agents).
5. Plan routes after allocation and shelter are done.
6. Send notifications only when all plans are finalized.
7. Trigger replanning when new events are detected.
8. Return ["__end__"] only when: allocation done + shelter done + routes done + notification sent.

Respond ONLY with valid JSON in this exact format:
{
  "next_agents": ["<agent_name>"],
  "reasoning": "<your chain-of-thought>",
  "needs_more_data": false,
  "confidence_threshold_met": true,
  "is_done": false,
  "priority": "high"
}"""

        human_prompt = f"""Current disaster response state:
{json.dumps(state_summary, indent=2)}

What agent(s) should run next? Respond with JSON only."""

        response = llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt),
        ])

        # Parse the JSON response
        response_text = response.content.strip()
        # Strip markdown code fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(
                line for line in lines
                if not line.startswith("```")
            ).strip()

        parsed = json.loads(response_text)

        # Validate next_agents against known agents
        raw_agents = parsed.get("next_agents", ["collect_data"])
        valid_next = [a for a in raw_agents if a in VALID_AGENTS]
        if not valid_next:
            valid_next = ["collect_data"]

        decision = SupervisorDecision(
            next_agents=valid_next,
            reasoning=parsed.get("reasoning", "LLM routing decision."),
            needs_more_data=parsed.get("needs_more_data", False),
            confidence_threshold_met=parsed.get("confidence_threshold_met", False),
            is_done=parsed.get("is_done", False),
            priority=parsed.get("priority", "medium"),
            iteration=iteration,
        )
        logger.info(f"[Supervisor] LLM decided: {decision.next_agents} | {decision.reasoning[:80]}...")
        return decision

    except Exception as e:
        logger.error(f"[Supervisor] LLM fallback failed: {e}. Defaulting to collect_data.")
        return SupervisorDecision(
            next_agents=["collect_data"],
            reasoning=f"LLM fallback failed ({e}). Defaulting to data collection as safe starting point.",
            needs_more_data=True,
            iteration=iteration,
        )


# ===========================================================================
# MAIN SUPERVISOR ENTRY POINT
# ===========================================================================

def run_supervisor(state: DisasterState) -> DisasterState:
    """
    Main Supervisor Agent function. Called by the LangGraph supervisor_node.

    Observe → Think → Decide → Act pipeline:
    1. Read current state (Observe)
    2. Try rule-based fast path (Think)
    3. Fall back to Gemini LLM if rules don't match (Think)
    4. Write SupervisorDecision back to state (Decide)
    5. LangGraph conditional edge reads decision and routes to next agent(s) (Act)

    Args:
        state: Current DisasterState from LangGraph

    Returns:
        Updated DisasterState with supervisor_decision, supervisor_iterations, next_agents
    """
    t_start = time.time()

    iteration = (state.get("supervisor_iterations") or 0) + 1
    logger.info(f"[Supervisor] ═══ Iteration {iteration}/{MAX_ITERATIONS} ═══")
    logger.info(f"[Supervisor] Agents completed so far: {state.get('agents_completed', [])}")
    logger.info(f"[Supervisor] Confidence: {state.get('confidence_score', 0.0):.2f} | "
                f"Severity: {state.get('severity_level', 'Unknown')}")

    # ── Step 1: Update metadata ──────────────────────────────────────────────
    state = update_state_metadata(state, AGENT_NAME)

    # ── Step 2: Rule-based fast path ────────────────────────────────────────
    decision = _rule_based_decision(state, iteration)

    # ── Step 3: LLM fallback if no rule matched ──────────────────────────────
    if decision is None:
        decision = _llm_decision(state, iteration)

    # ── Step 4: Log decision ─────────────────────────────────────────────────
    elapsed = round(time.time() - t_start, 2)
    logger.info(
        f"[Supervisor] Decision → {decision.next_agents} "
        f"| Priority: {decision.priority} "
        f"| Done: {decision.is_done} "
        f"| Took {elapsed}s"
    )
    logger.info(f"[Supervisor] Reasoning: {decision.reasoning}")

    # ── Step 5: Write decision back to state ─────────────────────────────────
    updated_state: DisasterState = {
        **state,
        "supervisor_decision":   decision.model_dump(),
        "supervisor_iterations": iteration,
        "next_agents":           decision.next_agents,
    }

    return update_state_metadata(
        updated_state,
        AGENT_NAME,
        data_source="SupervisorRules" if decision.reasoning.startswith("Safety") or
                     "rule" not in decision.reasoning.lower() else "SupervisorLLM",
    )


# ===========================================================================
# ROUTING HELPER (used in graph.py conditional edge)
# ===========================================================================

def supervisor_route(state: DisasterState) -> str | list[str]:
    """
    Reads the supervisor_decision from state and returns routing target(s).

    This function is registered as the LangGraph conditional edge function:
        builder.add_conditional_edges("supervisor", supervisor_route, {...})

    Returns:
        - A single string (e.g. "collect_data") for sequential routing
        - A list of strings (e.g. ["allocation", "shelter"]) for parallel fan-out
        - "__end__" to terminate the workflow

    Args:
        state: Current DisasterState

    Returns:
        str | list[str]: Next node name(s) or "__end__"
    """
    decision = state.get("supervisor_decision") or {}
    next_agents = decision.get("next_agents", [])

    if not next_agents or next_agents == ["__end__"]:
        logger.info("[Supervisor] Routing → END")
        return "__end__"

    if len(next_agents) == 1:
        target = next_agents[0]
        logger.info(f"[Supervisor] Routing → {target}")
        return target

    # Parallel fan-out
    logger.info(f"[Supervisor] Routing → PARALLEL {next_agents}")
    return next_agents


# ===========================================================================
# AGENT COMPLETION TRACKER
# ===========================================================================

def mark_agent_completed(state: DisasterState, agent_name: str) -> DisasterState:
    """
    Marks an agent as completed in the shared state.
    Call this at the END of every agent's node wrapper in nodes.py.

    Args:
        state:      Current DisasterState
        agent_name: Name of the agent that just completed (e.g. "collect_data")

    Returns:
        Updated DisasterState with agent_name appended to agents_completed
    """
    completed = list(state.get("agents_completed") or [])
    # Append even if already present — allows tracking retries
    completed.append(agent_name)
    logger.debug(f"[Supervisor] Marked '{agent_name}' as completed. Total: {completed}")
    return {**state, "agents_completed": completed}  # type: ignore[return-value]
