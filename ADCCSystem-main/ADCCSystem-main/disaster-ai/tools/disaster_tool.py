"""
ADCC — USGS Earthquake Tool
=============================
Fetches real-time earthquake data from the USGS Earthquake Hazards Program.

API Base: https://earthquake.usgs.gov/fdsnws/event/1/query
Docs:     https://earthquake.usgs.gov/fdsnws/event/1/

No API key required.

Used by (future):
    - data_collection_agent.py → imports live earthquake events into DB
    - severity_agent.py        → uses magnitude + depth for severity scoring
    - verification_agent.py    → cross-checks earthquake reports against USGS

Functions:
    get_recent_earthquakes(minmagnitude, days, limit)           → EarthquakeResponse
    get_earthquakes_by_magnitude(min_mag, max_mag, days, limit) → EarthquakeResponse
    get_earthquakes_near(lat, lon, radius_km, days, min_mag)    → EarthquakeResponse
    get_india_earthquakes(days, min_mag)                        → EarthquakeResponse
"""

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import requests
from loguru import logger
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
TIMEOUT      = 15  # seconds
MAX_RETRIES  = 3
RETRY_DELAY  = 2

# India bounding box for geo-filtered queries
INDIA_BBOX = {
    "minlatitude":  6.0,
    "maxlatitude":  37.6,
    "minlongitude": 68.0,
    "maxlongitude": 97.5,
}

# Magnitude → ADCC severity mapping
def _magnitude_to_severity(magnitude: float) -> str:
    """Maps Richter magnitude to ADCC SeverityLevel string."""
    if magnitude >= 7.0:
        return "Critical"
    elif magnitude >= 5.5:
        return "High"
    elif magnitude >= 4.0:
        return "Medium"
    else:
        return "Low"

# Depth → risk description
def _depth_to_label(depth_km: float) -> str:
    if depth_km < 10:
        return "Very Shallow (high surface impact)"
    elif depth_km < 70:
        return "Shallow"
    elif depth_km < 300:
        return "Intermediate"
    else:
        return "Deep"


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================


class EarthquakeEvent(BaseModel):
    """Normalized USGS GeoJSON earthquake event."""

    # USGS identifiers
    usgs_id: str = Field(..., description="USGS unique event ID (e.g. 'us7000ABCD')")
    usgs_url: str = Field(..., description="USGS event detail page URL")

    # Core measurements
    magnitude: float = Field(..., description="Richter magnitude")
    magnitude_type: str = Field("ml", description="Magnitude scale (ml, mw, mb, etc.)")
    depth_km: float = Field(..., description="Hypocentre depth (km)")
    depth_label: str = Field(..., description="Human depth category")

    # Location
    latitude: float
    longitude: float
    place: str = Field(..., description="USGS place description (e.g. '45km NW of Bhuj')")
    country: Optional[str] = Field(None, description="Country if extractable from place")

    # ADCC severity mapping
    severity_mapped: str = Field(..., description="Mapped ADCC severity: Low/Medium/High/Critical")

    # Timing
    event_time: datetime = Field(..., description="Event UTC timestamp")
    event_time_ist: Optional[str] = Field(None, description="Event time IST string (human-readable)")

    # Impact data (may be None for recent events)
    felt_reports: Optional[int] = Field(None, description="Number of 'Did you feel it?' reports")
    tsunami_risk: bool = Field(False, description="True if USGS issued tsunami alert")
    alert_level: Optional[str] = Field(None, description="PAGER alert level: green/yellow/orange/red")
    significance: Optional[int] = Field(None, description="USGS significance score 0-1000")

    # Source
    source: str = "USGS"
    source_url: str = Field(..., description="Direct USGS event URL")


class EarthquakeResponse(BaseModel):
    """Container for a USGS earthquake query result."""

    query_type: str
    parameters: dict = Field(default_factory=dict, description="Query parameters used")
    total_fetched: int
    events: list[EarthquakeEvent]
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "USGS Earthquake Hazards Program"
    source_url: str = "https://earthquake.usgs.gov/fdsnws/event/1"


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================


def _get_with_retry(url: str, params: dict) -> dict:
    """HTTP GET with exponential backoff retry for USGS API."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug(f"[DisasterTool] GET attempt {attempt}/{MAX_RETRIES} → {url}")
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.HTTPError as e:
            logger.error(f"[DisasterTool] HTTP {e.response.status_code}: {e}")
            raise

        except requests.exceptions.Timeout:
            logger.warning(f"[DisasterTool] Timeout on attempt {attempt}")

        except requests.exceptions.ConnectionError:
            logger.warning(f"[DisasterTool] Connection error on attempt {attempt}")

        except Exception as e:
            logger.error(f"[DisasterTool] Unexpected error: {e}")
            raise

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            logger.info(f"[DisasterTool] Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"[DisasterTool] All {MAX_RETRIES} retries failed for {url}")


def _parse_feature(feature: dict) -> Optional[EarthquakeEvent]:
    """
    Parses a USGS GeoJSON Feature into an EarthquakeEvent model.
    Returns None if parsing fails.
    """
    try:
        props = feature.get("properties", {})
        geom  = feature.get("geometry", {})
        coords = geom.get("coordinates", [None, None, None])

        magnitude = props.get("mag") or 0.0
        depth_km  = coords[2] or 0.0
        event_ms  = props.get("time") or 0
        place     = props.get("place") or "Unknown location"

        # Convert millisecond timestamp to datetime
        event_time = datetime.fromtimestamp(event_ms / 1000, tz=timezone.utc)

        # IST = UTC + 5:30
        from datetime import timedelta
        ist_offset = timedelta(hours=5, minutes=30)
        event_time_ist = (event_time + ist_offset).strftime("%d %b %Y %H:%M IST")

        # Extract country hint from place string
        country = None
        place_lower = place.lower()
        india_keywords = ["india", "gujarat", "assam", "kashmir", "uttarakhand",
                          "manipur", "andaman", "himachal", "rajasthan"]
        if any(kw in place_lower for kw in india_keywords):
            country = "India"

        tsunami = bool(props.get("tsunami", 0))
        alert   = props.get("alert")  # green/yellow/orange/red or None

        usgs_id  = feature.get("id", "unknown")
        usgs_url = props.get("url") or f"https://earthquake.usgs.gov/earthquakes/eventpage/{usgs_id}"

        return EarthquakeEvent(
            usgs_id=usgs_id,
            usgs_url=usgs_url,
            magnitude=round(magnitude, 1),
            magnitude_type=props.get("magType", "ml"),
            depth_km=round(depth_km, 1),
            depth_label=_depth_to_label(depth_km),
            latitude=coords[1],
            longitude=coords[0],
            place=place,
            country=country,
            severity_mapped=_magnitude_to_severity(magnitude),
            event_time=event_time,
            event_time_ist=event_time_ist,
            felt_reports=props.get("felt"),
            tsunami_risk=tsunami,
            alert_level=alert,
            significance=props.get("sig"),
            source_url=usgs_url,
        )

    except Exception as e:
        logger.warning(f"[DisasterTool] Failed to parse feature {feature.get('id')}: {e}")
        return None


def _build_time_params(days: int) -> dict:
    """Returns starttime/endtime params for the last N days."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)
    return {
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime":   now.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def _fetch_earthquakes(params: dict, query_type: str) -> EarthquakeResponse:
    """Core function: queries USGS API with given params, returns EarthquakeResponse."""
    params["format"] = "geojson"
    params["orderby"] = "time"  # most recent first

    try:
        data = _get_with_retry(API_BASE_URL, params)
    except Exception as e:
        logger.error(f"[DisasterTool] USGS API call failed: {e}")
        return EarthquakeResponse(
            query_type=query_type,
            parameters=params,
            total_fetched=0,
            events=[],
        )

    features = data.get("features", [])
    events: list[EarthquakeEvent] = []
    for feature in features:
        eq = _parse_feature(feature)
        if eq:
            events.append(eq)

    result = EarthquakeResponse(
        query_type=query_type,
        parameters=params,
        total_fetched=len(events),
        events=events,
    )
    return result


# ===========================================================================
# PUBLIC FUNCTIONS
# ===========================================================================


def get_recent_earthquakes(
    minmagnitude: float = 4.5,
    days: int = 7,
    limit: int = 50,
) -> EarthquakeResponse:
    """
    Fetches recent earthquakes globally above a minimum magnitude.

    Args:
        minmagnitude: Minimum Richter magnitude (default 4.5)
        days:         How many past days to query (default 7)
        limit:        Max results (default 50)

    Returns:
        EarthquakeResponse: Normalized list of earthquake events

    Example:
        >>> result = get_recent_earthquakes(minmagnitude=5.0, days=3)
        >>> for eq in result.events:
        ...     print(eq.magnitude, eq.place)
    """
    logger.info(f"[DisasterTool] Fetching recent earthquakes M≥{minmagnitude} past {days} days")

    params = {
        "minmagnitude": minmagnitude,
        "limit":        limit,
        **_build_time_params(days),
    }

    result = _fetch_earthquakes(params, f"recent_M{minmagnitude}_{days}d")
    logger.success(f"[DisasterTool] Found {result.total_fetched} earthquakes M≥{minmagnitude}")
    return result


def get_earthquakes_by_magnitude(
    min_mag: float,
    max_mag: Optional[float] = None,
    days: int = 30,
    limit: int = 100,
) -> EarthquakeResponse:
    """
    Fetches earthquakes within a magnitude range.

    Args:
        min_mag: Minimum magnitude (inclusive)
        max_mag: Maximum magnitude (inclusive, optional)
        days:    How many past days to query (default 30)
        limit:   Max results (default 100)

    Returns:
        EarthquakeResponse: Filtered earthquake events

    Example:
        >>> # Significant earthquakes (M5.5 - M7.0) in last 30 days
        >>> result = get_earthquakes_by_magnitude(5.5, 7.0, days=30)
    """
    logger.info(f"[DisasterTool] Fetching earthquakes M{min_mag}–{max_mag or '∞'} past {days} days")

    params: dict = {
        "minmagnitude": min_mag,
        "limit":        limit,
        **_build_time_params(days),
    }
    if max_mag is not None:
        params["maxmagnitude"] = max_mag

    label = f"M{min_mag}_{f'M{max_mag}' if max_mag else 'up'}_{days}d"
    result = _fetch_earthquakes(params, label)
    logger.success(f"[DisasterTool] Found {result.total_fetched} earthquakes in M range")
    return result


def get_earthquakes_near(
    latitude: float,
    longitude: float,
    radius_km: float = 300.0,
    days: int = 30,
    minmagnitude: float = 3.0,
) -> EarthquakeResponse:
    """
    Fetches earthquakes within a radius of given coordinates.
    Useful for checking seismic activity around a disaster zone.

    Args:
        latitude:     Centre latitude
        longitude:    Centre longitude
        radius_km:    Search radius in km (default 300km)
        days:         How many past days (default 30)
        minmagnitude: Minimum magnitude (default 3.0)

    Returns:
        EarthquakeResponse: Earthquakes near the given location

    Example:
        >>> # Earthquakes within 200km of Mumbai in last 14 days
        >>> result = get_earthquakes_near(19.0760, 72.8777, radius_km=200, days=14)
    """
    logger.info(f"[DisasterTool] Fetching M≥{minmagnitude} earthquakes within {radius_km}km of ({latitude}, {longitude})")

    params = {
        "latitude":     latitude,
        "longitude":    longitude,
        "maxradiuskm":  radius_km,
        "minmagnitude": minmagnitude,
        "limit":        50,
        **_build_time_params(days),
    }

    result = _fetch_earthquakes(params, f"near_{latitude}_{longitude}_{radius_km}km")
    logger.success(f"[DisasterTool] Found {result.total_fetched} earthquakes near ({latitude}, {longitude})")
    return result


def get_india_earthquakes(
    days: int = 30,
    minmagnitude: float = 3.0,
) -> EarthquakeResponse:
    """
    Fetches earthquakes within the India bounding box.
    Covers India, Pakistan, Nepal, Bangladesh, Sri Lanka.

    Args:
        days:         How many past days (default 30)
        minmagnitude: Minimum magnitude (default 3.0)

    Returns:
        EarthquakeResponse: Earthquakes in the India region

    Example:
        >>> india_eqs = get_india_earthquakes(days=7, minmagnitude=4.0)
        >>> print(india_eqs.total_fetched)
    """
    logger.info(f"[DisasterTool] Fetching India region earthquakes M≥{minmagnitude} past {days} days")

    params = {
        "minmagnitude": minmagnitude,
        "limit": 100,
        **INDIA_BBOX,
        **_build_time_params(days),
    }

    result = _fetch_earthquakes(params, f"india_M{minmagnitude}_{days}d")
    logger.success(f"[DisasterTool] Found {result.total_fetched} India region earthquakes")
    return result
