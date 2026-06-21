import json
import uuid
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from loguru import logger
from sqlalchemy.orm import Session

from database.models import (
    Disaster,
    DisasterType,
    SeverityLevel,
    Resource,
    ResourceType,
    ResourceStatus,
    Shelter,
    SimulationRun,
)

# Deterministic resource allocation rules based on disaster type and severity
ALLOCATION_RULES = {
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

# Standard coordinates presets for simulated grids
GRID_COORDS = {
    "Flood": {"latitude": 26.1445, "longitude": 91.7362, "location": "Guwahati, India"},
    "Cyclone": {"latitude": 19.0760, "longitude": 72.8777, "location": "Mumbai, India"},
    "Earthquake": {"latitude": 18.5204, "longitude": 73.8567, "location": "Pune, India"},
}

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes the great-circle distance between two GPS coordinates."""
    R = 6371.0  # Earth's radius in kilometers
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def run_simulation(
    db: Session,
    simulation_type: str,
    rainfall_change_pct: float,
    wind_speed_change_pct: float,
    population_change_pct: float,
    shelter_capacity_change_pct: float,
    resource_availability_change_pct: float,
    disaster_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for running the Digital Twin What-If Simulation.
    Fetches current DB state, applies delta multipliers, maps future metrics,
    persists a SimulationRun row, and returns comparative outputs.
    """
    logger.info(f"🔮 Initializing Digital Twin simulation for: {simulation_type} | Rain={rainfall_change_pct}%, Wind={wind_speed_change_pct}%, Pop={population_change_pct}%")
    
    # 1. Resolve simulation coordinates and baseline population
    baseline_pop = 50000
    latitude = GRID_COORDS.get(simulation_type, {}).get("latitude", 20.0)
    longitude = GRID_COORDS.get(simulation_type, {}).get("longitude", 80.0)
    location_label = GRID_COORDS.get(simulation_type, {}).get("location", "Central Sector")
    current_severity = "Low"
    
    db_disaster = None
    if disaster_id:
        try:
            dis_uuid = uuid.UUID(disaster_id)
            db_disaster = db.query(Disaster).filter(Disaster.id == dis_uuid).first()
        except Exception as e:
            logger.warning(f"Could not parse disaster_id: {e}")
            
    if not db_disaster:
        # Fallback to latest active disaster of matching type
        db_disaster = db.query(Disaster).filter(
            Disaster.disaster_type == DisasterType(simulation_type),
            Disaster.status == "Active"
        ).order_by(Disaster.created_at.desc()).first()

    if db_disaster:
        baseline_pop = db_disaster.affected_population or baseline_pop
        latitude = db_disaster.latitude
        longitude = db_disaster.longitude
        location_label = db_disaster.title
        current_severity = db_disaster.severity.value

    # 2. Apply delta updates to population
    predicted_population = int(baseline_pop * (1.0 + population_change_pct / 100.0))
    predicted_population = max(0, predicted_population)

    # 3. Trigger simulation sub-routines based on type
    if simulation_type == "Flood":
        sim_metrics = simulate_flood(rainfall_change_pct, wind_speed_change_pct)
    elif simulation_type == "Cyclone":
        sim_metrics = simulate_cyclone(rainfall_change_pct, wind_speed_change_pct)
    else:
        sim_metrics = simulate_earthquake(rainfall_change_pct, wind_speed_change_pct)

    # 4. Calculate predicted severity
    severity_results = calculate_future_severity(
        simulation_type=simulation_type,
        predicted_population=predicted_population,
        sim_metrics=sim_metrics,
        resource_availability_change_pct=resource_availability_change_pct
    )
    predicted_severity = severity_results["severity_level"]
    predicted_score = severity_results["severity_score"]

    # 5. Calculate future resource needs and gaps
    resource_needs = calculate_future_resource_needs(
        db=db,
        simulation_type=simulation_type,
        predicted_severity=predicted_severity,
        resource_availability_change_pct=resource_availability_change_pct
    )

    # 6. Calculate shelter requirements and gaps
    shelter_needs = calculate_future_shelter_requirements(
        db=db,
        latitude=latitude,
        longitude=longitude,
        predicted_population=predicted_population,
        shelter_capacity_change_pct=shelter_capacity_change_pct
    )

    # Compile result summary payload
    summary_data = {
        "simulation_type": simulation_type,
        "location": location_label,
        "coordinates": {"latitude": latitude, "longitude": longitude},
        "inputs": {
            "rainfall_change_pct": rainfall_change_pct,
            "wind_speed_change_pct": wind_speed_change_pct,
            "population_change_pct": population_change_pct,
            "shelter_capacity_change_pct": shelter_capacity_change_pct,
            "resource_availability_change_pct": resource_availability_change_pct
        },
        "baseline": {
            "affected_population": baseline_pop,
            "severity": current_severity
        },
        "predicted": {
            "affected_population": predicted_population,
            "severity_level": predicted_severity,
            "severity_score": predicted_score,
            "breakdown": severity_results["breakdown"]
        },
        "resource_metrics": resource_needs,
        "shelter_metrics": shelter_needs
    }

    # 7. Persist simulation run details to PostgreSQL
    sim_run = SimulationRun(
        scenario_name=f"What-If Simulation ({simulation_type}) at {location_label[:40]}",
        rainfall_change=rainfall_change_pct,
        wind_speed_change=wind_speed_change_pct,
        population_change=int(predicted_population - baseline_pop),
        predicted_severity=SeverityLevel(predicted_severity),
        result_summary=json.dumps(summary_data)
    )
    
    try:
        db.add(sim_run)
        db.commit()
        db.refresh(sim_run)
        logger.info(f"✅ Simulation successfully recorded in DB. ID: {sim_run.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to persist simulation details: {e}")

    return {
        "id": str(sim_run.id),
        "scenario_name": sim_run.scenario_name,
        "created_at": sim_run.created_at.isoformat() if sim_run.created_at else datetime.now().isoformat(),
        "summary": summary_data
    }

def simulate_flood(rainfall_change_pct: float, wind_speed_change_pct: float) -> Dict[str, float]:
    """Generates simulated rainfall and metrics for floods."""
    baseline_rain = 35.0  # mm/hr baseline
    baseline_wind = 12.0  # km/h baseline
    
    sim_rain = max(0.0, baseline_rain * (1.0 + rainfall_change_pct / 100.0))
    sim_wind = max(0.0, baseline_wind * (1.0 + wind_speed_change_pct / 100.0))
    
    return {
        "rainfall_mm": sim_rain,
        "wind_speed_kmh": sim_wind,
        "magnitude_indicator": min(100.0, 40.0 * (1.0 + rainfall_change_pct / 100.0))
    }

def simulate_cyclone(rainfall_change_pct: float, wind_speed_change_pct: float) -> Dict[str, float]:
    """Generates simulated wind and metrics for cyclones."""
    baseline_rain = 15.0  # mm/hr baseline
    baseline_wind = 85.0  # km/h baseline
    
    sim_rain = max(0.0, baseline_rain * (1.0 + rainfall_change_pct / 100.0))
    sim_wind = max(0.0, baseline_wind * (1.0 + wind_speed_change_pct / 100.0))
    
    return {
        "rainfall_mm": sim_rain,
        "wind_speed_kmh": sim_wind,
        "magnitude_indicator": min(100.0, 70.0 * (1.0 + wind_speed_change_pct / 100.0))
    }

def simulate_earthquake(rainfall_change_pct: float, wind_speed_change_pct: float) -> Dict[str, float]:
    """Generates simulated tectonic indicators for earthquakes (wind speed change doubles as seismic intensity)."""
    baseline_mag = 5.8  # Richter scale baseline
    
    # Map wind slider as generic force multiplier (up to +/- 50%)
    multiplier = 1.0 + (wind_speed_change_pct / 100.0)
    sim_mag = max(3.0, min(9.5, baseline_mag * multiplier))
    
    # Translate to 0-100 magnitude score
    magnitude_indicator = min(100.0, (sim_mag / 9.0) * 100.0)
    
    return {
        "rainfall_mm": 0.0,
        "wind_speed_kmh": 0.0,
        "seismic_magnitude": sim_mag,
        "magnitude_indicator": magnitude_indicator
    }

def calculate_future_severity(
    simulation_type: str,
    predicted_population: int,
    sim_metrics: Dict[str, float],
    resource_availability_change_pct: float
) -> Dict[str, Any]:
    """Calculates predicted severity score and level based on delta parameters."""
    
    # 1. Population Impact Score (scaled so that 200,000 affected population is 100%)
    pop_score = min(100.0, (predicted_population / 200000.0) * 100.0)
    
    # 2. Weather Risk Score
    rain = sim_metrics.get("rainfall_mm", 0.0)
    wind = sim_metrics.get("wind_speed_kmh", 0.0)
    
    if simulation_type == "Flood":
        if rain >= 50.0: weather_score = 100.0
        elif rain >= 20.0: weather_score = 70.0
        elif rain >= 5.0: weather_score = 40.0
        elif rain > 0.0: weather_score = 15.0
        else: weather_score = 0.0
    elif simulation_type == "Cyclone":
        if wind >= 120.0: weather_score = 100.0
        elif wind >= 80.0: weather_score = 70.0
        elif wind >= 40.0: weather_score = 40.0
        elif wind >= 20.0: weather_score = 15.0
        else: weather_score = 0.0
    else:
        weather_score = 10.0  # minimal weather influence on earthquakes
        
    # 3. Magnitude Score
    mag_score = sim_metrics.get("magnitude_indicator", 50.0)
    
    # 4. Resource Stress Score
    res_stress_score = min(100.0, max(0.0, 45.0 * (1.0 - resource_availability_change_pct / 100.0)))

    # Compute final weighted score
    weighted_score = (
        0.40 * pop_score +
        0.25 * weather_score +
        0.20 * mag_score +
        0.15 * res_stress_score
    )
    weighted_score = round(min(100.0, max(0.0, weighted_score)), 2)

    # Determine Severity Level
    if weighted_score <= 25.0:
        level = "Low"
    elif weighted_score <= 50.0:
        level = "Medium"
    elif weighted_score <= 75.0:
        level = "High"
    else:
        level = "Critical"

    return {
        "severity_level": level,
        "severity_score": weighted_score,
        "breakdown": {
            "population_impact_score": round(pop_score, 2),
            "weather_risk_score": round(weather_score, 2),
            "disaster_magnitude_score": round(mag_score, 2),
            "resource_stress_score": round(res_stress_score, 2)
        }
    }

def calculate_future_resource_needs(
    db: Session,
    simulation_type: str,
    predicted_severity: str,
    resource_availability_change_pct: float
) -> Dict[str, Any]:
    """Calculates future resource requirements, live inventory pools, and gaps."""
    # Lookup rules
    type_rules = ALLOCATION_RULES.get(simulation_type, {})
    required_needs = type_rules.get(predicted_severity, {})
    
    gaps = {}
    predicted_available = {}
    requirements = {}
    
    # Fetch live resources from DB to count available pools
    for r_name, req_qty in required_needs.items():
        requirements[r_name] = req_qty
        
        # Map readable name to enum type
        r_type_val = ResourceType.BOAT
        if r_name == "Ambulance": r_type_val = ResourceType.AMBULANCE
        elif r_name == "Medical Team": r_type_val = ResourceType.MEDICAL_TEAM
        elif r_name == "Rescue Team": r_type_val = ResourceType.RESCUE_TEAM
        elif r_name == "NDRF Unit": r_type_val = ResourceType.NDRF_UNIT
        elif r_name == "Helicopter": r_type_val = ResourceType.HELICOPTER
        elif r_name == "Food Truck": r_type_val = ResourceType.FOOD_TRUCK

        # Query quantity available in database
        db_qty = sum(r.quantity for r in db.query(Resource).filter(
            Resource.resource_type == r_type_val,
            Resource.status == ResourceStatus.AVAILABLE
        ).all())
        
        # Scale available pool based on availability changes
        scaled_available = max(0, int(db_qty * (1.0 + resource_availability_change_pct / 100.0)))
        predicted_available[r_name] = scaled_available
        
        # Determine gap
        gap = max(0, req_qty - scaled_available)
        gaps[r_name] = gap
        
    return {
        "required": requirements,
        "simulated_available": predicted_available,
        "gap": gaps,
        "total_gap_units": sum(gaps.values())
    }

def calculate_future_shelter_requirements(
    db: Session,
    latitude: float,
    longitude: float,
    predicted_population: int,
    shelter_capacity_change_pct: float
) -> Dict[str, Any]:
    """Calculates capacity changes across shelters and returns overflow gaps."""
    
    # Fetch shelters with some vacant capacity or all shelters near zone
    db_shelters = db.query(Shelter).all()
    
    # Sort shelters by haversine distance
    shelter_distances = []
    for s in db_shelters:
        dist = _haversine_km(latitude, longitude, s.latitude, s.longitude)
        shelter_distances.append((s, dist))
    shelter_distances.sort(key=lambda x: x[1])
    
    assignments = []
    remaining_evacuees = predicted_population
    total_simulated_capacity = 0
    total_occupied = 0
    
    for shelter, dist in shelter_distances:
        # Scale capacity by slider delta
        sim_capacity = max(0, int(shelter.capacity * (1.0 + shelter_capacity_change_pct / 100.0)))
        total_simulated_capacity += sim_capacity
        total_occupied += shelter.occupied
        
        vacant_slots = max(0, sim_capacity - shelter.occupied)
        
        assigned_qty = min(remaining_evacuees, vacant_slots)
        if assigned_qty > 0:
            assignments.append({
                "shelter_name": shelter.name,
                "distance_km": round(dist, 1),
                "assigned_people": assigned_qty,
                "simulated_capacity": sim_capacity,
                "new_occupancy_pct": round(((shelter.occupied + assigned_qty) / max(1, sim_capacity)) * 100, 1)
            })
            remaining_evacuees -= assigned_qty
            
    # Calculate overall deficit / overflow
    unassigned = max(0, remaining_evacuees)
    
    return {
        "affected_population": predicted_population,
        "assigned_population": predicted_population - unassigned,
        "unassigned_population": unassigned,
        "total_simulated_capacity": total_simulated_capacity,
        "total_occupied_slots": total_occupied,
        "shelter_assignments": assignments
    }
