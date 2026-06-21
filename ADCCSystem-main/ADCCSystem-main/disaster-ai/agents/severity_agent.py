"""
ADCC — Severity Assessment Agent
=================================
Calculates disaster severity scores deterministically based on four weighted factors:
    - Population Impact (40%)
    - Weather Risk (25%)
    - Disaster Magnitude (20%)
    - Resource Stress / Availability (15%)

Maps the score to one of four levels:
    - 0-25%   → Low
    - 26-50%  → Medium
    - 51-75%  → High
    - 76-100% → Critical

Position in Pipeline:
    [verification_agent]     ← populates verified_reports
         ↓
    [severity_agent]         ← THIS FILE
         ↓
    [allocation_agent]       (Phase 6)
"""

import time
from typing import Any, Optional
from loguru import logger
from pydantic import BaseModel, Field

from workflows.state import (
    DisasterState,
    StateUpdate,
    update_state_metadata,
    validate_state,
    set_severity,
)

# ---------------------------------------------------------------------------
# Constants & Thresholds
# ---------------------------------------------------------------------------

AGENT_NAME = "severity_agent"

# Weight allocations (sum to 1.0)
WEIGHT_POPULATION = 0.40
WEIGHT_WEATHER    = 0.25
WEIGHT_MAGNITUDE  = 0.20
WEIGHT_RESOURCES  = 0.15

# Severity levels mapping
SEVERITY_LOW      = "Low"
SEVERITY_MEDIUM   = "Medium"
SEVERITY_HIGH     = "High"
SEVERITY_CRITICAL = "Critical"


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================

class SeverityBreakdown(BaseModel):
    """Structured breakdown of the severity calculation."""
    population_impact_score: float = Field(..., description="Population impact score (0-100)")
    weather_risk_score: float = Field(..., description="Weather risk score (0-100)")
    disaster_magnitude_score: float = Field(..., description="Disaster magnitude score (0-100)")
    resource_stress_score: float = Field(..., description="Resource stress score (0-100)")
    weighted_total_score: float = Field(..., description="Final weighted score (0-100)")
    severity_level: str = Field(..., description="Low, Medium, High, or Critical")


# ===========================================================================
# FACTOR CALCULATORS
# ===========================================================================

def calculate_population_impact(state: DisasterState) -> float:
    """
    Calculates population impact score (0.0 to 100.0) based on verified events.
    Formula: min((max_affected_population / 1,000,000) * 100.0, 100.0)
    If population is missing, applies default values based on verified event type/severity.
    """
    verified_reports = state.get("verified_reports") or []
    if not verified_reports:
        logger.debug("[SeverityAgent] No verified reports found. Population impact score: 0.0")
        return 0.0

    # Build lookup of verified disaster titles
    verified_titles = {
        r.get("disaster_title") for r in verified_reports 
        if r.get("verification_result") in ("Verified", "High Confidence", "Medium Confidence", "Confirmed")
    }

    if not verified_titles:
        logger.debug("[SeverityAgent] No active/confirmed verified reports. Population impact score: 0.0")
        return 0.0

    max_population = 0
    has_verified_gdacs = False
    has_verified_eq = False
    max_eq_mag = 0.0

    # Look up population in raw GDACS events
    gdacs_events = state.get("disaster_events") or []
    for event in gdacs_events:
        title = event.get("title")
        if title in verified_titles:
            has_verified_gdacs = True
            affected = event.get("affected_population") or 0
            if affected > max_population:
                max_population = affected

    # Look up verified earthquakes
    eq_events = state.get("earthquake_events") or []
    for eq in eq_events:
        # Match by rough location place or title
        place = eq.get("place", "")
        mag = eq.get("magnitude", 0.0)
        title_with_mag = f"M{mag} Earthquake — {place}"
        if title_with_mag in verified_titles or any(place in vt for vt in verified_titles):
            has_verified_eq = True
            if mag > max_eq_mag:
                max_eq_mag = mag

    # Apply defaults if population count is not available
    if max_population == 0:
        if has_verified_gdacs:
            # Default to 100k affected for generic GDACS verified event
            max_population = 100000
            logger.info(f"[SeverityAgent] Verified GDACS event found without population. Defaulting to {max_population} affected.")
        elif has_verified_eq:
            # Estimate population impact based on magnitude
            if max_eq_mag >= 7.0:
                max_population = 500000
            elif max_eq_mag >= 6.0:
                max_population = 100000
            elif max_eq_mag >= 5.0:
                max_population = 20000
            else:
                max_population = 5000
            logger.info(f"[SeverityAgent] Verified M{max_eq_mag} earthquake found. Defaulting to {max_population} affected.")

    pop_score = min((max_population / 1000000.0) * 100.0, 100.0)
    logger.debug(f"[SeverityAgent] Calculated Population Impact: {pop_score:.2f} (Max Affected={max_population})")
    return round(pop_score, 2)


def calculate_weather_risk(state: DisasterState) -> float:
    """
    Calculates weather risk score (0.0 to 100.0) based on current weather and forecasts.
    Analyzes rainfall, wind speeds, temperature, and risk flags.
    """
    weather = state.get("weather_data")
    if not weather:
        logger.warning("[SeverityAgent] No weather data found in state. Weather risk score: 0.0")
        return 0.0

    # 1. Rainfall risk (Flood/Landslide)
    rain = weather.get("rainfall_mm", 0.0) or 0.0
    max_rain_fc = weather.get("max_rainfall_mm", 0.0) or 0.0
    
    if rain >= 50.0 or max_rain_fc >= 100.0:
        rain_score = 100.0
    elif rain >= 20.0 or max_rain_fc >= 50.0:
        rain_score = 70.0
    elif rain >= 5.0 or max_rain_fc >= 20.0:
        rain_score = 40.0
    elif rain > 0.0 or max_rain_fc > 0.0:
        rain_score = 15.0
    else:
        rain_score = 0.0

    # 2. Wind risk (Cyclone)
    wind = weather.get("wind_speed_kmh", 0.0) or 0.0
    max_wind_fc = weather.get("max_wind_kmh", 0.0) or 0.0
    
    if wind >= 120.0 or max_wind_fc >= 150.0:
        wind_score = 100.0
    elif wind >= 80.0 or max_wind_fc >= 100.0:
        wind_score = 70.0
    elif wind >= 40.0 or max_wind_fc >= 60.0:
        wind_score = 40.0
    elif wind >= 20.0 or max_wind_fc >= 30.0:
        wind_score = 15.0
    else:
        wind_score = 0.0

    # 3. Temperature risk (Heatwave/Wildfire context)
    temp = weather.get("temperature_c", 25.0) or 25.0
    if temp >= 45.0:
        temp_score = 100.0
    elif temp >= 40.0:
        temp_score = 70.0
    elif temp >= 35.0:
        temp_score = 30.0
    elif temp >= 30.0:
        temp_score = 10.0
    else:
        temp_score = 0.0

    # Max score of individual weather parameters
    weather_score = max(rain_score, wind_score, temp_score)

    # Elevate score if explicit risk flags are active
    if weather.get("flood_risk") or weather.get("cyclone_risk"):
        weather_score = max(weather_score, 70.0)
    
    # If both flags are set, push to maximum risk
    if weather.get("flood_risk") and weather.get("cyclone_risk"):
        weather_score = 100.0

    logger.debug(
        f"[SeverityAgent] Calculated Weather Risk: {weather_score:.2f} "
        f"(Rain={rain}mm Wind={wind}km/h Temp={temp}°C FloodRisk={weather.get('flood_risk')})"
    )
    return round(weather_score, 2)


def calculate_disaster_magnitude(state: DisasterState) -> float:
    """
    Calculates disaster physical magnitude score (0.0 to 100.0) across verified events.
    Red Alert / Mag >= 7.0   → 100.0
    Orange Alert / Mag >= 6.0 → 80.0
    Green Alert / Mag >= 5.0  → 60.0
    """
    verified_reports = state.get("verified_reports") or []
    if not verified_reports:
        logger.debug("[SeverityAgent] No verified reports found. Magnitude score: 0.0")
        return 0.0

    verified_titles = {
        r.get("disaster_title") for r in verified_reports 
        if r.get("verification_result") in ("Verified", "High Confidence", "Medium Confidence", "Confirmed")
    }

    if not verified_titles:
        logger.debug("[SeverityAgent] No active verified reports. Magnitude score: 0.0")
        return 0.0

    max_mag_score = 0.0

    # 1. GDACS event magnitude mapping
    gdacs_events = state.get("disaster_events") or []
    for event in gdacs_events:
        title = event.get("title")
        if title in verified_titles:
            alert = event.get("alert_level", "Green")
            score_map = {"Red": 100.0, "Orange": 70.0, "Green": 40.0}
            score = score_map.get(alert, 20.0)
            if score > max_mag_score:
                max_mag_score = score

    # 2. Earthquake magnitude mapping
    eq_events = state.get("earthquake_events") or []
    for eq in eq_events:
        place = eq.get("place", "")
        mag = eq.get("magnitude", 0.0)
        title_with_mag = f"M{mag} Earthquake — {place}"
        if title_with_mag in verified_titles or any(place in vt for vt in verified_titles):
            if mag >= 7.0:
                score = 100.0
            elif mag >= 6.0:
                score = 80.0
            elif mag >= 5.0:
                score = 60.0
            elif mag >= 4.0:
                score = 40.0
            else:
                score = 20.0
            if score > max_mag_score:
                max_mag_score = score

    logger.debug(f"[SeverityAgent] Calculated Disaster Magnitude Score: {max_mag_score:.2f}")
    return round(max_mag_score, 2)


def calculate_resource_stress(state: DisasterState) -> float:
    """
    Calculates resource stress score (0.0 to 100.0).
    Stress represents how scarce available physical response resources are.
    Stress = (1.0 - (available_resources / total_resources)) * 100
    If resource DB is empty or fails, defaults to 50.0 (moderate stress) to be safe.
    """
    resources = state.get("resources")
    if not resources:
        logger.warning("[SeverityAgent] No resource data in state. Defaulting to 50.0 resource stress.")
        return 50.0

    total = resources.get("total_resources", 0)
    available = resources.get("available_count", 0)

    if total <= 0:
        logger.warning("[SeverityAgent] Resource database count is 0. Defaulting to 50.0 resource stress.")
        return 50.0

    stress = (1.0 - (float(available) / float(total))) * 100.0

    # Add penalty context if specific critical resources are unavailable
    # e.g., if there are verified floods, and available boats = 0
    verified_reports = state.get("verified_reports") or []
    has_flood = any("flood" in r.get("disaster_title", "").lower() for r in verified_reports)
    has_cyclone = any("cyclone" in r.get("disaster_title", "").lower() for r in verified_reports)

    if has_flood and resources.get("boats_available", 0) == 0:
        stress = min(stress + 15.0, 100.0)
        logger.info("[SeverityAgent] Flood active but no boats available. Resource stress penalized (+15).")
    
    if (has_flood or has_cyclone) and resources.get("ndrf_units_available", 0) == 0:
        stress = min(stress + 10.0, 100.0)
        logger.info("[SeverityAgent] Flood/Cyclone active but no NDRF units available. Resource stress penalized (+10).")

    logger.debug(f"[SeverityAgent] Calculated Resource Stress: {stress:.2f} (Available={available}/{total})")
    return round(stress, 2)


# ===========================================================================
# SEVERITY COMBINER
# ===========================================================================

def calculate_severity(
    pop_impact: float,
    weather_risk: float,
    magnitude: float,
    resource_stress: float,
) -> tuple[float, str]:
    """
    Combines the four factors using weights and maps to human severity level.
    Weights: Pop (40%), Weather (25%), Magnitude (20%), Resources (15%)
    
    Returns:
        tuple[float, str]: (score 0.0-100.0, level label)
    """
    score = (
        (pop_impact * WEIGHT_POPULATION) +
        (weather_risk * WEIGHT_WEATHER) +
        (magnitude * WEIGHT_MAGNITUDE) +
        (resource_stress * WEIGHT_RESOURCES)
    )

    score = min(100.0, max(0.0, score))

    if score >= 76.0:
        level = SEVERITY_CRITICAL
    elif score >= 51.0:
        level = SEVERITY_HIGH
    elif score >= 26.0:
        level = SEVERITY_MEDIUM
    else:
        level = SEVERITY_LOW

    return round(score, 2), level


# ===========================================================================
# RECOMMENDATIONS GENERATOR
# ===========================================================================

def generate_recommendations(state: DisasterState, severity_level: str) -> list[str]:
    """
    Generates tailored actionable response recommendations based on:
        - Severity level (Critical, High, Medium, Low)
        - Disaster types of active verified reports.
    """
    verified_reports = state.get("verified_reports") or []
    
    if not verified_reports:
        return [
            "No confirmed disasters in the current session. Monitor incoming sensors.",
            "Maintain standard standby readiness for response teams."
        ]

    recs = []
    
    # Categorize verified disaster types
    disaster_types = set()
    for report in verified_reports:
        title = report.get("disaster_title", "").lower()
        if "flood" in title or "rain" in title:
            disaster_types.add("Flood")
        if "cyclone" in title or "storm" in title or "hurricane" in title:
            disaster_types.add("Cyclone")
        if "earthquake" in title or "seismic" in title:
            disaster_types.add("Earthquake")

    # Base level recommendations
    if severity_level == SEVERITY_CRITICAL:
        recs.append("Establish a localized Unified Command Post in the affected zone.")
        recs.append("Mobilize national-level disaster reserve funds immediately.")
    elif severity_level == SEVERITY_HIGH:
        recs.append("Place local Emergency Operations Centers (EOC) on 24/7 alert status.")
    elif severity_level == SEVERITY_MEDIUM:
        recs.append("Notify regional response units and verify logistics chains.")

    # Disaster type specific recommendations
    for dtype in disaster_types:
        if dtype == "Flood":
            if severity_level in (SEVERITY_CRITICAL, SEVERITY_HIGH):
                recs.append("Deploy NDRF Units for active swift-water rescue operations.")
                recs.append("Deploy inflatable rescue boats and life jackets to inundated grids.")
                recs.append("Activate emergency high-ground shelters and begin evacuations.")
                recs.append("Dispatch mobile medical teams and distribute clean drinking water and ORS packets.")
            else:
                recs.append("Monitor river basins, drainage networks, and dams for volume stress.")
                recs.append("Issue flood safety advisories and restrict entry to low-lying roads.")

        elif dtype == "Cyclone":
            if severity_level in (SEVERITY_CRITICAL, SEVERITY_HIGH):
                recs.append("Initiate mandatory evacuation of low-lying coastal zones.")
                recs.append("Open dedicated cyclone shelters stocked with dry rations and power backup.")
                recs.append("Deploy road clearance teams with chainsaws to restore access pathways.")
                recs.append("Suspend port operations and issue red alerts for all marine activities.")
            else:
                recs.append("Monitor storm trajectory and advise residents to secure loose roofs.")

        elif dtype == "Earthquake":
            if severity_level in (SEVERITY_CRITICAL, SEVERITY_HIGH):
                recs.append("Deploy specialized Search & Rescue (USAR) units for structural collapse rescue.")
                recs.append("Establish mobile field hospitals and coordinate with major trauma centers.")
                recs.append("Conduct rapid structural safety inspections of bridges, dams, and main highways.")
                recs.append("Set up outdoor temporary camps away from tall buildings for aftershock protection.")
            else:
                recs.append("Monitor local networks for significant aftershocks.")
                recs.append("Publish public advisories on earthquake safety and checking structural damage.")

    # Fallback default if no matching types found
    if not recs:
        if severity_level in (SEVERITY_CRITICAL, SEVERITY_HIGH):
            recs.extend([
                "Deploy emergency responders to the coordinates of the confirmed incident.",
                "Activate local emergency shelters and deploy regional medical units.",
                "Request additional resource support from adjacent districts."
            ])
        else:
            recs.extend([
                "Continue monitoring environmental sensors and news reports.",
                "Maintain standard standby readiness for response teams."
            ])

    return recs


# ===========================================================================
# STATE UPDATE & MASTER NODE
# ===========================================================================

def update_state(
    state: DisasterState,
    score: float,
    level: str,
    recommendations: list[str],
) -> DisasterState:
    """
    Updates the DisasterState with computed severity details.
    Normalizes the score to 0.0-1.0 range when saving to state.
    """
    # Normalize 0.0-1.0 for DisasterState compatibility
    normalized_score = round(score / 100.0, 4)
    
    # Use helper to set severity
    state = set_severity(
        state,
        score=normalized_score,
        level=level,
        confidence=state.get("confidence_score", 0.0),
    )

    # Set recommendations
    state = {
        **state,
        "recommendations": recommendations,
    }  # type: ignore[assignment]

    state = update_state_metadata(state, current_node=AGENT_NAME)
    return state


def run_severity_assessment(state: DisasterState) -> DisasterState:
    """
    Master severity assessment function — evaluates the state data
    and returns updated DisasterState.
    Designed to function as a node in the LangGraph workflow.

    Args:
        state: DisasterState (after verification_agent has run)

    Returns:
        DisasterState: Updated with severity_score, severity_level, and recommendations
    """
    logger.info(
        f"\n{'='*60}\n"
        f"[SeverityAgent] ⚖️ Starting Severity Assessment Node\n"
        f"  Session: {state.get('session_id')}\n"
        f"  Verified reports: {len(state.get('verified_reports') or [])}\n"
        f"{'='*60}"
    )
    t_start = time.monotonic()

    # 1. State Validation
    state = update_state_metadata(state, current_node=AGENT_NAME)
    is_valid, issues = validate_state(state)
    if not is_valid:
        for issue in issues:
            state = update_state_metadata(state, current_node=AGENT_NAME, warning=issue)

    # 2. Factor Computations
    pop_impact = calculate_population_impact(state)
    weather_risk = calculate_weather_risk(state)
    magnitude = calculate_disaster_magnitude(state)
    resource_stress = calculate_resource_stress(state)

    # 3. Overall Scoring
    score, level = calculate_severity(pop_impact, weather_risk, magnitude, resource_stress)
    
    # 4. Generate Recommendations
    recs = generate_recommendations(state, level)

    # 5. Update State
    state = update_state(state, score, level, recs)

    total_elapsed = round(time.monotonic() - t_start, 3)
    logger.success(
        f"[SeverityAgent] ✅ Assessment complete in {total_elapsed}s\n"
        f"  Severity Level : {level} ({score:.1f}/100)\n"
        f"  Pop Impact     : {pop_impact:.1f}\n"
        f"  Weather Risk   : {weather_risk:.1f}\n"
        f"  Magnitude Score: {magnitude:.1f}\n"
        f"  Resource Stress: {resource_stress:.1f}\n"
        f"  Recommendations: {len(recs)} generated\n"
    )

    return state


# ===========================================================================
# STANDALONE RUN
# ===========================================================================

if __name__ == "__main__":
    """
    Standalone test run of the Severity Assessment Agent.
    Usage:
        cd disaster-ai
        $env:PYTHONPATH="."; python agents/severity_agent.py
    """
    import json
    from workflows.state import create_initial_state, VerifiedReportState, WeatherStateData, ResourceStateData

    logger.info("[SeverityAgent] Standalone test starting...")

    # Build a mock state representing a high severity flood
    state = create_initial_state(environment="development")
    
    # Add weather data
    state["weather_data"] = WeatherStateData(
        rainfall_mm=45.0,
        max_rainfall_mm=95.0,
        temperature_c=27.5,
        wind_speed_kmh=20.0,
        flood_risk=True,
    )

    # Add mock resources (scarce)
    state["resources"] = ResourceStateData(
        total_resources=50,
        available_count=10,  # 80% stress
        boats_available=0,   # flood stress penalty
    )

    # Add verified reports
    state["verified_reports"] = [
        VerifiedReportState(
            disaster_title="Guwahati Brahmaputra River Flood",
            verification_result="Verified",
            consensus_confidence=0.96,
        )
    ]

    # Mock corresponding raw disaster event to supply population data (e.g. 600,000 affected)
    from workflows.state import GDACSEventState
    state["disaster_events"] = [
        GDACSEventState(
            title="Guwahati Brahmaputra River Flood",
            alert_level="Red",
            affected_population=600000,
        )
    ]

    # Run the assessment
    updated_state = run_severity_assessment(state)

    print("\n" + "="*60)
    print("STANDALONE SEVERITY ASSESSMENT RESULTS:")
    print("="*60)
    print(f"Severity Level : {updated_state.get('severity_level')}")
    print(f"Severity Score : {updated_state.get('severity_score')} (normalized 0.0-1.0)")
    print("\nRecommendations:")
    for r in updated_state.get("recommendations", []):
        print(f"  • {r}")
