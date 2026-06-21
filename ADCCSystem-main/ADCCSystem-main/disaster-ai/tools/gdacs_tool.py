"""
ADCC — GDACS Tool
==================
Fetches active global disaster alerts from the Global Disaster Alert
and Coordination System (GDACS).

API Base: https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH
RSS Feed: https://www.gdacs.org/xml/rss.xml
Docs:     https://www.gdacs.org/gdacsapi/

No API key required.

Used by (future):
    - data_collection_agent.py → imports live disaster alerts into DB
    - verification_agent.py    → cross-checks disasters against GDACS feed
    - severity_agent.py        → uses GDACS alert level for severity scoring

Functions:
    get_active_disasters(event_types, alert_levels, limit) → list[GDACSEvent]
    get_disaster_by_country(country_name, limit)           → list[GDACSEvent]
    get_event_detail(event_id, event_type)                 → GDACSEventDetail
"""

import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Optional

import requests
from loguru import logger
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_BASE_URL  = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH"
RSS_FEED_URL  = "https://www.gdacs.org/xml/rss.xml"
DETAIL_URL    = "https://www.gdacs.org/gdacsapi/api/events/geteventdata/report"
TIMEOUT       = 15
MAX_RETRIES   = 3
RETRY_DELAY   = 2

# GDACS alert level colors → ADCC severity mapping
ALERT_TO_SEVERITY: dict[str, str] = {
    "Red":    "Critical",
    "Orange": "High",
    "Green":  "Low",
}

# GDACS event type codes
EVENT_TYPES = {
    "EQ": "Earthquake",
    "TC": "Tropical Cyclone",
    "FL": "Flood",
    "VO": "Volcano",
    "DR": "Drought",
    "WF": "Wild Fire",
    "TS": "Tsunami",
}


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================


class GDACSEvent(BaseModel):
    """Normalized GDACS disaster event record."""

    # Identifiers
    event_id: str = Field(..., description="GDACS event ID")
    event_type: str = Field(..., description="Event type code: EQ, TC, FL, VO, etc.")
    event_type_label: str = Field(..., description="Human-readable event type")

    # Alert info
    alert_level: str = Field(..., description="GDACS alert level: Red, Orange, Green")
    severity_mapped: str = Field(..., description="Mapped ADCC severity level")
    alert_score: Optional[float] = Field(None, description="GDACS numerical alert score")

    # Location
    country: str = Field("Unknown", description="Affected country name")
    country_iso3: Optional[str] = Field(None, description="ISO3 country code")
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Description
    title: str = Field(..., description="Short event title")
    description: Optional[str] = Field(None, description="Detailed description")
    url: str = Field(..., description="GDACS event page URL")

    # Affected people
    affected_population: Optional[int] = Field(None, description="Estimated affected population")

    # Timestamps
    event_date: Optional[str] = Field(None, description="Event date (ISO string)")
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Source metadata for DB
    source: str = "GDACS"
    source_url: str = "https://www.gdacs.org"


class GDACSResponse(BaseModel):
    """Container for a GDACS API query result."""

    query_type: str = Field(..., description="'active', 'by_country', etc.")
    total_fetched: int
    events: list[GDACSEvent]
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "GDACS"
    source_url: str = "https://www.gdacs.org"


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================


def _get_with_retry(url: str, params: Optional[dict] = None, headers: Optional[dict] = None) -> requests.Response:
    """HTTP GET with exponential backoff retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.debug(f"[GDACSCTool] GET attempt {attempt}/{MAX_RETRIES} → {url}")
            resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp

        except requests.exceptions.HTTPError as e:
            logger.error(f"[GDACSCTool] HTTP {e.response.status_code}: {e}")
            raise

        except requests.exceptions.Timeout:
            logger.warning(f"[GDACSCTool] Timeout on attempt {attempt}")

        except requests.exceptions.ConnectionError:
            logger.warning(f"[GDACSCTool] Connection error on attempt {attempt}")

        except Exception as e:
            logger.error(f"[GDACSCTool] Unexpected error: {e}")
            raise

        if attempt < MAX_RETRIES:
            wait = RETRY_DELAY * (2 ** (attempt - 1))
            logger.info(f"[GDACSCTool] Retrying in {wait}s...")
            time.sleep(wait)

    raise RuntimeError(f"[GDACSCTool] All {MAX_RETRIES} retries failed for {url}")


def _parse_api_event(item: dict) -> Optional[GDACSEvent]:
    """
    Parses a single GDACS API event dict into a GDACSEvent model.
    Returns None if the event cannot be parsed.
    """
    try:
        event_type_code = item.get("eventtype", "??")
        alert_level = item.get("alertlevel", "Green")
        latitude = None
        longitude = None

        # Extract coordinates from bbox or point
        bbox = item.get("bbox")
        if bbox and len(bbox) >= 4:
            latitude  = (bbox[1] + bbox[3]) / 2
            longitude = (bbox[0] + bbox[2]) / 2
        
        # Fallback to direct property fields
        if latitude is None or longitude is None:
            latitude = item.get("_lat") or item.get("latitude")
            longitude = item.get("_lon") or item.get("longitude")

        # Population
        pop_str = item.get("affectedpopulation", "0") or "0"
        try:
            affected = int(str(pop_str).replace(",", "").split(".")[0])
        except (ValueError, TypeError):
            affected = None

        return GDACSEvent(
            event_id=str(item.get("eventid", "")),
            event_type=event_type_code,
            event_type_label=EVENT_TYPES.get(event_type_code, event_type_code),
            alert_level=alert_level,
            severity_mapped=ALERT_TO_SEVERITY.get(alert_level, "Medium"),
            alert_score=item.get("alertscore"),
            country=item.get("country", "Unknown"),
            country_iso3=item.get("iso3"),
            latitude=latitude,
            longitude=longitude,
            title=item.get("name", f"GDACS {event_type_code} Event"),
            description=item.get("description"),
            url=item.get("url", {}).get("report", f"https://www.gdacs.org/report.aspx?eventid={item.get('eventid')}&eventtype={event_type_code}") if isinstance(item.get("url"), dict) else f"https://www.gdacs.org/report.aspx?eventid={item.get('eventid')}&eventtype={event_type_code}",
            affected_population=affected,
            event_date=item.get("todate") or item.get("fromdate"),
        )
    except Exception as e:
        logger.warning(f"[GDACSCTool] Failed to parse event {item.get('eventid')}: {e}")
        return None


def _parse_rss_feed(xml_content: str) -> list[GDACSEvent]:
    """
    Fallback: parse GDACS RSS XML feed into GDACSEvent list.
    Used when the JSON API is unavailable.
    """
    events: list[GDACSEvent] = []

    # Namespace map for GDACS RSS
    ns = {
        "gdacs": "http://www.gdacs.org",
        "geo":   "http://www.w3.org/2003/01/geo/wgs84_pos#",
        "dc":    "http://purl.org/dc/elements/1.1/",
    }

    try:
        root = ET.fromstring(xml_content)
        channel = root.find("channel")
        if channel is None:
            return []

        items = channel.findall("item")
        logger.debug(f"[GDACSCTool] RSS feed has {len(items)} items")

        for item in items:
            try:
                title = item.findtext("title", "Unknown")
                link  = item.findtext("link", "https://www.gdacs.org")
                desc  = item.findtext("description", "")

                alert_level = item.findtext("gdacs:alertlevel", "Green", ns) or "Green"
                event_type  = item.findtext("gdacs:eventtype", "??", ns) or "??"
                event_id    = item.findtext("gdacs:eventid", "0", ns) or "0"
                country     = item.findtext("gdacs:country", "Unknown", ns) or "Unknown"

                lat_str = item.findtext("geo:lat", None, ns)
                lon_str = item.findtext("geo:long", None, ns)
                latitude  = float(lat_str) if lat_str else None
                longitude = float(lon_str) if lon_str else None

                pop_str = item.findtext("gdacs:population", "0", ns) or "0"
                try:
                    affected = int(str(pop_str).split(".")[0])
                except ValueError:
                    affected = None

                events.append(GDACSEvent(
                    event_id=str(event_id),
                    event_type=event_type,
                    event_type_label=EVENT_TYPES.get(event_type, event_type),
                    alert_level=alert_level,
                    severity_mapped=ALERT_TO_SEVERITY.get(alert_level, "Medium"),
                    country=country,
                    latitude=latitude,
                    longitude=longitude,
                    title=title,
                    description=desc[:500] if desc else None,
                    url=link,
                    affected_population=affected,
                    event_date=item.findtext("pubDate"),
                ))
            except Exception as e:
                logger.warning(f"[GDACSCTool] RSS item parse error: {e}")
                continue

    except ET.ParseError as e:
        logger.error(f"[GDACSCTool] RSS XML parse error: {e}")

    return events


# ===========================================================================
# PUBLIC FUNCTIONS
# ===========================================================================


def get_active_disasters(
    event_types: Optional[list[str]] = None,
    alert_levels: Optional[list[str]] = None,
    limit: int = 50,
) -> GDACSResponse:
    """
    Fetches currently active disaster events from GDACS.

    Args:
        event_types:  List of event codes to filter (e.g. ["EQ", "FL", "TC"]).
                      Default: all types (EQ, TC, FL, VO, DR, WF, TS)
        alert_levels: List of alert levels (e.g. ["Red", "Orange"]).
                      Default: all levels
        limit:        Max events to return (default 50)

    Returns:
        GDACSResponse: Normalized container with list of GDACSEvent

    Example:
        >>> result = get_active_disasters(event_types=["FL", "TC"], alert_levels=["Red"])
        >>> print(result.total_fetched)
    """
    if event_types is None:
        event_types = ["EQ", "TC", "FL", "VO", "WF"]
    if alert_levels is None:
        alert_levels = ["Red", "Orange", "Green"]

    logger.info(f"[GDACSCTool] Fetching active disasters — types={event_types} levels={alert_levels} limit={limit}")

    params = {
        "eventtypes": ",".join(event_types),
        "alertlevel": ",".join(alert_levels),
        "limit":      limit,
    }

    events: list[GDACSEvent] = []

    try:
        # Try JSON API first
        resp = _get_with_retry(API_BASE_URL, params=params)
        data = resp.json()

        # GDACS API returns {"features": [...]} GeoJSON or a list
        raw_events = []
        if isinstance(data, list):
            raw_events = data
        elif isinstance(data, dict):
            if "features" in data:
                # GeoJSON FeatureCollection
                for feature in data["features"]:
                    props = feature.get("properties", {})
                    geom = feature.get("geometry", {})
                    if geom and geom.get("coordinates"):
                        coords = geom["coordinates"]
                        props["_lon"] = coords[0] if len(coords) > 0 else None
                        props["_lat"] = coords[1] if len(coords) > 1 else None
                    raw_events.append(props)
            elif "items" in data:
                raw_events = data["items"]
            else:
                raw_events = [data]

        for item in raw_events:
            event = _parse_api_event(item)
            if event:
                events.append(event)

    except Exception as e:
        logger.warning(f"[GDACSCTool] JSON API failed ({e}), falling back to RSS feed")
        try:
            resp = _get_with_retry(RSS_FEED_URL)
            events = _parse_rss_feed(resp.text)

            # Apply filters manually on RSS results
            if event_types:
                events = [e for e in events if e.event_type in event_types]
            if alert_levels:
                events = [e for e in events if e.alert_level in alert_levels]
            events = events[:limit]

        except Exception as rss_err:
            logger.error(f"[GDACSCTool] RSS fallback also failed: {rss_err}")
            return GDACSResponse(
                query_type="active_disasters",
                total_fetched=0,
                events=[],
            )

    result = GDACSResponse(
        query_type="active_disasters",
        total_fetched=len(events),
        events=events,
    )

    logger.success(f"[GDACSCTool] Fetched {result.total_fetched} active disaster events")
    return result


def get_disaster_by_country(
    country_name: str,
    event_types: Optional[list[str]] = None,
    limit: int = 20,
) -> GDACSResponse:
    """
    Fetches GDACS disaster events for a specific country.

    Args:
        country_name: Country name to filter (e.g. "India", "Bangladesh")
        event_types:  Optional event type filter (e.g. ["FL", "EQ"])
        limit:        Max events (default 20)

    Returns:
        GDACSResponse: Events filtered by country

    Example:
        >>> india_events = get_disaster_by_country("India", event_types=["FL"])
        >>> for e in india_events.events:
        ...     print(e.title, e.alert_level)
    """
    logger.info(f"[GDACSCTool] Fetching disasters for country='{country_name}' types={event_types}")

    # Fetch all active disasters, then filter by country
    all_result = get_active_disasters(event_types=event_types, limit=200)

    # Filter by country (case-insensitive partial match)
    country_lower = country_name.lower()
    filtered = [
        e for e in all_result.events
        if country_lower in e.country.lower()
    ][:limit]

    result = GDACSResponse(
        query_type=f"by_country:{country_name}",
        total_fetched=len(filtered),
        events=filtered,
    )

    logger.success(f"[GDACSCTool] Found {result.total_fetched} events for '{country_name}'")
    return result


def get_high_alert_disasters(limit: int = 20) -> GDACSResponse:
    """
    Convenience function: returns only Red and Orange alert disasters.

    Args:
        limit: Max events (default 20)

    Returns:
        GDACSResponse: High-priority disaster events only

    Used by:
        - command_center.py → dashboard critical alerts panel
        - severity_agent.py → initial triage
    """
    logger.info(f"[GDACSCTool] Fetching high-alert disasters (Red + Orange, limit={limit})")
    return get_active_disasters(
        alert_levels=["Red", "Orange"],
        limit=limit,
    )
