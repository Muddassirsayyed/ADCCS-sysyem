"""
ADCC — Resource Tool
======================
Queries physical disaster response resources directly from the PostgreSQL database.

No external API — reads from local ADCC database (resources, ndrf_units tables).

Used by (future):
    - allocation_agent.py  → finds available resources near a disaster zone
    - shelter_agent.py     → checks NDRF unit availability
    - resource_tool        → exposes resource data to LangGraph workflow nodes
    - command_center.py    → real-time resource status dashboard

Functions:
    get_available_resources(resource_type)      → list[ResourceRecord]
    get_resources_by_type(resource_type)        → list[ResourceRecord]
    get_resources_by_city(city)                 → list[ResourceRecord]
    get_ndrf_units(status)                      → list[ResourceRecord]
    get_resources_near(lat, lon, radius_km)     → list[ResourceRecord]
    get_resource_summary()                      → ResourceSummary
"""

import math
from datetime import datetime, timezone
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database.models import Resource, ResourceStatus, ResourceType
from database.postgres import SessionLocal


# ===========================================================================
# PYDANTIC MODELS
# ===========================================================================


class ResourceRecord(BaseModel):
    """Normalized resource record returned by all resource_tool functions."""

    id: str = Field(..., description="UUID of the resource")
    resource_name: str
    resource_type: str
    status: str
    quantity: int

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Computed field (populated by get_resources_near)
    distance_km: Optional[float] = Field(None, description="Distance from query point (km)")

    last_updated: datetime
    is_available: bool = Field(..., description="True if status == Available")

    class Config:
        from_attributes = True


class ResourceSummary(BaseModel):
    """Aggregated resource availability summary for command_center dashboard."""

    total_resources: int
    available_count: int
    busy_count: int
    maintenance_count: int

    # Breakdown by type
    boats_available: int = 0
    ambulances_available: int = 0
    medical_teams_available: int = 0
    rescue_teams_available: int = 0
    ndrf_units_available: int = 0
    helicopters_available: int = 0
    food_trucks_available: int = 0

    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ===========================================================================
# INTERNAL HELPERS
# ===========================================================================


def _get_session() -> Session:
    """Creates a new database session for tool use (outside FastAPI request context)."""
    return SessionLocal()


def _resource_to_record(r: Resource, distance_km: Optional[float] = None) -> ResourceRecord:
    """Converts a SQLAlchemy Resource ORM object to a ResourceRecord Pydantic model."""
    return ResourceRecord(
        id=str(r.id),
        resource_name=r.resource_name,
        resource_type=r.resource_type.value,
        status=r.status.value,
        quantity=r.quantity,
        latitude=r.latitude,
        longitude=r.longitude,
        distance_km=round(distance_km, 2) if distance_km is not None else None,
        last_updated=r.last_updated,
        is_available=(r.status == ResourceStatus.AVAILABLE),
    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two points using Haversine formula.

    Returns:
        Distance in kilometres
    """
    R = 6371.0  # Earth radius km
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat / 2) ** 2
         + math.cos(math.radians(lat1))
         * math.cos(math.radians(lat2))
         * math.sin(d_lon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ===========================================================================
# PUBLIC FUNCTIONS
# ===========================================================================


def get_available_resources(
    resource_type: Optional[str] = None,
) -> list[ResourceRecord]:
    """
    Returns all resources with status = Available.

    Args:
        resource_type: Optional filter by type (e.g. "Boat", "Ambulance", "NDRF Unit").
                       Pass None to get all available resources.

    Returns:
        list[ResourceRecord]: Available resources, ordered by resource_name

    Example:
        >>> boats = get_available_resources(resource_type="Boat")
        >>> print(len(boats), "boats available")
    """
    logger.info(f"[ResourceTool] Fetching available resources (type={resource_type or 'all'})")

    db: Session = _get_session()
    try:
        query = db.query(Resource).filter(Resource.status == ResourceStatus.AVAILABLE)

        if resource_type:
            # Match enum value string (e.g. "Boat" → ResourceType.BOAT)
            matched_type = _resolve_resource_type(resource_type)
            if matched_type:
                query = query.filter(Resource.resource_type == matched_type)
            else:
                logger.warning(f"[ResourceTool] Unknown resource_type '{resource_type}', returning all available")

        resources = query.order_by(Resource.resource_name).all()
        result = [_resource_to_record(r) for r in resources]

        logger.success(f"[ResourceTool] Found {len(result)} available resources")
        return result

    except Exception as e:
        logger.error(f"[ResourceTool] DB error in get_available_resources: {e}")
        return []
    finally:
        db.close()


def get_resources_by_type(
    resource_type: str,
    status: Optional[str] = None,
) -> list[ResourceRecord]:
    """
    Fetches all resources of a given type, with optional status filter.

    Args:
        resource_type: Resource type string (e.g. "Boat", "Ambulance", "Medical Team",
                       "Rescue Team", "Helicopter", "Food Truck", "NDRF Unit")
        status:        Optional status filter ("Available", "Busy", "Maintenance")

    Returns:
        list[ResourceRecord]: Resources of given type

    Example:
        >>> ndrf_units = get_resources_by_type("NDRF Unit")
        >>> available_boats = get_resources_by_type("Boat", status="Available")
    """
    logger.info(f"[ResourceTool] Fetching resources type='{resource_type}' status={status}")

    db: Session = _get_session()
    try:
        matched_type = _resolve_resource_type(resource_type)
        if not matched_type:
            logger.error(f"[ResourceTool] Invalid resource_type: '{resource_type}'")
            logger.info(f"[ResourceTool] Valid types: {[t.value for t in ResourceType]}")
            return []

        query = db.query(Resource).filter(Resource.resource_type == matched_type)

        if status:
            matched_status = _resolve_resource_status(status)
            if matched_status:
                query = query.filter(Resource.status == matched_status)

        resources = query.order_by(Resource.status, Resource.resource_name).all()
        result = [_resource_to_record(r) for r in resources]

        logger.success(f"[ResourceTool] Found {len(result)} '{resource_type}' resources")
        return result

    except Exception as e:
        logger.error(f"[ResourceTool] DB error in get_resources_by_type: {e}")
        return []
    finally:
        db.close()


def get_resources_by_city(
    city: str,
    status: Optional[str] = None,
) -> list[ResourceRecord]:
    """
    Fetches resources located in or near a given city.

    Note: City matching is based on resource_name containing the city name
    (e.g. "NDRF 5th Bn Unit-A" doesn't have explicit city, so this function
    uses a coordinate bounding box approach for future enhancement).
    For now, it matches city names in the resource_name field.

    Args:
        city:   City name (e.g. "Mumbai", "Delhi", "Chennai")
        status: Optional status filter ("Available", "Busy", "Maintenance")

    Returns:
        list[ResourceRecord]: Resources in the given city

    Example:
        >>> mumbai_resources = get_resources_by_city("Mumbai")
        >>> available_in_delhi = get_resources_by_city("Delhi", status="Available")
    """
    logger.info(f"[ResourceTool] Fetching resources in city='{city}' status={status}")

    db: Session = _get_session()
    try:
        # City bounding boxes for major Indian cities (rough lat/lon boxes)
        city_boxes = {
            "Mumbai":    (18.85, 19.35, 72.75, 73.05),
            "Delhi":     (28.40, 28.90, 76.90, 77.50),
            "Pune":      (18.40, 18.65, 73.70, 74.05),
            "Nagpur":    (21.05, 21.25, 78.95, 79.20),
            "Bengaluru": (12.80, 13.15, 77.45, 77.80),
            "Chennai":   (12.90, 13.25, 80.10, 80.35),
            "Hyderabad": (17.30, 17.55, 78.35, 78.60),
            "Kolkata":   (22.45, 22.70, 88.25, 88.50),
        }

        query = db.query(Resource)

        city_key = next((k for k in city_boxes if k.lower() == city.lower()), None)
        if city_key:
            min_lat, max_lat, min_lon, max_lon = city_boxes[city_key]
            # Filter by coordinate bounding box
            query = query.filter(
                Resource.latitude.isnot(None),
                Resource.longitude.isnot(None),
                Resource.latitude.between(min_lat, max_lat),
                Resource.longitude.between(min_lon, max_lon),
            )
        else:
            # Fallback: text search in resource_name
            logger.warning(f"[ResourceTool] City '{city}' not in bounding box list, searching by name")
            query = query.filter(Resource.resource_name.ilike(f"%{city}%"))

        if status:
            matched_status = _resolve_resource_status(status)
            if matched_status:
                query = query.filter(Resource.status == matched_status)

        resources = query.order_by(Resource.status, Resource.resource_name).all()
        result = [_resource_to_record(r) for r in resources]

        logger.success(f"[ResourceTool] Found {len(result)} resources in '{city}'")
        return result

    except Exception as e:
        logger.error(f"[ResourceTool] DB error in get_resources_by_city: {e}")
        return []
    finally:
        db.close()


def get_ndrf_units(
    status: Optional[str] = None,
) -> list[ResourceRecord]:
    """
    Fetches all NDRF (National Disaster Response Force) units.

    Args:
        status: Optional status filter ("Available", "Busy", "Maintenance")

    Returns:
        list[ResourceRecord]: NDRF unit records

    Example:
        >>> ndrf_available = get_ndrf_units(status="Available")
        >>> print(f"{len(ndrf_available)} NDRF units ready for deployment")
    """
    logger.info(f"[ResourceTool] Fetching NDRF units (status={status or 'all'})")
    return get_resources_by_type("NDRF Unit", status=status)


def get_resources_near(
    latitude: float,
    longitude: float,
    radius_km: float = 200.0,
    resource_type: Optional[str] = None,
    status: Optional[str] = "Available",
) -> list[ResourceRecord]:
    """
    Finds resources within a given radius of a disaster location.
    Sorted by distance (nearest first).

    Args:
        latitude:      Disaster zone latitude
        longitude:     Disaster zone longitude
        radius_km:     Search radius in km (default 200km)
        resource_type: Optional type filter
        status:        Status filter (default "Available")

    Returns:
        list[ResourceRecord]: Resources sorted by distance ascending

    Used by:
        - allocation_agent.py → finds nearest deployable resources

    Example:
        >>> # Find boats within 150km of Chennai flood zone
        >>> boats = get_resources_near(13.0827, 80.2707, radius_km=150, resource_type="Boat")
    """
    logger.info(
        f"[ResourceTool] Finding resources within {radius_km}km of ({latitude:.4f}, {longitude:.4f}) "
        f"type={resource_type or 'all'} status={status}"
    )

    db: Session = _get_session()
    try:
        query = db.query(Resource).filter(
            Resource.latitude.isnot(None),
            Resource.longitude.isnot(None),
        )

        if resource_type:
            matched_type = _resolve_resource_type(resource_type)
            if matched_type:
                query = query.filter(Resource.resource_type == matched_type)

        if status:
            matched_status = _resolve_resource_status(status)
            if matched_status:
                query = query.filter(Resource.status == matched_status)

        resources = query.all()

        # Compute distances and filter by radius
        result: list[ResourceRecord] = []
        for r in resources:
            if r.latitude is not None and r.longitude is not None:
                dist = _haversine_km(latitude, longitude, r.latitude, r.longitude)
                if dist <= radius_km:
                    record = _resource_to_record(r, distance_km=dist)
                    result.append(record)

        # Sort by distance (nearest first)
        result.sort(key=lambda x: x.distance_km or 0)

        logger.success(
            f"[ResourceTool] Found {len(result)} resources within {radius_km}km "
            f"of ({latitude:.4f}, {longitude:.4f})"
        )
        return result

    except Exception as e:
        logger.error(f"[ResourceTool] DB error in get_resources_near: {e}")
        return []
    finally:
        db.close()


def get_resource_summary() -> ResourceSummary:
    """
    Returns an aggregated summary of all resource availability.
    Used by the command_center dashboard and reporting agents.

    Returns:
        ResourceSummary: Counts by status and type

    Example:
        >>> summary = get_resource_summary()
        >>> print(f"Available: {summary.available_count}/{summary.total_resources}")
    """
    logger.info("[ResourceTool] Computing resource availability summary")

    db: Session = _get_session()
    try:
        all_resources = db.query(Resource).all()

        total = len(all_resources)
        available = [r for r in all_resources if r.status == ResourceStatus.AVAILABLE]
        busy = [r for r in all_resources if r.status == ResourceStatus.BUSY]
        maintenance = [r for r in all_resources if r.status == ResourceStatus.MAINTENANCE]

        def count_available_by_type(rt: ResourceType) -> int:
            return sum(1 for r in available if r.resource_type == rt)

        summary = ResourceSummary(
            total_resources=total,
            available_count=len(available),
            busy_count=len(busy),
            maintenance_count=len(maintenance),
            boats_available=count_available_by_type(ResourceType.BOAT),
            ambulances_available=count_available_by_type(ResourceType.AMBULANCE),
            medical_teams_available=count_available_by_type(ResourceType.MEDICAL_TEAM),
            rescue_teams_available=count_available_by_type(ResourceType.RESCUE_TEAM),
            ndrf_units_available=count_available_by_type(ResourceType.NDRF_UNIT),
            helicopters_available=count_available_by_type(ResourceType.HELICOPTER),
            food_trucks_available=count_available_by_type(ResourceType.FOOD_TRUCK),
        )

        logger.success(
            f"[ResourceTool] Summary: {summary.available_count}/{summary.total_resources} available | "
            f"Boats={summary.boats_available} NDRF={summary.ndrf_units_available}"
        )
        return summary

    except Exception as e:
        logger.error(f"[ResourceTool] DB error in get_resource_summary: {e}")
        return ResourceSummary(
            total_resources=0,
            available_count=0,
            busy_count=0,
            maintenance_count=0,
        )
    finally:
        db.close()


# ===========================================================================
# ENUM RESOLUTION HELPERS
# ===========================================================================

def _resolve_resource_type(type_str: str) -> Optional[ResourceType]:
    """
    Resolves a string to a ResourceType enum value.
    Case-insensitive, handles common aliases.

    Args:
        type_str: Human string like "Boat", "NDRF Unit", "medical team"

    Returns:
        ResourceType enum value or None if not found
    """
    normalized = type_str.strip().lower()
    mapping = {
        "boat":         ResourceType.BOAT,
        "ambulance":    ResourceType.AMBULANCE,
        "medical team": ResourceType.MEDICAL_TEAM,
        "medical":      ResourceType.MEDICAL_TEAM,
        "rescue team":  ResourceType.RESCUE_TEAM,
        "rescue":       ResourceType.RESCUE_TEAM,
        "helicopter":   ResourceType.HELICOPTER,
        "food truck":   ResourceType.FOOD_TRUCK,
        "food":         ResourceType.FOOD_TRUCK,
        "ndrf unit":    ResourceType.NDRF_UNIT,
        "ndrf":         ResourceType.NDRF_UNIT,
    }
    result = mapping.get(normalized)
    if not result:
        logger.warning(f"[ResourceTool] Could not resolve type '{type_str}'. Valid: {list(mapping.keys())}")
    return result


def _resolve_resource_status(status_str: str) -> Optional[ResourceStatus]:
    """
    Resolves a string to ResourceStatus enum value.

    Args:
        status_str: "Available", "Busy", or "Maintenance"

    Returns:
        ResourceStatus or None
    """
    normalized = status_str.strip().lower()
    mapping = {
        "available":   ResourceStatus.AVAILABLE,
        "busy":        ResourceStatus.BUSY,
        "maintenance": ResourceStatus.MAINTENANCE,
    }
    result = mapping.get(normalized)
    if not result:
        logger.warning(f"[ResourceTool] Could not resolve status '{status_str}'")
    return result
