import os
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger
from sqlalchemy.orm import Session
import google.generativeai as genai

from database.models import (
    Disaster,
    DisasterStatus,
    Resource,
    ResourceAllocation,
    AllocationStatus,
    Shelter,
    Alert,
    SimulationRun,
)

# ---------------------------------------------------------------------------
# Gemini Configuration & Fallback Detection
# ---------------------------------------------------------------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
model_initialized = False

if GOOGLE_API_KEY and GOOGLE_API_KEY != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=GOOGLE_API_KEY)
        model_initialized = True
        logger.info("✅ Gemini AI model configured successfully for ADCC.")
    except Exception as e:
        logger.error(f"❌ Failed to configure Gemini AI: {e}. Falling back to rule-based mock engine.")
else:
    logger.warning("⚠️ GOOGLE_API_KEY missing or placeholder. Running command center in Rule-Based Mock Fallback mode.")

# ---------------------------------------------------------------------------
# System Context Compiler
# ---------------------------------------------------------------------------
def compile_system_context(db: Session) -> str:
    """
    Compiles all active database tables (disasters, alerts, allocations, shelters, resources, simulations)
    into a structured Markdown representation to serve as contextual RAG facts for Gemini.
    """
    logger.debug("[AI Command Center] Compiling database context for LLM...")
    
    # 1. Fetch active disasters
    active_disasters = db.query(Disaster).filter(Disaster.status == DisasterStatus.ACTIVE).all()
    disaster_text = "### 🚨 ACTIVE DISASTER HAZARDS\n"
    if not active_disasters:
        disaster_text += "- No active disasters currently reported in the geo grid.\n"
    for d in active_disasters:
        disaster_text += (
            f"- **Title:** {d.title}\n"
            f"  - ID: {d.id}\n"
            f"  - Type: {d.disaster_type.value}\n"
            f"  - Severity Level: {d.severity.value}\n"
            f"  - Affected Population: {d.affected_population or 0}\n"
            f"  - Location: ({d.latitude}, {d.longitude})\n"
            f"  - Verification: {d.verification_status.value} (Confidence: {int((d.confidence_score or 0) * 100)}%)\n"
            f"  - Source: {d.source or 'N/A'}\n"
        )

    # 2. Fetch active allocations
    active_allocs = db.query(ResourceAllocation).filter(ResourceAllocation.status == AllocationStatus.ACTIVE).all()
    alloc_text = "### 🚁 ACTIVE RESOURCE DEPLOYMENTS\n"
    if not active_allocs:
        alloc_text += "- No physical resources currently allocated.\n"
    for a in active_allocs:
        disaster_name = a.disaster.title if a.disaster else "Unknown Disaster"
        res_name = a.resource.resource_name if a.resource else "Generic Resource"
        res_type = a.resource.resource_type.value if a.resource else "N/A"
        alloc_text += (
            f"- **Deployed:** {a.quantity} x {res_name} ({res_type}) to {disaster_name}\n"
            f"  - Purpose: {a.allocation_reason or 'No log details'}\n"
            f"  - Timestamp: {a.allocated_at.isoformat()}\n"
        )

    # 3. Fetch shelters capacity
    shelters = db.query(Shelter).all()
    shelter_text = "### ⛺ EMERGENCY SHELTERS STATUS\n"
    if not shelters:
        shelter_text += "- No shelter records registered in database.\n"
    for s in shelters:
        vacant = max(0, s.capacity - s.occupied)
        occupancy_pct = (s.occupied / max(1, s.capacity)) * 100
        shelter_text += (
            f"- **Shelter:** {s.name} ({s.city})\n"
            f"  - Capacity: {s.capacity} slots | Occupied: {s.occupied} slots ({occupancy_pct:.1f}% occupied)\n"
            f"  - Vacant Slots Available: {vacant}\n"
            f"  - Location: ({s.latitude}, {s.longitude})\n"
        )

    # 4. Fetch available logistics pool
    resources = db.query(Resource).all()
    res_text = "### 📦 RESPONDERS DEPOT INVENTORY\n"
    available_counts: Dict[str, int] = {}
    for r in resources:
        r_type = r.resource_type.value
        if r.status == ResourceStatus.AVAILABLE:
            available_counts[r_type] = available_counts.get(r_type, 0) + r.quantity
    
    if not available_counts:
        res_text += "- No resources are currently available in the central depot.\n"
    else:
        for r_type, qty in available_counts.items():
            res_text += f"- **{r_type}:** {qty} units available for dispatch.\n"

    # 5. Fetch recent alerts
    recent_alerts = db.query(Alert).order_by(Alert.created_at.desc()).limit(5).all()
    alert_text = "### ⚠️ CRITICAL TELEMETRY ALERTS (RECENT)\n"
    if not recent_alerts:
        alert_text += "- No anomalous alerts received.\n"
    for al in recent_alerts:
        alert_text += f"- [{al.severity.value}] **{al.title}:** {al.message} (Source: {al.source or 'Sensors'})\n"

    # 6. Fetch recent simulations
    recent_sims = db.query(SimulationRun).order_by(SimulationRun.created_at.desc()).limit(3).all()
    sim_text = "### 🔮 DIGITAL TWIN SIMULATIONS (WHAT-IF SCENARIOS)\n"
    if not recent_sims:
        sim_text += "- No recent simulation run history registered.\n"
    for sim in recent_sims:
        sim_text += (
            f"- **Scenario:** {sim.scenario_name}\n"
            f"  - Inputs: Rainfall={sim.rainfall_change or 0}mm, Wind={sim.wind_speed_change or 0}km/h, Pop={sim.population_change or 0}\n"
            f"  - Predicted Severity: {sim.predicted_severity.value if sim.predicted_severity else 'N/A'}\n"
        )

    full_context = (
        f"OPERATIONAL DATABASE CONTEXT - TIMESTAMP: {datetime.now().isoformat()}\n"
        "==========================================================\n"
        f"{disaster_text}\n"
        f"{alloc_text}\n"
        f"{shelter_text}\n"
        f"{res_text}\n"
        f"{alert_text}\n"
        f"{sim_text}\n"
    )
    return full_context

# ---------------------------------------------------------------------------
# Core Gemini Invocations & Rule-Based Mock Fallback Responses
# ---------------------------------------------------------------------------
SYSTEM_INSTRUCTION = """
You are Antigravity, the AI Cognitive Director of the Autonomous Disaster Command Center (ADCC).
You have access to real-time operations database logs, multi-agent state node logs, and What-If simulation records.

Your task is to provide emergency managers with clear, concise, actionable, and analytical responses.
Format your responses beautifully in Markdown using appropriate emojis, headings, bullet lists, and highlight boxes.
Maintain a professional, military/NASA mission control-like authority tone.
Answer ONLY using the provided Operational Database Context. If the context has no disasters, report system nominal.
"""

def generate_mock_response(query: str, db: Session) -> str:
    """Generates analytical fallback responses if Gemini is offline/unauthenticated."""
    logger.debug("[RuleEngine] Generating analytical fallback response...")
    
    # Query database basics to make it context-aware
    disasters = db.query(Disaster).filter(Disaster.status == DisasterStatus.ACTIVE).all()
    allocs = db.query(ResourceAllocation).filter(ResourceAllocation.status == AllocationStatus.ACTIVE).all()
    shelters = db.query(Shelter).all()
    alerts = db.query(Alert).all()
    sims = db.query(SimulationRun).all()

    query_l = query.lower()

    # Calculate actual buffer stock counts from database dynamically
    resources = db.query(Resource).all()
    total_resources_count = len(resources)
    available_resources_count = sum(r.quantity for r in resources if r.status == ResourceStatus.AVAILABLE)
    
    boats_total = sum(r.quantity for r in resources if r.resource_type == ResourceType.BOAT)
    boats_busy = sum(r.quantity for r in resources if r.resource_type == ResourceType.BOAT and r.status == ResourceStatus.BUSY)
    boats_avail = max(0, boats_total - boats_busy)
    boats_pct = int(round((boats_busy / max(1, boats_total)) * 100)) if boats_total > 0 else 0
    
    amb_total = sum(r.quantity for r in resources if r.resource_type == ResourceType.AMBULANCE)
    amb_busy = sum(r.quantity for r in resources if r.resource_type == ResourceType.AMBULANCE and r.status == ResourceStatus.BUSY)
    amb_avail = max(0, amb_total - amb_busy)
    amb_pct = int(round((amb_busy / max(1, amb_total)) * 100)) if amb_total > 0 else 0
    
    ndrf_total = sum(r.quantity for r in resources if r.resource_type == ResourceType.NDRF_UNIT)
    ndrf_busy = sum(r.quantity for r in resources if r.resource_type == ResourceType.NDRF_UNIT and r.status == ResourceStatus.BUSY)
    ndrf_avail = max(0, ndrf_total - ndrf_busy)
    ndrf_pct = int(round((ndrf_busy / max(1, ndrf_total)) * 100)) if ndrf_total > 0 else 0

    if "happen" in query_l or "situation" in query_l or "monitoring" in query_l:
        # Situation Summary
        if not disasters:
            return (
                "### 🛰️ ADCC STATUS REPORT: SYSTEM NOMINAL\n\n"
                "> **Alert Level:** GREEN (No active outbreaks)\n\n"
                "* **Status:** Satellite networks and seismometer lines are normal.\n"
                "* **Depots:** Central logistics depots report full readiness.\n"
                "* **Recommendation:** Standby mode active. Continuous meteorological feed listening."
            )
        
        d_summaries = []
        for d in disasters:
            d_summaries.append(
                f"* **{d.title}** ({d.disaster_type.value})\n"
                f"  * **Severity:** `{d.severity.value}` | **Evacuees:** {d.affected_population or 0}\n"
                f"  * **Location:** ({d.latitude:.4f}, {d.longitude:.4f})\n"
                f"  * **Verification:** {d.verification_status.value} (Confidence: {int((d.confidence_score or 0) * 100)}%)"
            )
        d_list = "\n".join(d_summaries)
        
        return (
            "### 🛰️ ADCC TACTICAL SITUATION SUMMARY\n\n"
            f"Currently monitoring **{len(disasters)} active hazard sectors**:\n\n"
            f"{d_list}\n\n"
            "#### 📋 Active Allocations\n"
            f"A total of **{len(allocs)} response deployments** are active. Relief corridors are established."
        )

    elif "severity" in query_l or "critical" in query_l or "why" in query_l:
        # Explain Severity
        if not disasters:
            return "### ⚖️ SEVERITY ASSESSMENT: NOMINAL\nNo active disasters are logged. Severity score is 0.0."
        
        d = disasters[0]
        return (
            f"### ⚖️ SEVERITY DIAGNOSTICS: {d.title.upper()}\n\n"
            f"* **Current Severity Rating:** `{d.severity.value}`\n"
            f"* **Confidence Consensus Score:** `{int((d.confidence_score or 0.1) * 100)}%` ({d.verification_status.value})\n\n"
            "#### 🔍 Key Stress Factors:\n"
            f"1. **Population Exposure:** ~{d.affected_population or 1000} citizens located in the warning grid.\n"
            f"2. **Weather Risk:** Rainfall/wind parameters evaluated for coordinates ({d.latitude:.4f}, {d.longitude:.4f}).\n"
            f"3. **Depot Strain:** Responders central depots are active. Available logistics buffer: {available_resources_count} units.\n\n"
            f"> **Assessment:** Verification agent verified event details from live sources. Severity category validated as {d.severity.value}."
        )

    elif "resource" in query_l or "allocat" in query_l or "deploy" in query_l:
        # Explain Allocations
        if not allocs:
            return (
                "### 🚁 LOGISTICS REGISTRY: STANDBY\n\n"
                "No resources have been deployed yet. Central depots report full relief buffer readiness.\n\n"
                f"#### Central Depot Availability:\n"
                f"* Boats: {boats_avail} available\n"
                f"* NDRF Units: {ndrf_avail} available\n"
                f"* Ambulances: {amb_avail} available"
            )
        
        alloc_list = []
        for a in allocs:
            res_name = a.resource.resource_name if a.resource else "Rescue Unit"
            dest = a.disaster.title if a.disaster else "Disaster Zone"
            alloc_list.append(f"* **{a.quantity}x {res_name}** deployed to {dest} (Reason: *{a.allocation_reason or 'Command override'}*)")
        alloc_text = "\n".join(alloc_list)
        
        return (
            "### 🚁 DISPATCH REGISTRY AND LOGISTICS STATUS\n\n"
            f"Central command registers **{len(allocs)} active relief allocations**:\n\n"
            f"{alloc_text}\n\n"
            "#### 📦 Buffer Stock Check:\n"
            f"* Boats: {boats_pct}% occupied ({boats_avail}/{boats_total} available)\n"
            f"* NDRF Units: {ndrf_pct}% occupied ({ndrf_avail}/{ndrf_total} available)\n"
            f"* Ambulances: {amb_pct}% occupied ({amb_avail}/{amb_total} available)"
        )

    elif "shelter" in query_l or "evacuat" in query_l or "capacity" in query_l:
        # Explain Shelters
        occupied_shelters = [s for s in shelters if s.occupied > 0]
        shelter_list = []
        for s in occupied_shelters:
            occupancy = (s.occupied / max(1, s.capacity)) * 100
            shelter_list.append(f"* **{s.name}** ({s.city}): `{s.occupied}/{s.capacity}` occupied ({occupancy:.1f}%)")
        shelter_text = "\n".join(shelter_list) if shelter_list else "* All registered shelters are currently vacant."
        
        total_slots = sum(s.capacity for s in shelters)
        occupied_slots = sum(s.occupied for s in shelters)
        vacant_slots = max(0, total_slots - occupied_slots)
        
        return (
            "### ⛺ EMERGENCY SHELTERS & EVACUATION SUMMARY\n\n"
            f"Command tracks shelter utilization metrics across active regions. Total vacant capacity: {vacant_slots} slots.\n\n"
            f"{shelter_text}\n\n"
            "#### 📡 Evacuation Routing:\n"
            "> Evacuation routes are computed using nearest-first greedy matching. Emergency transport standby active."
        )

    elif "do next" in query_l or "recommend" in query_l or "action" in query_l:
        # Action Recommendations
        if not disasters:
            return (
                "### 📋 ADCC TACTICAL ACTION PROTOCOLS\n\n"
                "System is nominal. No urgent disaster response operations are active.\n"
                "1. **Monitor feeds:** Maintain satellite and weather telemetry polling.\n"
                "2. **Depot maintenance:** Check responder status flags."
            )
        
        d = disasters[0]
        recs = []
        if d.disaster_type.value == "Flood":
            recs = [
                f"1. **🚨 Evacuate Low-Lying Grids:** Alert vulnerable populations in the {d.title} sector.",
                "2. **🚁 Water Rescue Dispatch:** Mobilize rubber boats and NDRF battalions.",
                "3. **⛺ Overflow Shelters:** Prepare temporary camps in safe surrounding locations."
            ]
        elif d.disaster_type.value == "Earthquake":
            recs = [
                f"1. **🚨 Search and Rescue:** Dispatch heavy rescue teams and dog squads to {d.title}.",
                "2. **🏥 Trauma Standby:** Alert closest hospital networks to clear beds.",
                "3. **⛺ Open Relief Centers:** Activate emergency camps to house displaced citizens."
            ]
        elif d.disaster_type.value == "Cyclone":
            recs = [
                f"1. **🚨 Storm Surge Warnings:** Broadcast warnings to coastal fishing hamlets.",
                "2. **⛺ Evacuate to Cyclone Shelters:** Assist residents in shifting to reinforced structures.",
                "3. **📦 Deploy Power & Comm Reserves:** Position emergency backup towers."
            ]
        else:
            recs = [
                f"1. **🚨 Deploy Responders:** Dispatch nearest available resources to {d.title}.",
                "2. **⛺ Shelter Management:** Route affected population to closest vacancies.",
                "3. **📡 Satellite Analysis:** Request high-resolution imagery passes."
            ]
            
        recs_text = "\n".join(recs)
        return (
            "### 📋 ADCC TACTICAL ACTION PROTOCOLS\n\n"
            "Based on multi-agent logs, the following operations are recommended:\n\n"
            f"{recs_text}\n\n"
            "> **Notification:** Status escalated to active response mode. Continuous tracking active."
        )

    elif "simulation" in query_l or "predicted" in query_l:
        # Simulation Summary
        if not sims:
            return "### 🔮 DIGITAL TWIN: IDLE\nNo simulations recorded in the database history."
        
        s = sims[0]
        
        deficit_text = "No resource deficit identified."
        if s.result_summary:
            try:
                sim_data = json.loads(s.result_summary)
                gaps = sim_data.get("resource_metrics", {}).get("gap", {})
                active_gaps = [f"{g_qty} {g_type}" for g_type, g_qty in gaps.items() if g_qty > 0]
                if active_gaps:
                    deficit_text = f"Projected resource deficit: **{', '.join(active_gaps)}**."
            except Exception:
                if "deficit" in s.result_summary.lower():
                    deficit_text = s.result_summary
        
        return (
            f"### 🔮 DIGITAL TWIN WHAT-IF ASSESSMENT: {s.scenario_name}\n\n"
            f"* **Inputs Applied:** Rainfall={s.rainfall_change or 0}mm, Wind/Seismic={s.wind_speed_change or 0}km/h, Pop={s.population_change or 0}\n"
            f"* **Predicted Severity Outcome:** `{s.predicted_severity.value if s.predicted_severity else 'High'}`\n\n"
            "#### 📉 Outbreak Gaps:\n"
            f"* **Shelter Corridors:** Evacuation routing warning thresholds active.\n"
            f"* **Depot Reserves:** {deficit_text}"
        )

    # General fallback
    return (
        "### 🛰️ COMMAND CENTER COGNITIVE LINK OPERATIONAL\n\n"
        f"I have parsed your query: *\"{query}\"*.\n\n"
        "Please ask specific questions about:\n"
        "1. Active disaster landscape (\"What is happening in the active sector?\")\n"
        "2. Resource allocations (\"How many boats have been deployed?\")\n"
        "3. Shelter capacity status (\"Show evacuation risks\")\n"
        "4. Scenario simulations (\"What happens if rainfall increases by 30%?\")"
    )

# ---------------------------------------------------------------------------
# Public Functions called by API endpoints
# ---------------------------------------------------------------------------
def query_gemini_model(prompt: str) -> str:
    """Invokes the Gemini API with system instructions and user prompt."""
    if not model_initialized:
        raise ValueError("Gemini is not initialized.")
        
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=SYSTEM_INSTRUCTION
    )
    
    response = model.generate_content(prompt)
    if not response or not response.text:
        raise ValueError("Empty response received from Gemini.")
        
    return response.text

def analyze_disaster(db: Session, query: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
    """Ask natural language questions about disasters and simulations using the LangChain Command Agent."""
    logger.info(f"[AI Command Center] Routing operator query through LangChain Agent: '{query}'")
    from agents.langchain_command_agent import run_langchain_agent
    try:
        return run_langchain_agent(db, query, conversation_history=conversation_history)
    except Exception as e:
        logger.error(f"LangChain Agent execution failed: {e}. Falling back to command center rule engine.")
        return generate_mock_response(query, db)


def summarize_current_situation(db: Session) -> str:
    """Summarizes active disasters and responses."""
    return analyze_disaster(db, "Give a comprehensive situation report of active disasters.")

def explain_severity(db: Session) -> str:
    """Explains severity assessment triggers."""
    return analyze_disaster(db, "Why is the current disaster level set to its rating? Explain the severity stress factors.")

def explain_resource_allocation(db: Session) -> str:
    """Explains logistics allocations and depot stress."""
    return analyze_disaster(db, "Detail what resources are allocated and explain why they were selected.")

def explain_shelter_plan(db: Session) -> str:
    """Explains shelter capacities and evacuee routing."""
    return analyze_disaster(db, "Show evacuation risks and explain shelter status.")

def generate_action_recommendations(db: Session) -> str:
    """Recommends urgent operator actions."""
    return analyze_disaster(db, "What should emergency operators do next? Provide action protocols.")
