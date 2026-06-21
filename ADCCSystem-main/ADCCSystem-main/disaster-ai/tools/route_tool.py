"""
ADCC — Route Tool
=================
Emergency routing and evacuation path planning using OpenRouteService API.
Supports fallbacks when API is offline or key is missing.

API Base: https://api.openrouteservice.org
Docs:     https://openrouteservice.org/dev/#/api-docs
"""

import os
import time
import math
from datetime import datetime, timedelta, timezone
from typing import Optional, List

import requests
from loguru import logger
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE_URL = "https://api.openrouteservice.org/v2/directions"
TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 2

# Profile mappings for OpenRouteService
# Docs: https://openrouteservice.org/dev/#/api-docs/v2/directions/{profile}/post
ORS_PROFILES = {
    "driving-car": "driving-car",
    "driving-hgv": "driving-hgv",
    "foot-walking": "foot-walking",
    "cycling-regular": "cycling-regular"
}


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================

class AlternativeRoute(BaseModel):
    """Sub-route for alternative options."""
    distance_km: float = Field(..., description="Route distance in kilometers")
    duration_minutes: float = Field(..., description="Route duration in minutes")
    route_coordinates: List[List[float]] = Field(..., description="List of [latitude, longitude] coordinates")
    eta: str = Field(..., description="ISO 8601 estimated time of arrival")


class RouteResponse(BaseModel):
    """Normalized routing response returned by all route_tool functions."""
    distance_km: float = Field(..., description="Total route distance in kilometers")
    duration_minutes: float = Field(..., description="Total route duration in minutes")
    route_coordinates: List[List[float]] = Field(..., description="List of [latitude, longitude] coordinates")
    eta: str = Field(..., description="ISO 8601 estimated time of arrival")
    alternative_routes: List[AlternativeRoute] = Field(default_factory=list, description="Alternative routes")
    provider: str = Field(..., description="API provider name ('OpenRouteService' or 'Geometric Fallback')")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        from_attributes = True


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================

def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates straight-line distance between two points in km."""
    R = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _generate_geometric_fallback(
    start_coords: List[float],
    end_coords: List[float],
    profile: str = "driving-car",
    target_count: int = 1
) -> RouteResponse:
    """
    Generates a realistic routing estimation using straight-line distance,
    road winding factors, typical speeds per vehicle profile, and interpolated points.
    """
    lat1, lon1 = start_coords[0], start_coords[1]
    lat2, lon2 = end_coords[0], end_coords[1]

    direct_dist = _haversine_distance(lat1, lon1, lat2, lon2)
    
    # Winding factors: roads are not straight lines. 1.3 is standard road winding.
    winding_factor = 1.3
    distance_km = round(direct_dist * winding_factor, 2)

    # Typical speeds (km/h) for different profiles
    speeds = {
        "driving-car": 50.0,
        "driving-hgv": 40.0,
        "foot-walking": 5.0,
        "cycling-regular": 15.0
    }
    speed_kmh = speeds.get(profile, 50.0)
    duration_minutes = round((distance_km / speed_kmh) * 60.0, 1)

    # Interpolate coordinates to represent path points on the map
    # We generate a list of 10 points between start and end with minor random deviations
    num_points = max(5, int(distance_km // 2))
    num_points = min(num_points, 30)  # cap at 30 points
    coords = []
    for i in range(num_points + 1):
        t = i / num_points
        lat_t = lat1 + t * (lat2 - lat1)
        lon_t = lon1 + t * (lon2 - lon1)
        
        # Add slight wobble to make it look like road bends, except for start and end
        if i > 0 and i < num_points:
            wobble_lat = math.sin(t * math.pi) * 0.005 * (math.sin(i * 1.5))
            wobble_lon = math.cos(t * math.pi) * 0.005 * (math.cos(i * 1.5))
            lat_t += wobble_lat
            lon_t += wobble_lon
            
        coords.append([round(lat_t, 6), round(lon_t, 6)])

    # Compute ETA
    now = datetime.now(timezone.utc)
    eta_dt = now + timedelta(minutes=duration_minutes)
    eta_str = eta_dt.isoformat()

    # Generate alternative routes if target_count > 1
    alternative_routes = []
    if target_count > 1:
        for idx in range(1, target_count):
            # Alternative routes are slightly longer and take different winding routes
            alt_winding = winding_factor + (idx * 0.15)
            alt_dist = round(direct_dist * alt_winding, 2)
            alt_duration = round((alt_dist / (speed_kmh * 0.85)) * 60.0, 1)
            
            # Alternative coordinates (skewed slightly differently)
            alt_coords = []
            for i in range(num_points + 1):
                t = i / num_points
                lat_t = lat1 + t * (lat2 - lat1)
                lon_t = lon1 + t * (lon2 - lon1)
                if i > 0 and i < num_points:
                    wobble_lat = math.sin(t * math.pi) * 0.012 * (math.sin(i * 2.1 + idx))
                    wobble_lon = math.cos(t * math.pi) * 0.012 * (math.cos(i * 2.1 + idx))
                    lat_t += wobble_lat
                    lon_t += wobble_lon
                alt_coords.append([round(lat_t, 6), round(lon_t, 6)])
            
            alt_eta = (now + timedelta(minutes=alt_duration)).isoformat()
            alternative_routes.append(
                AlternativeRoute(
                    distance_km=alt_dist,
                    duration_minutes=alt_duration,
                    route_coordinates=alt_coords,
                    eta=alt_eta
                )
            )

    return RouteResponse(
        distance_km=distance_km,
        duration_minutes=duration_minutes,
        route_coordinates=coords,
        eta=eta_str,
        alternative_routes=alternative_routes,
        provider="Geometric Fallback"
    )


def _get_api_key() -> Optional[str]:
    """Retrieves ORS API key from environment."""
    return os.getenv("OPENROUTESERVICE_API_KEY") or os.getenv("ORS_API_KEY")


# ===========================================================================
# PUBLIC FUNCTIONS
# ===========================================================================

def get_route(
    start_coords: List[float],
    end_coords: List[float],
    profile: str = "driving-car"
) -> RouteResponse:
    """
    Calculates the fastest route between start_coords and end_coords using OpenRouteService.
    If the API key is missing or the service is offline, falls back to a geometric path.

    Args:
        start_coords: Origin coordinates as list [latitude, longitude]
        end_coords: Destination coordinates as list [latitude, longitude]
        profile: Route vehicle profile: driving-car, driving-hgv, foot-walking, cycling-regular

    Returns:
        RouteResponse: Pydantic model with distance, duration, coordinate track, and ETA.
    """
    # Validate coordinate lists
    if len(start_coords) != 2 or len(end_coords) != 2:
        raise ValueError("Coordinates must be in the format [latitude, longitude]")

    api_key = _get_api_key()
    if not api_key:
        logger.warning("[RouteTool] No OPENROUTESERVICE_API_KEY or ORS_API_KEY found. Using geometric fallback.")
        return _generate_geometric_fallback(start_coords, end_coords, profile=profile)

    ors_profile = ORS_PROFILES.get(profile, "driving-car")
    url = f"{API_BASE_URL}/{ors_profile}/geojson"

    # Coordinate translation: OpenRouteService expects coordinates as [longitude, latitude]
    # We take [latitude, longitude] and flip them for the API.
    body = {
        "coordinates": [
            [start_coords[1], start_coords[0]],  # start: [lon, lat]
            [end_coords[1], end_coords[0]]      # end: [lon, lat]
        ]
    }
    
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    logger.info(f"[RouteTool] Routing via OpenRouteService: {start_coords} -> {end_coords} (profile={ors_profile})")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
            
            if resp.status_code == 401:
                logger.error("[RouteTool] 401 Unauthorized — invalid API key. Falling back.")
                return _generate_geometric_fallback(start_coords, end_coords, profile=profile)

            resp.raise_for_status()
            data = resp.json()
            
            # Parse GeoJSON response
            features = data.get("features", [])
            if not features:
                logger.warning("[RouteTool] Empty features in route response. Falling back.")
                return _generate_geometric_fallback(start_coords, end_coords, profile=profile)

            feature = features[0]
            properties = feature.get("properties", {})
            geometry = feature.get("geometry", {})

            summary = properties.get("summary", {})
            distance_m = summary.get("distance", 0.0)
            duration_s = summary.get("duration", 0.0)

            # Convert to km and minutes
            distance_km = round(distance_m / 1000.0, 2)
            duration_minutes = round(duration_s / 60.0, 1)

            # Coordinates in GeoJSON are [lon, lat]. We reverse them back to [lat, lon] for ADCC.
            raw_coordinates = geometry.get("coordinates", [])
            route_coordinates = [[pt[1], pt[0]] for pt in raw_coordinates]

            # ETA
            now = datetime.now(timezone.utc)
            eta_dt = now + timedelta(minutes=duration_minutes)
            eta_str = eta_dt.isoformat()

            logger.success(f"[RouteTool] Route fetched successfully: {distance_km}km, {duration_minutes}m")
            return RouteResponse(
                distance_km=distance_km,
                duration_minutes=duration_minutes,
                route_coordinates=route_coordinates,
                eta=eta_str,
                provider="OpenRouteService"
            )

        except requests.exceptions.HTTPError as e:
            logger.error(f"[RouteTool] HTTP error on attempt {attempt}/{MAX_RETRIES}: {e}")
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            logger.warning(f"[RouteTool] Network warning on attempt {attempt}/{MAX_RETRIES}: {e}")
        except Exception as e:
            logger.error(f"[RouteTool] Unexpected parsing error: {e}")
            break

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY * attempt)

    logger.warning("[RouteTool] Routing request failed. Using geometric fallback.")
    return _generate_geometric_fallback(start_coords, end_coords, profile=profile)


def get_evacuation_route(start_coords: List[float], end_coords: List[float]) -> RouteResponse:
    """Convenience wrapper for calculating evacuation route (e.g. disaster zone to shelter)."""
    return get_route(start_coords, end_coords, profile="driving-car")


def get_resource_route(start_coords: List[float], end_coords: List[float]) -> RouteResponse:
    """Convenience wrapper for calculating heavy resource deployment route (e.g. hospital/NDRF base to zone)."""
    return get_route(start_coords, end_coords, profile="driving-hgv")


def get_alternative_routes(
    start_coords: List[float],
    end_coords: List[float],
    count: int = 3
) -> RouteResponse:
    """
    Calculates multiple alternative routes between origin and destination.
    Uses ORS alternative route capability or geometric calculation.
    """
    if len(start_coords) != 2 or len(end_coords) != 2:
        raise ValueError("Coordinates must be in the format [latitude, longitude]")

    api_key = _get_api_key()
    if not api_key:
        return _generate_geometric_fallback(start_coords, end_coords, profile="driving-car", target_count=count)

    # For alternative routes, ORS directions endpoint supports alternative routes POST param
    url = f"{API_BASE_URL}/driving-car/geojson"
    body = {
        "coordinates": [
            [start_coords[1], start_coords[0]],
            [end_coords[1], end_coords[0]]
        ],
        "alternative_routes": {
            "target_count": count
        }
    }
    
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    try:
        resp = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        
        features = data.get("features", [])
        if not features:
            return _generate_geometric_fallback(start_coords, end_coords, profile="driving-car", target_count=count)

        # The first feature is the primary route
        primary_feature = features[0]
        p_props = primary_feature.get("properties", {})
        p_geom = primary_feature.get("geometry", {})
        p_summary = p_props.get("summary", {})
        p_coords = [[pt[1], pt[0]] for pt in p_geom.get("coordinates", [])]
        p_dist = round(p_summary.get("distance", 0.0) / 1000.0, 2)
        p_dur = round(p_summary.get("duration", 0.0) / 60.0, 1)
        now = datetime.now(timezone.utc)
        p_eta = (now + timedelta(minutes=p_dur)).isoformat()

        # Parse alternatives (remaining features)
        alternative_routes = []
        for feat in features[1:]:
            geom = feat.get("geometry", {})
            props = feat.get("properties", {})
            summary = props.get("summary", {})
            coords = [[pt[1], pt[0]] for pt in geom.get("coordinates", [])]
            dist = round(summary.get("distance", 0.0) / 1000.0, 2)
            dur = round(summary.get("duration", 0.0) / 60.0, 1)
            eta = (now + timedelta(minutes=dur)).isoformat()
            
            alternative_routes.append(
                AlternativeRoute(
                    distance_km=dist,
                    duration_minutes=dur,
                    route_coordinates=coords,
                    eta=eta
                )
            )

        return RouteResponse(
            distance_km=p_dist,
            duration_minutes=p_dur,
            route_coordinates=p_coords,
            eta=p_eta,
            alternative_routes=alternative_routes,
            provider="OpenRouteService"
        )
    except Exception as e:
        logger.warning(f"[RouteTool] Failed to fetch alternatives: {e}. Using geometric fallback.")
        return _generate_geometric_fallback(start_coords, end_coords, profile="driving-car", target_count=count)


def calculate_eta(
    start_coords: List[float],
    end_coords: List[float],
    profile: str = "driving-car"
) -> dict:
    """
    Returns a brief dictionary summary with duration and ETA timestamp.
    Convenient for quick state lookups.
    """
    route = get_route(start_coords, end_coords, profile=profile)
    return {
        "duration_minutes": route.duration_minutes,
        "eta": route.eta,
        "distance_km": route.distance_km,
        "provider": route.provider
    }


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDATING: tools/route_tool.py")
    print("=" * 60)
    try:
        # Load environment variables if any
        from dotenv import load_dotenv
        load_dotenv()
        
        mumbai = [19.0760, 72.8777]
        pune = [18.5204, 73.8567]
        
        # Test 1: get_route (default car)
        res = get_route(mumbai, pune)
        print(f"Test 1 (get_route) Passed: {res.distance_km}km, {res.duration_minutes}min via {res.provider}")
        
        # Test 2: Pydantic validation
        assert isinstance(res, RouteResponse)
        assert len(res.route_coordinates) > 0
        print("Test 2 (Pydantic validation) Passed.")
        
        # Test 3: get_alternative_routes
        alts = get_alternative_routes(mumbai, pune, count=2)
        print(f"Test 3 (get_alternative_routes) Passed: Primary={alts.distance_km}km, Alternatives Count={len(alts.alternative_routes)}")
        
        # Test 4: calculate_eta
        eta_data = calculate_eta(mumbai, pune)
        print(f"Test 4 (calculate_eta) Passed: ETA is {eta_data['eta']}")
        
        print("\n[RouteTool] Validation completed successfully!")
    except Exception as e:
        print(f"\n[RouteTool] Validation FAILED: {e}")
        import traceback
        traceback.print_exc()

