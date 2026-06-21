# ADCC — Lightweight Demo Scenarios Helper
# ========================================

from typing import Optional, Dict, Any

DEMO_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "Mumbai Flood": {
        "title": "Mumbai Flood Inundation Warning",
        "disaster_type": "Flood",
        "latitude": 19.0760,
        "longitude": 72.8777,
        "default_severity": "High",
        "affected_population": 250000,
        "confidence_score": 0.95,
        "weather": {
            "rainfall_mm": 85.0,
            "wind_speed_kmh": 35.0,
            "temperature_c": 28.0,
            "humidity_percent": 90.0,
            "flood_risk": True,
            "cyclone_risk": False,
            "weather_description": "Simulated heavy monsoon downpour causing urban flash floods."
        }
    },
    "Gujarat Cyclone": {
        "title": "Gujarat Cyclone Landfall Alert",
        "disaster_type": "Cyclone",
        "latitude": 22.2587,
        "longitude": 71.1924,
        "default_severity": "Critical",
        "affected_population": 200000,
        "confidence_score": 0.96,
        "weather": {
            "rainfall_mm": 75.0,
            "wind_speed_kmh": 145.0,
            "temperature_c": 26.0,
            "humidity_percent": 92.0,
            "flood_risk": True,
            "cyclone_risk": True,
            "weather_description": "Simulated cyclonic landfall with severe wind surges."
        }
    },
    "Kashmir Earthquake": {
        "title": "Kashmir Valley Earthquake Alert",
        "disaster_type": "Earthquake",
        "latitude": 34.0837,
        "longitude": 74.7973,
        "default_severity": "Critical",
        "affected_population": 150000,
        "confidence_score": 0.94,
        "weather": {
            "rainfall_mm": 5.0,
            "wind_speed_kmh": 10.0,
            "temperature_c": 12.0,
            "humidity_percent": 60.0,
            "flood_risk": False,
            "cyclone_risk": False,
            "weather_description": "Simulated shallow seismic tremor causing valley damage."
        },
        "earthquake": {
            "magnitude": 7.2,
            "depth_km": 12.0,
            "depth_label": "Shallow",
            "place": "Srinagar, Kashmir"
        }
    }
}

def get_demo_scenario(name: str) -> Optional[Dict[str, Any]]:
    """Retrieves the pre-configured demo scenario by exact or partial name."""
    name_clean = name.strip().lower()
    for key, data in DEMO_SCENARIOS.items():
        if name_clean == key.lower() or name_clean in key.lower():
            return data
    return None
