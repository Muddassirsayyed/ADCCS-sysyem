"""
ADCC — SQLAlchemy 2.0 ORM Models
==================================
Production-grade database schema for the Autonomous Disaster Command Center.

Tables (10 total):
    Core:       Disaster, Resource, Hospital, Shelter, Alert
    AI Support: DataSource, ApiSyncLog, VerificationLog, ResourceAllocation, SimulationRun

Future Compatibility:
    - LangGraph workflows      → workflows/graph.py, workflows/nodes.py
    - LangChain tools          → tools/weather_tool.py, tools/gdacs_tool.py
    - Verification Agent       → agents/verification_agent.py  (uses VerificationLog)
    - Allocation Agent         → agents/allocation_agent.py    (uses ResourceAllocation)
    - Severity Agent           → agents/severity_agent.py      (uses Disaster.confidence_score)
    - Replanning Agent         → agents/replanning_agent.py    (uses DisasterStatus)
    - Digital Twin             → services/simulation_engine.py (uses SimulationRun)
    - AI Command Center        → agents/command_center.py      (reads all tables)
    - RAG Knowledge Base       → uses source_url fields for document retrieval

External Data Sources (future):
    Weather:            https://open-meteo.com
    Disaster Alerts:    https://www.gdacs.org
    Earthquakes:        https://earthquake.usgs.gov/fdsnws/event/1
    Hospitals/Shelters: https://overpass-api.de
    Maps:               https://www.openstreetmap.org
    Routes:             https://openrouteservice.org
    Satellite:          https://www.sentinel-hub.com
    NASA EarthData:     https://earthdata.nasa.gov
    India Gov Data:     https://data.gov.in
    Gemini AI:          https://ai.google.dev
"""

import enum
import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.postgres import Base


# ===========================================================================
# ENUMS
# ===========================================================================


class DisasterType(str, enum.Enum):
    """Types of natural disasters tracked by ADCC."""
    FLOOD = "Flood"
    CYCLONE = "Cyclone"
    EARTHQUAKE = "Earthquake"
    WILDFIRE = "Wildfire"
    HEATWAVE = "Heatwave"
    LANDSLIDE = "Landslide"


class SeverityLevel(str, enum.Enum):
    """
    Severity scoring used by severity_agent.py.
    Also used for Alerts.
    """
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class DisasterStatus(str, enum.Enum):
    """
    Lifecycle status of a disaster event.
    replanning_agent.py triggers on ACTIVE disasters.
    """
    ACTIVE = "Active"
    MONITORING = "Monitoring"
    RESOLVED = "Resolved"
    ARCHIVED = "Archived"


class ResourceType(str, enum.Enum):
    """Types of physical resources available for disaster response."""
    BOAT = "Boat"
    AMBULANCE = "Ambulance"
    MEDICAL_TEAM = "Medical Team"
    RESCUE_TEAM = "Rescue Team"
    HELICOPTER = "Helicopter"
    FOOD_TRUCK = "Food Truck"
    NDRF_UNIT = "NDRF Unit"


class ResourceStatus(str, enum.Enum):
    """Current operational status of a resource."""
    AVAILABLE = "Available"
    BUSY = "Busy"
    MAINTENANCE = "Maintenance"


class SourceType(str, enum.Enum):
    """
    Identifies which external API or system provided the data.
    Used by gdacs_tool.py, weather_tool.py, disaster_tool.py, news_tool.py.
    """
    GDACS = "GDACS"
    USGS = "USGS"
    OPENMETEO = "OpenMeteo"
    NEWSAPI = "NewsAPI"
    NASA = "NASA"
    SENTINEL = "Sentinel"
    NDMA = "NDMA"
    MANUAL = "Manual"


class VerificationStatus(str, enum.Enum):
    """
    Verification lifecycle managed by verification_agent.py.
    UNVERIFIED → PENDING → VERIFIED / REJECTED
    """
    UNVERIFIED = "Unverified"
    PENDING = "Pending"
    VERIFIED = "Verified"
    REJECTED = "Rejected"


class DataSourceStatus(str, enum.Enum):
    """Operational health status of an external API data source."""
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    ERROR = "Error"


class SyncStatus(str, enum.Enum):
    """Result status of an API sync operation."""
    SUCCESS = "Success"
    FAILED = "Failed"
    PARTIAL = "Partial"
    RUNNING = "Running"


class AllocationStatus(str, enum.Enum):
    """Lifecycle of a resource allocation managed by allocation_agent.py."""
    ACTIVE = "Active"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


# ===========================================================================
# TABLE 1: Disaster
# Source: GDACS, USGS, OpenMeteo, NDMA, Manual reports
# Used by: severity_agent, verification_agent, allocation_agent, replanning_agent
# ===========================================================================


class Disaster(Base):
    """
    Core disaster event record.

    Populated by:
        - data_collection_agent.py (via gdacs_tool, usgs_tool, weather_tool)
        - Manual entry via POST /api/disasters

    Updated by:
        - severity_agent.py        → severity, confidence_score
        - verification_agent.py    → verification_status, last_verified_at
        - replanning_agent.py      → status transitions
    """

    __tablename__ = "disasters"

    # ── Primary Key ─────────────────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="UUID primary key — globally unique disaster identifier"
    )

    # ── Core Fields ─────────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Human-readable disaster title, e.g. 'Mumbai Coastal Flooding'"
    )
    disaster_type: Mapped[DisasterType] = mapped_column(
        SAEnum(DisasterType, name="disastertype", create_type=True),
        nullable=False,
        comment="Type of disaster (Flood, Cyclone, Earthquake, etc.)"
    )
    severity: Mapped[SeverityLevel] = mapped_column(
        SAEnum(SeverityLevel, name="severitylevel", create_type=True),
        nullable=False,
        comment="Set by severity_agent.py based on affected population and confidence"
    )
    status: Mapped[DisasterStatus] = mapped_column(
        SAEnum(DisasterStatus, name="disasterstatus", create_type=True),
        default=DisasterStatus.ACTIVE, nullable=False,
        comment="Disaster lifecycle: Active → Monitoring → Resolved → Archived"
    )

    # ── Geolocation ─────────────────────────────────────────────────────────
    latitude: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Epicenter or impact zone latitude (WGS84)"
    )
    longitude: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Epicenter or impact zone longitude (WGS84)"
    )

    # ── Impact Metrics ───────────────────────────────────────────────────────
    affected_population: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Estimated number of people affected — used by severity_agent"
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0.0–1.0 confidence score assigned by confidence_engine.py"
    )

    # ── Source Tracking ──────────────────────────────────────────────────────
    # Used by RAG Knowledge Base and verification_agent.py
    source: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
        comment="Human-readable source name, e.g. 'GDACS Alert #1234'"
    )
    source_type: Mapped[Optional[SourceType]] = mapped_column(
        SAEnum(SourceType, name="sourcetype", create_type=True),
        nullable=True,
        comment="API/system that provided this disaster data"
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="Direct URL to the source record (for RAG & verification)"
    )

    # ── Verification ─────────────────────────────────────────────────────────
    # Managed by verification_agent.py
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SAEnum(VerificationStatus, name="verificationstatus", create_type=True),
        default=VerificationStatus.UNVERIFIED, nullable=False,
        comment="Set by verification_agent.py after cross-source validation"
    )
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp of last verification check by verification_agent.py"
    )

    # ── Timestamps ───────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    # ── Relationships ────────────────────────────────────────────────────────
    verification_logs: Mapped[List["VerificationLog"]] = relationship(
        "VerificationLog", back_populates="disaster", cascade="all, delete-orphan"
    )
    allocations: Mapped[List["ResourceAllocation"]] = relationship(
        "ResourceAllocation", back_populates="disaster", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Disaster '{self.title}' [{self.disaster_type.value} | {self.severity.value}]>"


# ===========================================================================
# TABLE 2: Resource
# Used by: allocation_agent.py, resource_tool.py
# ===========================================================================


class Resource(Base):
    """
    Physical disaster response resource (boat, ambulance, team, etc.).

    Managed by:
        - allocation_agent.py → status changes, linked via ResourceAllocation
        - resource_tool.py    → queries available resources by type/location
    """

    __tablename__ = "resources"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    resource_name: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Name/identifier, e.g. 'NDRF Boat MH-07'"
    )
    resource_type: Mapped[ResourceType] = mapped_column(
        SAEnum(ResourceType, name="resourcetype", create_type=True),
        nullable=False
    )
    status: Mapped[ResourceStatus] = mapped_column(
        SAEnum(ResourceStatus, name="resourcestatus", create_type=True),
        default=ResourceStatus.AVAILABLE, nullable=False,
        comment="Real-time status updated by allocation_agent.py"
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="Number of units (e.g. 3 boats in one entry)"
    )

    # Geolocation — for route_tool.py distance calculations
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False
    )

    # Relationships
    allocations: Mapped[List["ResourceAllocation"]] = relationship(
        "ResourceAllocation", back_populates="resource"
    )

    def __repr__(self) -> str:
        return f"<Resource '{self.resource_name}' [{self.resource_type.value} | {self.status.value}]>"


# ===========================================================================
# TABLE 3: Hospital
# Source: https://overpass-api.de (OpenStreetMap)
# Used by: allocation_agent.py, shelter_agent.py
# ===========================================================================


class Hospital(Base):
    """
    Hospital facility with bed capacity tracking.

    Data Source: OpenStreetMap / Overpass API (https://overpass-api.de)
    Used by: allocation_agent.py to route injured to nearest hospitals.
    """

    __tablename__ = "hospitals"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    total_beds: Mapped[int] = mapped_column(Integer, nullable=False)
    available_beds: Mapped[int] = mapped_column(Integer, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<Hospital '{self.name}' [{self.city}] — {self.available_beds}/{self.total_beds} beds>"


# ===========================================================================
# TABLE 4: Shelter
# Source: https://overpass-api.de (OpenStreetMap)
# Used by: shelter_agent.py
# ===========================================================================


class Shelter(Base):
    """
    Emergency shelter with capacity tracking.

    Data Source: OpenStreetMap / Overpass API (https://overpass-api.de)
    Used by: shelter_agent.py to assign displaced people to nearest shelter.
    """

    __tablename__ = "shelters"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return f"<Shelter '{self.name}' [{self.city}] — {self.occupied}/{self.capacity} occupied>"


# ===========================================================================
# TABLE 5: Alert
# Source: GDACS, USGS, NDMA, NewsAPI, Manual
# Used by: notification_tool.py, command_center.py
# ===========================================================================


class Alert(Base):
    """
    System or external alert/warning record.

    Created by:
        - data_collection_agent.py (from GDACS, USGS, NDMA feeds)
        - severity_agent.py (auto-generated on severity escalation)
        - Manual entry via POST /api/alerts

    Used by:
        - notification_tool.py → Twilio SMS/WhatsApp delivery
        - command_center.py    → Real-time dashboard display
    """

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[SeverityLevel] = mapped_column(
        SAEnum(SeverityLevel, name="severitylevel", create_type=False),
        nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Source tracking
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_type: Mapped[Optional[SourceType]] = mapped_column(
        SAEnum(SourceType, name="sourcetype", create_type=False),
        nullable=True,
        comment="API source that generated this alert"
    )
    source_url: Mapped[Optional[str]] = mapped_column(
        String(500), nullable=True,
        comment="Direct URL to original alert for RAG retrieval"
    )
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True,
        comment="0.0–1.0 reliability score from confidence_engine.py"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<Alert '{self.title}' [{self.severity.value}]>"


# ===========================================================================
# TABLE 6: DataSource
# Purpose: Registry of all external APIs used by ADCC tools/agents
# Used by: all tools in tools/, ApiSyncLog
# ===========================================================================


class DataSource(Base):
    """
    Registry of external APIs and data sources used by ADCC.

    Each tool in tools/ should have a corresponding DataSource entry.
    ApiSyncLog references DataSource by source_name for health tracking.

    Seed entries:
        GDACS, USGS, OpenMeteo, NewsAPI, NASA EarthData,
        Sentinel Hub, OpenStreetMap, Overpass API, OpenRouteService,
        Data.gov.in, Gemini API
    """

    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True,
        comment="Unique source name, e.g. 'GDACS'"
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="sourcetype", create_type=False),
        nullable=False
    )
    base_url: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="Base API URL for the external service"
    )
    status: Mapped[DataSourceStatus] = mapped_column(
        SAEnum(DataSourceStatus, name="datasourcestatus", create_type=True),
        default=DataSourceStatus.ACTIVE, nullable=False
    )
    last_sync: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="Timestamp of the most recent successful sync"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="What this source provides and how it is used in ADCC"
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<DataSource '{self.name}' [{self.status.value}]>"


# ===========================================================================
# TABLE 7: ApiSyncLog
# Purpose: Track API health and sync history for all external sources
# Used by: all tools in tools/, monitoring dashboard
# ===========================================================================


class ApiSyncLog(Base):
    """
    Log of every API sync attempt — success, failure, partial results.

    Created by:
        - weather_tool.py, gdacs_tool.py, news_tool.py, disaster_tool.py
          after each data fetch attempt.

    Used by:
        - command_center.py → API health status panel
        - replanning_agent.py → detect stale/failed data sources
    """

    __tablename__ = "api_sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Name of the DataSource synced, e.g. 'GDACS'"
    )
    sync_status: Mapped[SyncStatus] = mapped_column(
        SAEnum(SyncStatus, name="syncstatus", create_type=True),
        nullable=False
    )
    records_fetched: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True,
        comment="Number of records retrieved in this sync"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Error details if sync_status is FAILED or PARTIAL"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        comment="When the sync operation started"
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
        comment="When the sync completed (null if still RUNNING)"
    )

    def __repr__(self) -> str:
        return f"<ApiSyncLog '{self.source_name}' [{self.sync_status.value}] fetched={self.records_fetched}>"


# ===========================================================================
# TABLE 8: VerificationLog
# Purpose: Multi-source cross-verification records for each disaster
# Used by: verification_agent.py
# ===========================================================================


class VerificationLog(Base):
    """
    Records each verification check performed by verification_agent.py.

    One disaster can have multiple VerificationLogs (one per source checked).
    The agent aggregates these to update Disaster.verification_status.

    Workflow:
        verification_agent.py
            → Checks GDACS, USGS, NewsAPI for the disaster
            → Creates one VerificationLog per source
            → Updates Disaster.verification_status based on consensus
    """

    __tablename__ = "verification_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    disaster_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("disasters.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to Disaster — which event was being verified"
    )
    source_checked: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Which source was checked, e.g. 'GDACS', 'USGS', 'NewsAPI'"
    )
    result: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="Outcome: 'Confirmed', 'Denied', 'Inconclusive'"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="0.0–1.0 confidence score for this source's verification result"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Agent reasoning or source excerpt"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationship
    disaster: Mapped["Disaster"] = relationship("Disaster", back_populates="verification_logs")

    def __repr__(self) -> str:
        return f"<VerificationLog disaster={self.disaster_id} source='{self.source_checked}' result='{self.result}'>"


# ===========================================================================
# TABLE 9: ResourceAllocation
# Purpose: Tracks which resources were deployed to which disaster
# Used by: allocation_agent.py
# ===========================================================================


class ResourceAllocation(Base):
    """
    Links a Resource to a Disaster — records every allocation decision.

    Created/updated by:
        - allocation_agent.py → decides and records resource deployment
        - replanning_agent.py → can cancel/modify allocations on new info

    Used by:
        - resource_tool.py   → checks if resource is already allocated
        - command_center.py  → displays active deployments
    """

    __tablename__ = "resource_allocations"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    disaster_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("disasters.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to the Disaster this resource is deployed for"
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("resources.id", ondelete="CASCADE"),
        nullable=False,
        comment="FK to the Resource being allocated"
    )
    quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        comment="How many units of this resource are allocated"
    )
    allocation_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Agent's reasoning for this allocation decision (LangGraph node output)"
    )
    status: Mapped[AllocationStatus] = mapped_column(
        SAEnum(AllocationStatus, name="allocationstatus", create_type=True),
        default=AllocationStatus.ACTIVE, nullable=False
    )
    allocated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    disaster: Mapped["Disaster"] = relationship("Disaster", back_populates="allocations")
    resource: Mapped["Resource"] = relationship("Resource", back_populates="allocations")

    def __repr__(self) -> str:
        return f"<ResourceAllocation disaster={self.disaster_id} resource={self.resource_id} qty={self.quantity}>"


# ===========================================================================
# TABLE 10: SimulationRun
# Purpose: Digital Twin simulation scenarios
# Used by: services/simulation_engine.py, dashboard/pages/command_center.py
# ===========================================================================


class SimulationRun(Base):
    """
    Records each Digital Twin simulation run with its parameters and outcome.

    Created by:
        - services/simulation_engine.py → runs scenario simulations
        - dashboard/pages/command_center.py → user-triggered simulations

    Used by:
        - replanning_agent.py → what-if analysis for disaster response
        - AI Command Center   → scenario comparison dashboard

    Parameters represent delta values (change from current state):
        rainfall_change    → e.g., +50 means 50mm additional rainfall
        wind_speed_change  → e.g., +30 means 30 km/h increase in wind
        population_change  → e.g., +10000 means 10,000 more people in zone
    """

    __tablename__ = "simulation_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scenario_name: Mapped[str] = mapped_column(
        String(255), nullable=False,
        comment="Descriptive name, e.g. 'Mumbai Flood — High Rainfall Surge'"
    )

    # Simulation input parameters (delta values)
    rainfall_change: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Change in rainfall (mm) from baseline"
    )
    wind_speed_change: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Change in wind speed (km/h) from baseline"
    )
    population_change: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Change in affected population count"
    )

    # Output
    result_summary: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON or text summary of simulation outcome from simulation_engine.py"
    )
    predicted_severity: Mapped[Optional[SeverityLevel]] = mapped_column(
        SAEnum(SeverityLevel, name="severitylevel", create_type=False),
        nullable=True,
        comment="Predicted severity level based on simulation output"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<SimulationRun '{self.scenario_name}'>"
