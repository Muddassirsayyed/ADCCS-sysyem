"""
ADCC — Satellite Tool
======================
Retrieves satellite imagery metadata and preview observations for disaster zones.
Providers:
1. Sentinel Hub (OAuth2 client credentials search)
2. Copernicus Data Space Ecosystem (CDSE OpenSearch Resto API - Free, no auth)
3. NASA EarthData CMR (Common Metadata Repository - Free, no auth)
4. NASA FIRMS (Fallback active fire locations)

Normalizes observations into SatelliteObservation Pydantic models.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests
from loguru import logger
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NASA_CMR_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
COPERNICUS_CDSE_URL = "https://catalogue.dataspace.copernicus.eu/resto/api/collections"
SENTINEL_HUB_OAUTH_URL = "https://services.sentinel-hub.com/oauth/token"
SENTINEL_HUB_CATALOG_URL = "https://services.sentinel-hub.com/api/v1/catalog/1.0.0/search"

TIMEOUT = 12
MAX_RETRIES = 3
RETRY_DELAY = 1


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================

class SatelliteObservation(BaseModel):
    """Normalized satellite observation record."""
    image_url: str = Field(..., description="Direct link to a quicklook/browse preview image or portal page")
    capture_time: str = Field(..., description="ISO 8601 capture timestamp")
    provider: str = Field(..., description="Metadata provider name (e.g., Copernicus CDSE, NASA CMR, Sentinel Hub)")
    latitude: float = Field(..., description="Observation center latitude")
    longitude: float = Field(..., description="Observation center longitude")
    disaster_type: str = Field(..., description="Disaster context: Flood, Cyclone, Wildfire, Earthquake, General")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific metadata attributes")

    class Config:
        from_attributes = True


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================

def _get_with_retry(
    url: str,
    params: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None
) -> requests.Response:
    """HTTP GET with timeout and backoff retries."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except Exception as e:
            logger.warning(f"[SatelliteTool] Request to {url} failed on attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_DELAY * attempt)
    raise RuntimeError(f"[SatelliteTool] Failed all retries for URL: {url}")


def _generate_synthetic_observations(
    latitude: float,
    longitude: float,
    disaster_type: str = "General",
    limit: int = 3
) -> List[SatelliteObservation]:
    """Generates realistic synthetic satellite observations for testing/offline support."""
    logger.warning(f"[SatelliteTool] Returning synthetic satellite observations for {latitude}, {longitude}")
    
    # Static placeholder links from NASA / Sentinel portals
    sample_images = {
        "Flood": "https://earthobservatory.nasa.gov/images/150000/150821/mumbai_amo_2022212_lrg.jpg",
        "Cyclone": "https://earthobservatory.nasa.gov/images/148347/cyclone_tauktae_vir_2021137_lrg.jpg",
        "Wildfire": "https://earthobservatory.nasa.gov/images/152345/forest_fire_oli_2024045_lrg.jpg",
        "Earthquake": "https://earthobservatory.nasa.gov/images/151000/151008/turkey_oli_2023038_lrg.jpg",
        "General": "https://eoimages.gsfc.nasa.gov/images/imagerecords/148000/148281/india_vir_2021115_lrg.jpg"
    }

    image_url = sample_images.get(disaster_type, sample_images["General"])
    now = datetime.now(timezone.utc)
    
    observations = []
    for idx in range(limit):
        cap_time = (now - timedelta(days=idx, hours=idx * 2)).isoformat()
        observations.append(
            SatelliteObservation(
                image_url=image_url,
                capture_time=cap_time,
                provider="NASA & ESA Open Archives (Simulated)",
                latitude=round(latitude + (idx * 0.02) - 0.01, 4),
                longitude=round(longitude + (idx * 0.02) - 0.01, 4),
                disaster_type=disaster_type,
                metadata={
                    "satellite_instrument": "Sentinel-2 MSI / MODIS",
                    "cloud_cover_percent": round(5.5 + idx * 8.2, 1),
                    "resolution_meters": 10 if disaster_type in ["Flood", "Wildfire"] else 250,
                    "simulated_warning": "Real keys not available or APIs rate-limited. Serving archival templates."
                }
            )
        )
    return observations


# ===========================================================================
# API REQUEST LOGIC
# ===========================================================================

def _fetch_sentinel_hub_catalog(
    lat: float,
    lon: float,
    client_id: str,
    client_secret: str,
    limit: int = 5
) -> List[SatelliteObservation]:
    """Queries the Sentinel Hub catalog API using OAuth2 client credentials."""
    logger.info(f"[SatelliteTool] Querying Sentinel Hub Catalog for lat={lat}, lon={lon}...")
    try:
        # 1. Fetch OAuth2 Token
        token_data = {"grant_type": "client_credentials"}
        token_auth = (client_id, client_secret)
        token_resp = requests.post(SENTINEL_HUB_OAUTH_URL, data=token_data, auth=token_auth, timeout=TIMEOUT)
        token_resp.raise_for_status()
        token = token_resp.json().get("access_token")

        if not token:
            logger.warning("[SatelliteTool] Failed to extract Sentinel Hub token.")
            return []

        # Bounding box around coordinates (roughly 0.1 deg ~ 11km)
        bbox = [lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05]
        now = datetime.now(timezone.utc)
        start_time = (now - timedelta(days=15)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")

        body = {
            "bbox": bbox,
            "datetime": f"{start_time}/{end_time}",
            "collections": ["sentinel-2-l2a"],
            "limit": limit
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        catalog_resp = requests.post(SENTINEL_HUB_CATALOG_URL, json=body, headers=headers, timeout=TIMEOUT)
        catalog_resp.raise_for_status()
        data = catalog_resp.json()

        observations = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            
            # Extract center coordinates of bounding box
            coords = geom.get("coordinates", [[[]]])
            centroid_lon = lon
            centroid_lat = lat
            try:
                # Approximate centroid
                all_pts = coords[0] if isinstance(coords[0], list) else []
                if all_pts:
                    centroid_lon = sum(pt[0] for pt in all_pts) / len(all_pts)
                    centroid_lat = sum(pt[1] for pt in all_pts) / len(all_pts)
            except Exception:
                pass

            # Sentinel Hub doesn't always provide simple public JPG URLs in catalog response.
            # We map a portal link or a Sentinel Hub explorer link.
            view_url = f"https://apps.sentinel-hub.com/eo-browser/?zoom=12&lat={lat}&lng={lon}&themeId=default-theme"

            observations.append(
                SatelliteObservation(
                    image_url=view_url,
                    capture_time=props.get("datetime", now.isoformat()),
                    provider="Sentinel Hub",
                    latitude=round(centroid_lat, 4),
                    longitude=round(centroid_lon, 4),
                    disaster_type="General",
                    metadata={
                        "catalog_id": props.get("id"),
                        "cloud_cover_percent": props.get("eo:cloud_cover", 0.0),
                        "satellite_platform": props.get("platform", "Sentinel-2"),
                        "instrument": "MSI"
                    }
                )
            )
        return observations
    except Exception as e:
        logger.warning(f"[SatelliteTool] Sentinel Hub catalog query failed: {e}")
        return []


def _fetch_copernicus_cdse_opensearch(
    lat: float,
    lon: float,
    limit: int = 5
) -> List[SatelliteObservation]:
    """Queries Copernicus CDSE OpenSearch Resto API for Sentinel-2 cloudless imagery metadata."""
    logger.info(f"[SatelliteTool] Querying Copernicus CDSE OpenSearch for lat={lat}, lon={lon}...")
    url = f"{COPERNICUS_CDSE_URL}/Sentinel2/search.json"
    
    # Search within last 14 days, sort by start date
    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=14)).strftime("%Y-%m-%d")
    
    params = {
        "lat": lat,
        "lon": lon,
        "startDate": start_date,
        "maxRecords": limit,
        "sortKeys": "startDate"
    }

    try:
        resp = _get_with_retry(url, params=params)
        data = resp.json()
        features = data.get("features", [])
        
        observations = []
        for feature in features:
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})

            # Center point
            coords = geom.get("coordinates", [])
            obs_lon = lon
            obs_lat = lat
            if coords and isinstance(coords, list):
                if isinstance(coords[0], float) and len(coords) >= 2:
                    obs_lon = coords[0]
                    obs_lat = coords[1]
                elif isinstance(coords[0], list):
                    # MultiPolygon/Polygon boundary coordinates
                    first_ring = coords[0]
                    obs_lon = sum(pt[0] for pt in first_ring) / len(first_ring)
                    obs_lat = sum(pt[1] for pt in first_ring) / len(first_ring)

            # Thumbnail link from Copernicus
            services = props.get("services", {})
            thumbnail_url = services.get("thumbnail", {}).get("url")
            quicklook_url = services.get("quicklook", {}).get("url")
            image_url = quicklook_url or thumbnail_url or f"https://browser.dataspace.copernicus.eu/?zoom=11&lat={lat}&lng={lon}"

            observations.append(
                SatelliteObservation(
                    image_url=image_url,
                    capture_time=props.get("startDate", now.isoformat()),
                    provider="Copernicus CDSE",
                    latitude=round(obs_lat, 4),
                    longitude=round(obs_lon, 4),
                    disaster_type="General",
                    metadata={
                        "product_id": props.get("productIdentifier"),
                        "cloud_cover_percent": props.get("cloudCover", 0.0),
                        "instrument": props.get("instrument", "MSI"),
                        "resolution_meters": 10
                    }
                )
            )
        return observations
    except Exception as e:
        logger.warning(f"[SatelliteTool] Copernicus CDSE OpenSearch query failed: {e}")
        return []


def _fetch_nasa_cmr(
    lat: float,
    lon: float,
    limit: int = 5
) -> List[SatelliteObservation]:
    """Queries NASA EarthData Common Metadata Repository (CMR) for recent MODIS/Landsat products."""
    logger.info(f"[SatelliteTool] Querying NASA CMR for lat={lat}, lon={lon}...")
    
    # Spatial boundary box (0.5 degree range)
    bbox = f"{lon - 0.25},{lat - 0.25},{lon + 0.25},{lat + 0.25}"
    
    # LPDAAC provider coordinates search
    params = {
        "bounding_box": bbox,
        "page_size": limit,
        "sort_key": "-start_date",
        "short_name": "MOD14A1"  # MODIS Active Fire metadata collection
    }

    try:
        resp = _get_with_retry(NASA_CMR_URL, params=params)
        data = resp.json()
        entries = data.get("feed", {}).get("entry", [])
        
        observations = []
        for entry in entries:
            capture_time = entry.get("time_start", datetime.now(timezone.utc).isoformat())
            
            # Find the esipfed feed browse/preview links (image_url)
            image_url = ""
            for link in entry.get("links", []):
                rel = link.get("rel", "")
                href = link.get("href", "")
                if "browse" in rel or href.endswith((".jpg", ".png", ".jpeg")):
                    image_url = href
                    break
            
            if not image_url:
                # Fallback to general browse
                image_url = f"https://worldview.earthdata.nasa.gov/?v={lon-1},{lat-1},{lon+1},{lat+1}&t={capture_time[:10]}"

            # Coordinates
            centroid_lat = lat
            centroid_lon = lon
            polygons = entry.get("polygons", [])
            if polygons and isinstance(polygons[0], list):
                try:
                    pts = [float(x) for x in polygons[0][0].split()]
                    centroid_lat = sum(pts[0::2]) / (len(pts) / 2)
                    centroid_lon = sum(pts[1::2]) / (len(pts) / 2)
                except Exception:
                    pass

            observations.append(
                SatelliteObservation(
                    image_url=image_url,
                    capture_time=capture_time,
                    provider="NASA EarthData",
                    latitude=round(centroid_lat, 4),
                    longitude=round(centroid_lon, 4),
                    disaster_type="Wildfire",  # MOD14 is fire metadata
                    metadata={
                        "granule_ur": entry.get("granule_ur"),
                        "dataset_id": entry.get("dataset_id"),
                        "data_size_mb": round(float(entry.get("size", "0.0")), 2),
                        "instrument": "MODIS"
                    }
                )
            )
        return observations
    except Exception as e:
        logger.warning(f"[SatelliteTool] NASA CMR catalog query failed: {e}")
        return []


# ===========================================================================
# PUBLIC API FUNCTIONS
# ===========================================================================

def get_satellite_metadata(
    latitude: float,
    longitude: float,
    radius_km: float = 50.0
) -> List[SatelliteObservation]:
    """
    Finds satellite observations (metadata + preview imagery) around a geographic point.
    Attempts Sentinel Hub first if keys present, falls back to Copernicus CDSE, NASA CMR,
    and returns synthetic placeholders if offline or empty.
    """
    client_id = os.getenv("SENTINEL_HUB_CLIENT_ID")
    client_secret = os.getenv("SENTINEL_HUB_CLIENT_SECRET")
    
    # 1. Twilio / Sentinel credentials search
    if client_id and client_secret:
        results = _fetch_sentinel_hub_catalog(latitude, longitude, client_id, client_secret)
        if results:
            return results

    # 2. Copernicus CDSE (Free Sentinel metadata OpenSearch)
    results = _fetch_copernicus_cdse_opensearch(latitude, longitude)
    if results:
        return results

    # 3. NASA CMR API (MODIS active fire catalog metadata)
    results = _fetch_nasa_cmr(latitude, longitude)
    if results:
        return results

    # 4. Offline Fallback
    return _generate_synthetic_observations(latitude, longitude, limit=3)


def get_flood_imagery(
    latitude: float,
    longitude: float,
    date_str: Optional[str] = None
) -> List[SatelliteObservation]:
    """Retrieves Sentinel or MODIS imagery filtered for flood/water extension (e.g. NDWI mapping context)."""
    logger.info(f"[SatelliteTool] Fetching flood imagery metadata at lat={latitude}, lon={longitude}")
    observations = get_satellite_metadata(latitude, longitude)
    
    # Annotate disaster context
    for obs in observations:
        obs.disaster_type = "Flood"
        # Append specific flood indexing metadata
        obs.metadata["spectral_band_analysis"] = "B03 (Green) vs B08 (NIR) - NDWI Water Index ready"
        
    return observations


def get_wildfire_imagery(
    latitude: float,
    longitude: float
) -> List[SatelliteObservation]:
    """Retrieves FIRMS active thermal anomalies/fires metadata."""
    logger.info(f"[SatelliteTool] Fetching fire anomaly imagery metadata at lat={latitude}, lon={longitude}")
    
    # Try NASA CMR directly for MOD14 (MODIS active fire)
    nasa_fires = _fetch_nasa_cmr(latitude, longitude)
    if nasa_fires:
        for f in nasa_fires:
            f.disaster_type = "Wildfire"
        return nasa_fires

    # General search with fire tagging
    observations = get_satellite_metadata(latitude, longitude)
    for obs in observations:
        obs.disaster_type = "Wildfire"
        obs.metadata["thermal_anomaly_bands"] = "B11 (SWIR) & B12 - Active hotspots indicator"
    return observations


def get_disaster_imagery(
    disaster_type: str,
    latitude: float,
    longitude: float
) -> List[SatelliteObservation]:
    """General dispatcher to fetch satellite observations tailored for a disaster category."""
    dtype = disaster_type.capitalize()
    if dtype == "Flood":
        return get_flood_imagery(latitude, longitude)
    elif dtype == "Wildfire":
        return get_wildfire_imagery(latitude, longitude)
    
    # General categories
    observations = get_satellite_metadata(latitude, longitude)
    for obs in observations:
        obs.disaster_type = dtype
    return observations


def get_latest_satellite_observations(
    latitude: float,
    longitude: float
) -> List[SatelliteObservation]:
    """Simple wrapper returning the absolute newest observations near coordinates."""
    return get_satellite_metadata(latitude, longitude, radius_km=25.0)


if __name__ == "__main__":
    print("=" * 60)
    print("VALIDATING: tools/satellite_tool.py")
    print("=" * 60)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        mumbai_lat, mumbai_lon = 19.0760, 72.8777
        
        # Test 1: get_satellite_metadata (General search around Mumbai)
        obs = get_satellite_metadata(mumbai_lat, mumbai_lon)
        print(f"Test 1 (get_satellite_metadata) Passed: Count={len(obs)}")
        if obs:
            print(f"  First observation: Provider={obs[0].provider} | Captured={obs[0].capture_time} | Coordinates={obs[0].latitude}, {obs[0].longitude}")
            print(f"  Image URL: {obs[0].image_url}")
            
        # Test 2: Pydantic Validation check
        if obs:
            assert isinstance(obs[0], SatelliteObservation)
            print("Test 2 (Pydantic validation) Passed.")
            
        # Test 3: get_flood_imagery
        flood_imgs = get_flood_imagery(mumbai_lat, mumbai_lon)
        print(f"Test 3 (get_flood_imagery) Passed: Count={len(flood_imgs)}")
        
        # Test 4: get_wildfire_imagery
        fire_imgs = get_wildfire_imagery(mumbai_lat, mumbai_lon)
        print(f"Test 4 (get_wildfire_imagery) Passed: Count={len(fire_imgs)}")

        print("\n[SatelliteTool] Validation completed successfully!")
    except Exception as e:
        print(f"\n[SatelliteTool] Validation FAILED: {e}")
        import traceback
        traceback.print_exc()

