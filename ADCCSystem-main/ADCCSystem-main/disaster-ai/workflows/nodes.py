"""
ADCC — LangGraph Workflow Nodes
================================
Defines the LangGraph-compatible wrapper nodes that invoke the underlying
ADCC agents. These wrapper nodes maintain zero business logic duplication,
delegating all execution to the corresponding agent modules.

All nodes now call mark_agent_completed() from supervisor_agent so the
Supervisor can track which agents have run and make informed routing decisions.

Nodes:
    ── Core Agents (existing) ──
    1.  collect_data_node
    2.  verification_node
    3.  severity_node
    4.  allocation_node
    5.  shelter_node
    6.  replanning_node

    ── Supervisor & New Agents ──
    7.  supervisor_node
    8.  notification_node
    9.  route_planning_node
"""

from loguru import logger
from workflows.state import DisasterState

# ── Existing agent imports ──────────────────────────────────────────────────
from agents.data_collection_agent import collect_all_data
from agents.verification_agent import run_verification
from agents.severity_agent import run_severity_assessment
from agents.allocation_agent import run_resource_allocation
from agents.shelter_agent import run_shelter_assignment
from agents.replanning_agent import run_dynamic_replanning

# ── New agent imports ───────────────────────────────────────────────────────
from agents.supervisor_agent import run_supervisor, mark_agent_completed
from agents.notification_agent import run_notification
from agents.route_planning_agent import run_route_planning


# ===========================================================================
# SUPERVISOR NODE
# ===========================================================================

def supervisor_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Supervisor Agent.
    The Supervisor is the entry point and router — it is called after every
    agent completes and decides which agent(s) to invoke next.

    Uses rule-based fast path with Gemini LLM fallback for ambiguous states.
    """
    logger.info("[WorkflowNode] ══════ Entering Supervisor Node ══════")
    return run_supervisor(state)


# ===========================================================================
# EXISTING AGENT NODES (updated to call mark_agent_completed)
# ===========================================================================

def collect_data_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Data Collection Agent.
    Fetches weather, GDACS alerts, USGS earthquake events, and local resources.

    Coordinates are extracted from the input state (e.g. from state['latitude'],
    state['longitude'], or weather_data if pre-initialized) with safe default values
    for Mumbai, India.
    """
    logger.info("[WorkflowNode] ──→ Entering Data Collection Node")

    # Extract coordinate inputs from state or fallback to Mumbai default
    latitude       = state.get("latitude")       or 19.0760
    longitude      = state.get("longitude")      or 72.8777
    location_label = state.get("location_label") or "Mumbai"
    country        = state.get("country")        or "India"

    # Check if weather_data has latitude/longitude (in case it was set prior)
    weather = state.get("weather_data")
    if weather:
        latitude  = weather.get("latitude")  or latitude
        longitude = weather.get("longitude") or longitude

    result = collect_all_data(
        state,
        latitude=latitude,
        longitude=longitude,
        location_label=location_label,
        country=country,
    )

    return mark_agent_completed(result, "collect_data")


def verification_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Verification Agent.
    Cross-checks collected alerts against news sources and confidence score logic.
    """
    logger.info("[WorkflowNode] ──→ Entering Verification Node")
    result = run_verification(state)
    return mark_agent_completed(result, "verification")


def severity_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Severity Assessment Agent.
    Computes population impact, weather risk, magnitude, and resource stress levels.
    """
    logger.info("[WorkflowNode] ──→ Entering Severity Node")
    result = run_severity_assessment(state)
    return mark_agent_completed(result, "severity")


def allocation_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Resource Allocation Agent.
    Allocates available safety resources based on calculated severity and requirements.
    """
    logger.info("[WorkflowNode] ──→ Entering Resource Allocation Node")
    result = run_resource_allocation(state)
    return mark_agent_completed(result, "allocation")


def shelter_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Shelter Assignment Agent.
    Sequentially maps affected population to nearest shelters, managing overflow risk.
    """
    logger.info("[WorkflowNode] ──→ Entering Shelter Assignment Node")
    result = run_shelter_assignment(state)
    return mark_agent_completed(result, "shelter")


def replanning_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Dynamic Replanning Agent.
    Evaluates trigger conditions (rainfall, deficit, aftershock) and modifies plans.

    After replanning, clears the new_events_detected flag so the Supervisor
    does not trigger replanning again unnecessarily.
    """
    logger.info("[WorkflowNode] ──→ Entering Dynamic Replanning Node")
    result = run_dynamic_replanning(state)
    result = mark_agent_completed(result, "replanning")

    # Clear new_events flag after replanning to prevent infinite loops
    return {**result, "new_events_detected": False}  # type: ignore[return-value]


# ===========================================================================
# NEW AGENT NODES
# ===========================================================================

def notification_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Notification Agent.
    Dispatches SMS and WhatsApp emergency alerts via Twilio to emergency contacts.
    Invoked by the Supervisor when all response plans are finalized.
    """
    logger.info("[WorkflowNode] ──→ Entering Notification Node")
    # run_notification already calls mark_agent_completed internally
    return run_notification(state)


def route_planning_node(state: DisasterState) -> DisasterState:
    """
    LangGraph wrapper node for the Route Planning Agent.
    Computes primary and alternative evacuation routes from disaster zone to shelters.
    Invoked by the Supervisor after allocation and shelter plans are confirmed.
    """
    logger.info("[WorkflowNode] ──→ Entering Route Planning Node")
    # run_route_planning already calls mark_agent_completed internally
    return run_route_planning(state)
