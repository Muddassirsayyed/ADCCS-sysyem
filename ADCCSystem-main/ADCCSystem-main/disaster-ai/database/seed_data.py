"""
ADCC — Database Seed Data
==========================
Populates the PostgreSQL database with realistic India-based disaster data.

Run this script directly:
    python -m database.seed_data

Or import and call:
    from database.seed_data import seed_all
    seed_all()

Seed Counts:
    Disasters:  20  (10 Floods, 5 Cyclones, 5 Earthquakes)
    Resources:  30  (10 Boats, 5 Ambulances, 5 Medical Teams, 5 Rescue Teams, 5 NDRF Units)
    Hospitals:  20  (real India hospitals)
    Shelters:   20  (real India shelter locations)
    Alerts:     15  (mix of severity levels)
    DataSources: 11 (all external APIs used by ADCC tools)

Cities Covered:
    Mumbai, Delhi, Pune, Nagpur, Bengaluru, Chennai, Hyderabad, Kolkata,
    Assam, Bihar, Kerala, Uttarakhand, Gujarat, Odisha, Andhra Pradesh
"""

import sys
import uuid
from datetime import datetime, timedelta, timezone

from loguru import logger

from database.postgres import SessionLocal, create_tables
from database.models import (
    Alert,
    AllocationStatus,
    ApiSyncLog,
    DataSource,
    DataSourceStatus,
    Disaster,
    DisasterStatus,
    DisasterType,
    Hospital,
    Resource,
    ResourceAllocation,
    ResourceStatus,
    ResourceType,
    SeverityLevel,
    Shelter,
    SimulationRun,
    SourceType,
    SyncStatus,
    VerificationLog,
    VerificationStatus,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def now() -> datetime:
    return datetime.now(timezone.utc)


def days_ago(n: int) -> datetime:
    return now() - timedelta(days=n)


def hours_ago(n: int) -> datetime:
    return now() - timedelta(hours=n)


# ===========================================================================
# DISASTERS — 20 total
# ===========================================================================

DISASTERS = [
    # ── 10 Floods ────────────────────────────────────────────────────────────
    {
        "title": "Mumbai Coastal Flooding — Mithi River Overflow",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.CRITICAL,
        "status": DisasterStatus.ACTIVE,
        "latitude": 19.0760, "longitude": 72.8777,
        "affected_population": 450000,
        "confidence_score": 0.93,
        "source": "NDMA Alert #2024-MH-001",
        "source_type": SourceType.NDMA,
        "source_url": "https://ndma.gov.in/alerts/2024/MH-001",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(2),
        "created_at": days_ago(1),
    },
    {
        "title": "Assam Brahmaputra River Floods",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.CRITICAL,
        "status": DisasterStatus.ACTIVE,
        "latitude": 26.1445, "longitude": 91.7362,
        "affected_population": 820000,
        "confidence_score": 0.96,
        "source": "GDACS FL-20240612-ASM",
        "source_type": SourceType.GDACS,
        "source_url": "https://www.gdacs.org/report.aspx?eventid=1234&eventtype=FL",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(1),
        "created_at": days_ago(3),
    },
    {
        "title": "Bihar Ganga Plains Flash Flood",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.ACTIVE,
        "latitude": 25.5941, "longitude": 85.1376,
        "affected_population": 310000,
        "confidence_score": 0.88,
        "source": "NDMA Alert #2024-BR-002",
        "source_type": SourceType.NDMA,
        "source_url": "https://ndma.gov.in/alerts/2024/BR-002",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(4),
        "created_at": days_ago(2),
    },
    {
        "title": "Kerala Wayanad District Flash Flood",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.MONITORING,
        "latitude": 11.6854, "longitude": 76.1320,
        "affected_population": 95000,
        "confidence_score": 0.85,
        "source": "Open-Meteo Rainfall Alert",
        "source_type": SourceType.OPENMETEO,
        "source_url": "https://open-meteo.com/en/docs#latitude=11.6854&longitude=76.1320",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(6),
        "created_at": days_ago(1),
    },
    {
        "title": "Chennai Adyar River Urban Flooding",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.ACTIVE,
        "latitude": 13.0827, "longitude": 80.2707,
        "affected_population": 280000,
        "confidence_score": 0.91,
        "source": "NDMA Alert #2024-TN-003",
        "source_type": SourceType.NDMA,
        "source_url": "https://ndma.gov.in/alerts/2024/TN-003",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(3),
        "created_at": days_ago(2),
    },
    {
        "title": "Kolkata Hooghly River Flooding",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.MEDIUM,
        "status": DisasterStatus.MONITORING,
        "latitude": 22.5726, "longitude": 88.3639,
        "affected_population": 125000,
        "confidence_score": 0.79,
        "source": "NewsAPI Report",
        "source_type": SourceType.NEWSAPI,
        "source_url": "https://newsapi.org/v2/everything?q=kolkata+flood+2024",
        "verification_status": VerificationStatus.PENDING,
        "last_verified_at": None,
        "created_at": days_ago(1),
    },
    {
        "title": "Odisha Mahanadi River Flood",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.CRITICAL,
        "status": DisasterStatus.ACTIVE,
        "latitude": 20.4625, "longitude": 85.8830,
        "affected_population": 560000,
        "confidence_score": 0.94,
        "source": "GDACS FL-20240611-OD",
        "source_type": SourceType.GDACS,
        "source_url": "https://www.gdacs.org/report.aspx?eventid=1235&eventtype=FL",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(2),
        "created_at": days_ago(4),
    },
    {
        "title": "Uttarakhand Rishikesh Flash Flood",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.ACTIVE,
        "latitude": 30.0869, "longitude": 78.2676,
        "affected_population": 42000,
        "confidence_score": 0.87,
        "source": "NDMA Alert #2024-UK-004",
        "source_type": SourceType.NDMA,
        "source_url": "https://ndma.gov.in/alerts/2024/UK-004",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(5),
        "created_at": days_ago(1),
    },
    {
        "title": "Gujarat Ahmedabad Urban Waterlogging",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.MEDIUM,
        "status": DisasterStatus.MONITORING,
        "latitude": 23.0225, "longitude": 72.5714,
        "affected_population": 89000,
        "confidence_score": 0.76,
        "source": "Open-Meteo Heavy Rain Alert",
        "source_type": SourceType.OPENMETEO,
        "source_url": "https://open-meteo.com/en/docs#latitude=23.0225&longitude=72.5714",
        "verification_status": VerificationStatus.UNVERIFIED,
        "last_verified_at": None,
        "created_at": hours_ago(12),
    },
    {
        "title": "Andhra Pradesh Krishna River Flooding",
        "disaster_type": DisasterType.FLOOD,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.ACTIVE,
        "latitude": 16.5062, "longitude": 80.6480,
        "affected_population": 195000,
        "confidence_score": 0.89,
        "source": "NDMA Alert #2024-AP-005",
        "source_type": SourceType.NDMA,
        "source_url": "https://ndma.gov.in/alerts/2024/AP-005",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(3),
        "created_at": days_ago(2),
    },

    # ── 5 Cyclones ────────────────────────────────────────────────────────────
    {
        "title": "Cyclone Tauktae — Maharashtra Coastline",
        "disaster_type": DisasterType.CYCLONE,
        "severity": SeverityLevel.CRITICAL,
        "status": DisasterStatus.ACTIVE,
        "latitude": 19.2183, "longitude": 72.9781,
        "affected_population": 750000,
        "confidence_score": 0.97,
        "source": "GDACS TC-20240610-TAUKTAE",
        "source_type": SourceType.GDACS,
        "source_url": "https://www.gdacs.org/report.aspx?eventid=1001&eventtype=TC",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(1),
        "created_at": days_ago(1),
    },
    {
        "title": "Cyclone Amphan — West Bengal Coast",
        "disaster_type": DisasterType.CYCLONE,
        "severity": SeverityLevel.CRITICAL,
        "status": DisasterStatus.MONITORING,
        "latitude": 22.5726, "longitude": 88.3639,
        "affected_population": 1200000,
        "confidence_score": 0.98,
        "source": "GDACS TC-20240608-AMPHAN",
        "source_type": SourceType.GDACS,
        "source_url": "https://www.gdacs.org/report.aspx?eventid=1002&eventtype=TC",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(2),
        "created_at": days_ago(5),
    },
    {
        "title": "Cyclone Biparjoy — Gujarat Coast",
        "disaster_type": DisasterType.CYCLONE,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.RESOLVED,
        "latitude": 22.3072, "longitude": 68.9680,
        "affected_population": 430000,
        "confidence_score": 0.95,
        "source": "GDACS TC-20240601-BIPARJOY",
        "source_type": SourceType.GDACS,
        "source_url": "https://www.gdacs.org/report.aspx?eventid=1003&eventtype=TC",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": days_ago(2),
        "created_at": days_ago(8),
    },
    {
        "title": "Cyclone Nisarga — Raigad Maharashtra",
        "disaster_type": DisasterType.CYCLONE,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.MONITORING,
        "latitude": 18.2437, "longitude": 73.1355,
        "affected_population": 210000,
        "confidence_score": 0.92,
        "source": "GDACS TC-20240605-NISARGA",
        "source_type": SourceType.GDACS,
        "source_url": "https://www.gdacs.org/report.aspx?eventid=1004&eventtype=TC",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(6),
        "created_at": days_ago(3),
    },
    {
        "title": "Cyclone Yaas — Odisha Balasore",
        "disaster_type": DisasterType.CYCLONE,
        "severity": SeverityLevel.CRITICAL,
        "status": DisasterStatus.ACTIVE,
        "latitude": 21.4942, "longitude": 86.9319,
        "affected_population": 890000,
        "confidence_score": 0.96,
        "source": "GDACS TC-20240609-YAAS",
        "source_type": SourceType.GDACS,
        "source_url": "https://www.gdacs.org/report.aspx?eventid=1005&eventtype=TC",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(1),
        "created_at": days_ago(2),
    },

    # ── 5 Earthquakes ─────────────────────────────────────────────────────────
    {
        "title": "Gujarat Bhuj Earthquake M5.8",
        "disaster_type": DisasterType.EARTHQUAKE,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.ACTIVE,
        "latitude": 23.2419, "longitude": 69.6669,
        "affected_population": 180000,
        "confidence_score": 0.99,
        "source": "USGS EQ-20240612-001",
        "source_type": SourceType.USGS,
        "source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000ABCD",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(1),
        "created_at": hours_ago(8),
    },
    {
        "title": "Uttarakhand Chamoli Earthquake M5.2",
        "disaster_type": DisasterType.EARTHQUAKE,
        "severity": SeverityLevel.MEDIUM,
        "status": DisasterStatus.MONITORING,
        "latitude": 30.4021, "longitude": 79.3586,
        "affected_population": 35000,
        "confidence_score": 0.98,
        "source": "USGS EQ-20240611-002",
        "source_type": SourceType.USGS,
        "source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000EFGH",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(4),
        "created_at": days_ago(1),
    },
    {
        "title": "Manipur Imphal Earthquake M5.5",
        "disaster_type": DisasterType.EARTHQUAKE,
        "severity": SeverityLevel.HIGH,
        "status": DisasterStatus.ACTIVE,
        "latitude": 24.8170, "longitude": 93.9368,
        "affected_population": 67000,
        "confidence_score": 0.97,
        "source": "USGS EQ-20240610-003",
        "source_type": SourceType.USGS,
        "source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000IJKL",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(3),
        "created_at": days_ago(2),
    },
    {
        "title": "Jammu Kashmir Earthquake M4.8",
        "disaster_type": DisasterType.EARTHQUAKE,
        "severity": SeverityLevel.MEDIUM,
        "status": DisasterStatus.MONITORING,
        "latitude": 34.0837, "longitude": 74.7973,
        "affected_population": 28000,
        "confidence_score": 0.95,
        "source": "USGS EQ-20240609-004",
        "source_type": SourceType.USGS,
        "source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000MNOP",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": hours_ago(8),
        "created_at": days_ago(2),
    },
    {
        "title": "Andaman Islands Earthquake M5.1",
        "disaster_type": DisasterType.EARTHQUAKE,
        "severity": SeverityLevel.LOW,
        "status": DisasterStatus.MONITORING,
        "latitude": 11.7401, "longitude": 92.6586,
        "affected_population": 12000,
        "confidence_score": 0.96,
        "source": "USGS EQ-20240608-005",
        "source_type": SourceType.USGS,
        "source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000QRST",
        "verification_status": VerificationStatus.VERIFIED,
        "last_verified_at": days_ago(1),
        "created_at": days_ago(3),
    },
]


# ===========================================================================
# RESOURCES — 30 total
# ===========================================================================

RESOURCES = [
    # 10 Boats
    {"resource_name": "NDRF Rescue Boat MH-01", "resource_type": ResourceType.BOAT, "status": ResourceStatus.AVAILABLE, "quantity": 2, "latitude": 19.0760, "longitude": 72.8777},
    {"resource_name": "NDRF Rescue Boat MH-02", "resource_type": ResourceType.BOAT, "status": ResourceStatus.AVAILABLE, "quantity": 1, "latitude": 19.0596, "longitude": 72.8656},
    {"resource_name": "Coast Guard Inflatable Boat KL-01", "resource_type": ResourceType.BOAT, "status": ResourceStatus.BUSY, "quantity": 3, "latitude": 18.9220, "longitude": 72.8347},
    {"resource_name": "SDRF Flood Boat WB-01", "resource_type": ResourceType.BOAT, "status": ResourceStatus.AVAILABLE, "quantity": 2, "latitude": 22.5726, "longitude": 88.3639},
    {"resource_name": "SDRF Flood Boat WB-02", "resource_type": ResourceType.BOAT, "status": ResourceStatus.AVAILABLE, "quantity": 1, "latitude": 22.5851, "longitude": 88.3467},
    {"resource_name": "NDRF Motor Boat TN-01", "resource_type": ResourceType.BOAT, "status": ResourceStatus.MAINTENANCE, "quantity": 2, "latitude": 13.0827, "longitude": 80.2707},
    {"resource_name": "River Rescue Boat OR-01", "resource_type": ResourceType.BOAT, "status": ResourceStatus.AVAILABLE, "quantity": 4, "latitude": 20.4625, "longitude": 85.8830},
    {"resource_name": "Flood Rescue Boat KA-01", "resource_type": ResourceType.BOAT, "status": ResourceStatus.AVAILABLE, "quantity": 2, "latitude": 12.9716, "longitude": 77.5946},
    {"resource_name": "Emergency Boat MH-03", "resource_type": ResourceType.BOAT, "status": ResourceStatus.BUSY, "quantity": 1, "latitude": 19.2183, "longitude": 72.9781},
    {"resource_name": "Patrol Boat AP-01", "resource_type": ResourceType.BOAT, "status": ResourceStatus.AVAILABLE, "quantity": 3, "latitude": 17.3850, "longitude": 78.4867},
    # 5 Ambulances
    {"resource_name": "CATS Ambulance MH-001", "resource_type": ResourceType.AMBULANCE, "status": ResourceStatus.AVAILABLE, "quantity": 1, "latitude": 19.0760, "longitude": 72.8777},
    {"resource_name": "108 Emergency Ambulance DL-001", "resource_type": ResourceType.AMBULANCE, "status": ResourceStatus.BUSY, "quantity": 1, "latitude": 28.6139, "longitude": 77.2090},
    {"resource_name": "CATS Ambulance KA-001", "resource_type": ResourceType.AMBULANCE, "status": ResourceStatus.AVAILABLE, "quantity": 1, "latitude": 12.9716, "longitude": 77.5946},
    {"resource_name": "GVK EMRI Ambulance TN-001", "resource_type": ResourceType.AMBULANCE, "status": ResourceStatus.AVAILABLE, "quantity": 1, "latitude": 13.0827, "longitude": 80.2707},
    {"resource_name": "108 Ambulance TS-001", "resource_type": ResourceType.AMBULANCE, "status": ResourceStatus.MAINTENANCE, "quantity": 1, "latitude": 17.3850, "longitude": 78.4867},
    # 5 Medical Teams
    {"resource_name": "NDRF Medical Team MH-Alpha", "resource_type": ResourceType.MEDICAL_TEAM, "status": ResourceStatus.AVAILABLE, "quantity": 12, "latitude": 19.0760, "longitude": 72.8777},
    {"resource_name": "Army Medical Corps Team DL-Bravo", "resource_type": ResourceType.MEDICAL_TEAM, "status": ResourceStatus.BUSY, "quantity": 15, "latitude": 28.6139, "longitude": 77.2090},
    {"resource_name": "AIIMS Rapid Response Team DL-Charlie", "resource_type": ResourceType.MEDICAL_TEAM, "status": ResourceStatus.AVAILABLE, "quantity": 8, "latitude": 28.5672, "longitude": 77.2100},
    {"resource_name": "Civil Medical Team KA-Delta", "resource_type": ResourceType.MEDICAL_TEAM, "status": ResourceStatus.AVAILABLE, "quantity": 10, "latitude": 12.9716, "longitude": 77.5946},
    {"resource_name": "GMCH Medical Team MH-Echo", "resource_type": ResourceType.MEDICAL_TEAM, "status": ResourceStatus.AVAILABLE, "quantity": 10, "latitude": 21.1458, "longitude": 79.0882},
    # 5 Rescue Teams
    {"resource_name": "NDRF Rescue Team MH-1", "resource_type": ResourceType.RESCUE_TEAM, "status": ResourceStatus.AVAILABLE, "quantity": 25, "latitude": 19.0760, "longitude": 72.8777},
    {"resource_name": "SDRF Rescue Team WB-1", "resource_type": ResourceType.RESCUE_TEAM, "status": ResourceStatus.BUSY, "quantity": 20, "latitude": 22.5726, "longitude": 88.3639},
    {"resource_name": "NDRF Rescue Team DL-1", "resource_type": ResourceType.RESCUE_TEAM, "status": ResourceStatus.AVAILABLE, "quantity": 25, "latitude": 28.6139, "longitude": 77.2090},
    {"resource_name": "Fire & Rescue Team TN-1", "resource_type": ResourceType.RESCUE_TEAM, "status": ResourceStatus.AVAILABLE, "quantity": 18, "latitude": 13.0827, "longitude": 80.2707},
    {"resource_name": "NDRF Rescue Team TS-1", "resource_type": ResourceType.RESCUE_TEAM, "status": ResourceStatus.MAINTENANCE, "quantity": 22, "latitude": 17.3850, "longitude": 78.4867},
    # 5 NDRF Units
    {"resource_name": "NDRF 5th Bn Unit-A", "resource_type": ResourceType.NDRF_UNIT, "status": ResourceStatus.AVAILABLE, "quantity": 45, "latitude": 18.5204, "longitude": 73.8567},
    {"resource_name": "NDRF 8th Bn Unit-B", "resource_type": ResourceType.NDRF_UNIT, "status": ResourceStatus.BUSY, "quantity": 45, "latitude": 28.6139, "longitude": 77.2090},
    {"resource_name": "NDRF 2nd Bn Unit-C", "resource_type": ResourceType.NDRF_UNIT, "status": ResourceStatus.AVAILABLE, "quantity": 45, "latitude": 22.5726, "longitude": 88.3639},
    {"resource_name": "NDRF 4th Bn Unit-D", "resource_type": ResourceType.NDRF_UNIT, "status": ResourceStatus.AVAILABLE, "quantity": 45, "latitude": 13.0827, "longitude": 80.2707},
    {"resource_name": "NDRF 12th Bn Unit-E", "resource_type": ResourceType.NDRF_UNIT, "status": ResourceStatus.AVAILABLE, "quantity": 45, "latitude": 19.0760, "longitude": 72.8777},
]


# ===========================================================================
# HOSPITALS — 20 total
# ===========================================================================

HOSPITALS = [
    {"name": "KEM Hospital", "city": "Mumbai", "total_beds": 1800, "available_beds": 320, "latitude": 19.0018, "longitude": 72.8425},
    {"name": "Nair Hospital", "city": "Mumbai", "total_beds": 1200, "available_beds": 210, "latitude": 19.0037, "longitude": 72.8379},
    {"name": "Sion Hospital", "city": "Mumbai", "total_beds": 1500, "available_beds": 280, "latitude": 19.0440, "longitude": 72.8647},
    {"name": "AIIMS Delhi", "city": "Delhi", "total_beds": 2478, "available_beds": 410, "latitude": 28.5672, "longitude": 77.2100},
    {"name": "Safdarjung Hospital", "city": "Delhi", "total_beds": 1531, "available_beds": 265, "latitude": 28.5676, "longitude": 77.2060},
    {"name": "Ram Manohar Lohia Hospital", "city": "Delhi", "total_beds": 1532, "available_beds": 310, "latitude": 28.6319, "longitude": 77.2090},
    {"name": "Sassoon General Hospital", "city": "Pune", "total_beds": 1400, "available_beds": 230, "latitude": 18.5204, "longitude": 73.8567},
    {"name": "Ruby Hall Clinic", "city": "Pune", "total_beds": 450, "available_beds": 95, "latitude": 18.5362, "longitude": 73.8956},
    {"name": "Government Medical College Nagpur", "city": "Nagpur", "total_beds": 1200, "available_beds": 185, "latitude": 21.1458, "longitude": 79.0882},
    {"name": "Lata Mangeshkar Hospital", "city": "Nagpur", "total_beds": 350, "available_beds": 72, "latitude": 21.1630, "longitude": 79.1090},
    {"name": "Victoria Hospital Bengaluru", "city": "Bengaluru", "total_beds": 1300, "available_beds": 198, "latitude": 12.9716, "longitude": 77.5946},
    {"name": "Bowring and Lady Curzon Hospital", "city": "Bengaluru", "total_beds": 850, "available_beds": 130, "latitude": 12.9784, "longitude": 77.6408},
    {"name": "Kidwai Memorial Institute", "city": "Bengaluru", "total_beds": 500, "available_beds": 88, "latitude": 12.9352, "longitude": 77.5942},
    {"name": "Rajiv Gandhi Government General Hospital", "city": "Chennai", "total_beds": 2700, "available_beds": 450, "latitude": 13.0827, "longitude": 80.2707},
    {"name": "Stanley Medical College Hospital", "city": "Chennai", "total_beds": 2500, "available_beds": 380, "latitude": 13.1067, "longitude": 80.2906},
    {"name": "Gandhi Hospital Hyderabad", "city": "Hyderabad", "total_beds": 1900, "available_beds": 310, "latitude": 17.4065, "longitude": 78.4772},
    {"name": "Osmania General Hospital", "city": "Hyderabad", "total_beds": 1200, "available_beds": 195, "latitude": 17.3616, "longitude": 78.4747},
    {"name": "SSKM Hospital Kolkata", "city": "Kolkata", "total_beds": 1850, "available_beds": 290, "latitude": 22.5354, "longitude": 88.3401},
    {"name": "NRS Medical College Hospital", "city": "Kolkata", "total_beds": 1200, "available_beds": 215, "latitude": 22.5580, "longitude": 88.3510},
    {"name": "RG Kar Medical College Hospital", "city": "Kolkata", "total_beds": 1100, "available_beds": 175, "latitude": 22.6017, "longitude": 88.3852},
]


# ===========================================================================
# SHELTERS — 20 total
# ===========================================================================

SHELTERS = [
    {"name": "Bandra Kurla Relief Camp", "city": "Mumbai", "capacity": 2000, "occupied": 850, "latitude": 19.0596, "longitude": 72.8656},
    {"name": "Dharavi Flood Shelter", "city": "Mumbai", "capacity": 1500, "occupied": 620, "latitude": 19.0432, "longitude": 72.8520},
    {"name": "Chhatrapati Shivaji Stadium Shelter", "city": "Mumbai", "capacity": 3000, "occupied": 1100, "latitude": 19.0760, "longitude": 72.8777},
    {"name": "Yamuna Flood Relief Camp", "city": "Delhi", "capacity": 2500, "occupied": 980, "latitude": 28.6692, "longitude": 77.2384},
    {"name": "Pragati Maidan Emergency Shelter", "city": "Delhi", "capacity": 4000, "occupied": 1560, "latitude": 28.6186, "longitude": 77.2413},
    {"name": "Rohini Disaster Relief Center", "city": "Delhi", "capacity": 1800, "occupied": 640, "latitude": 28.7206, "longitude": 77.1154},
    {"name": "Shivajinagar Relief Camp", "city": "Pune", "capacity": 1200, "occupied": 430, "latitude": 18.5308, "longitude": 73.8474},
    {"name": "Hadapsar Flood Shelter", "city": "Pune", "capacity": 900, "occupied": 290, "latitude": 18.4961, "longitude": 73.9319},
    {"name": "VNIT Relief Center", "city": "Nagpur", "capacity": 1100, "occupied": 320, "latitude": 21.1369, "longitude": 79.0518},
    {"name": "Kamptee Road Shelter", "city": "Nagpur", "capacity": 800, "occupied": 210, "latitude": 21.1667, "longitude": 79.1033},
    {"name": "Kanteerava Stadium Shelter", "city": "Bengaluru", "capacity": 2000, "occupied": 720, "latitude": 12.9793, "longitude": 77.5891},
    {"name": "Whitefield Relief Camp", "city": "Bengaluru", "capacity": 1500, "occupied": 490, "latitude": 12.9698, "longitude": 77.7499},
    {"name": "YMCA Ground Shelter Chennai", "city": "Chennai", "capacity": 2200, "occupied": 890, "latitude": 13.0602, "longitude": 80.2449},
    {"name": "Velachery Flood Relief Camp", "city": "Chennai", "capacity": 1800, "occupied": 660, "latitude": 12.9778, "longitude": 80.2216},
    {"name": "LB Nagar Emergency Shelter", "city": "Hyderabad", "capacity": 1600, "occupied": 530, "latitude": 17.3483, "longitude": 78.5494},
    {"name": "Kukatpally Relief Center", "city": "Hyderabad", "capacity": 2000, "occupied": 810, "latitude": 17.4947, "longitude": 78.3996},
    {"name": "Salt Lake Shelter", "city": "Kolkata", "capacity": 1700, "occupied": 590, "latitude": 22.5812, "longitude": 88.4298},
    {"name": "Howrah Bridge Relief Camp", "city": "Kolkata", "capacity": 2500, "occupied": 1050, "latitude": 22.5851, "longitude": 88.3467},
    {"name": "Brahmand Relief Center", "city": "Mumbai", "capacity": 1000, "occupied": 340, "latitude": 19.1665, "longitude": 72.9694},
    {"name": "Anna Nagar Shelter", "city": "Chennai", "capacity": 1300, "occupied": 420, "latitude": 13.0850, "longitude": 80.2101},
]


# ===========================================================================
# ALERTS — 15 total
# ===========================================================================

ALERTS = [
    {"title": "Red Alert: Cyclone Tauktae Landfall Imminent", "severity": SeverityLevel.CRITICAL, "message": "Cyclone Tauktae expected to make landfall near Mumbai coast within 6 hours. Wind speeds 180 km/h. Evacuate coastal areas immediately.", "source": "IMD", "source_type": SourceType.GDACS, "source_url": "https://www.gdacs.org/report.aspx?eventid=1001&eventtype=TC", "confidence_score": 0.97},
    {"title": "Orange Alert: Brahmaputra River Flood Warning", "severity": SeverityLevel.HIGH, "message": "Brahmaputra river levels 3.2m above danger mark. Flash flood warning for Guwahati, Dibrugarh, Jorhat districts.", "source": "CWC India", "source_type": SourceType.NDMA, "source_url": "https://ndma.gov.in/alerts/assam-flood-2024", "confidence_score": 0.94},
    {"title": "Critical: Mumbai M5.8 Seismic Activity Detected", "severity": SeverityLevel.HIGH, "message": "USGS confirms M5.8 earthquake 45km off Mumbai coast. Tsunami watch NOT issued. Check for structural damage.", "source": "USGS", "source_type": SourceType.USGS, "source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000ABCD", "confidence_score": 0.99},
    {"title": "Red Alert: Cyclone Yaas Category 4 Intensification", "severity": SeverityLevel.CRITICAL, "message": "Cyclone Yaas has intensified to Category 4. Expected landfall near Balasore, Odisha. 500,000 evacuated.", "source": "GDACS", "source_type": SourceType.GDACS, "source_url": "https://www.gdacs.org/report.aspx?eventid=1005&eventtype=TC", "confidence_score": 0.96},
    {"title": "Flash Flood Warning: Kerala Wayanad", "severity": SeverityLevel.HIGH, "message": "Extreme rainfall (280mm in 24hrs) causing flash floods in Wayanad district. 95,000 residents at risk.", "source": "Open-Meteo", "source_type": SourceType.OPENMETEO, "source_url": "https://open-meteo.com/en/docs", "confidence_score": 0.85},
    {"title": "Resource Shortage Alert: Odisha Rescue Operations", "severity": SeverityLevel.HIGH, "message": "NDRF reports critical shortage of rescue boats in Odisha flood zones. 5 additional units requested from Maharashtra.", "source": "NDMA Operations Center", "source_type": SourceType.NDMA, "source_url": "https://ndma.gov.in/operations/odisha-2024", "confidence_score": 0.91},
    {"title": "Shelter Capacity Warning: Mumbai Camps Full", "severity": SeverityLevel.MEDIUM, "message": "3 of 4 designated relief camps in Mumbai have reached 85% capacity. Additional shelter facilities being activated.", "source": "BMC Mumbai", "source_type": SourceType.MANUAL, "source_url": None, "confidence_score": 0.88},
    {"title": "Earthquake Aftershock Warning: Gujarat Bhuj Area", "severity": SeverityLevel.MEDIUM, "message": "USGS monitoring system detected 12 aftershocks (M2.5-M3.8) following M5.8 event. Residents advised to stay outdoors.", "source": "USGS Aftershock Monitor", "source_type": SourceType.USGS, "source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000ABCD/aftershocks", "confidence_score": 0.96},
    {"title": "Satellite Alert: Sentinel-2 Detects Flood Expansion", "severity": SeverityLevel.HIGH, "message": "NASA Sentinel-2 imagery shows Chennai flood extent has grown 35% in last 6 hours. Adyar, Tambaram areas newly inundated.", "source": "Sentinel Hub / NASA", "source_type": SourceType.SENTINEL, "source_url": "https://www.sentinel-hub.com/explore/sentinelplayground", "confidence_score": 0.93},
    {"title": "Weather Alert: Extreme Rainfall Forecast Bihar", "severity": SeverityLevel.HIGH, "message": "Open-Meteo forecast: 200-250mm rainfall expected in Bihar over next 48 hours. Ganga river flood risk elevated.", "source": "Open-Meteo", "source_type": SourceType.OPENMETEO, "source_url": "https://open-meteo.com/en/docs#latitude=25.5941&longitude=85.1376", "confidence_score": 0.82},
    {"title": "Cyclone Amphan: Kolkata Landfall in 12 Hours", "severity": SeverityLevel.CRITICAL, "message": "Super Cyclone Amphan (190 km/h) will make landfall near Kolkata in 12 hours. All low-lying areas must evacuate NOW.", "source": "GDACS", "source_type": SourceType.GDACS, "source_url": "https://www.gdacs.org/report.aspx?eventid=1002&eventtype=TC", "confidence_score": 0.98},
    {"title": "Hospital Surge Warning: Delhi Hospitals at 90% Capacity", "severity": SeverityLevel.MEDIUM, "message": "Delhi disaster hospitals reporting 90% bed occupancy. Army Medical Corp deploying field hospital units.", "source": "Delhi Health Dept", "source_type": SourceType.MANUAL, "source_url": None, "confidence_score": 0.87},
    {"title": "Low Alert: Andaman Seismic Activity M4.2", "severity": SeverityLevel.LOW, "message": "Minor earthquake M4.2 detected near North Andaman Island. No significant damage reported. Tsunami risk: None.", "source": "USGS", "source_type": SourceType.USGS, "source_url": "https://earthquake.usgs.gov/earthquakes/eventpage/us7000QRST", "confidence_score": 0.98},
    {"title": "Supply Alert: Food & Medicine Shortage Assam Camps", "severity": SeverityLevel.MEDIUM, "message": "Flood relief camps in Assam running low on food rations and ORS packets. Air drop scheduled for tomorrow morning.", "source": "NDRF Operations", "source_type": SourceType.MANUAL, "source_url": None, "confidence_score": 0.89},
    {"title": "Landslide Risk: Uttarakhand NH-58 Blocked", "severity": SeverityLevel.HIGH, "message": "Heavy rainfall triggered landslide on NH-58 near Devprayag. Road blocked. 1200 pilgrims stranded. Air rescue initiated.", "source": "NDMA Alert", "source_type": SourceType.NDMA, "source_url": "https://ndma.gov.in/alerts/2024/UK-005", "confidence_score": 0.92},
]


# ===========================================================================
# DATA SOURCES — 11 external APIs
# ===========================================================================

DATA_SOURCES = [
    {
        "name": "GDACS",
        "source_type": SourceType.GDACS,
        "base_url": "https://www.gdacs.org",
        "status": DataSourceStatus.ACTIVE,
        "description": "Global Disaster Alert and Coordination System. Provides real-time alerts for floods, cyclones, earthquakes, tsunamis. Used by: gdacs_tool.py",
    },
    {
        "name": "USGS Earthquake API",
        "source_type": SourceType.USGS,
        "base_url": "https://earthquake.usgs.gov/fdsnws/event/1",
        "status": DataSourceStatus.ACTIVE,
        "description": "United States Geological Survey real-time earthquake data API. Used by: disaster_tool.py",
    },
    {
        "name": "Open-Meteo",
        "source_type": SourceType.OPENMETEO,
        "base_url": "https://open-meteo.com",
        "status": DataSourceStatus.ACTIVE,
        "description": "Free open-source weather API. Provides hourly and daily forecasts, historical data. Used by: weather_tool.py",
    },
    {
        "name": "NewsAPI",
        "source_type": SourceType.NEWSAPI,
        "base_url": "https://newsapi.org",
        "status": DataSourceStatus.ACTIVE,
        "description": "Real-time news aggregation API. Used to scrape disaster news for verification. Used by: news_tool.py",
    },
    {
        "name": "NASA EarthData",
        "source_type": SourceType.NASA,
        "base_url": "https://earthdata.nasa.gov",
        "status": DataSourceStatus.ACTIVE,
        "description": "NASA Earth science data portal. Provides satellite imagery, MODIS flood detection. Used by: satellite_tool.py",
    },
    {
        "name": "Sentinel Hub",
        "source_type": SourceType.SENTINEL,
        "base_url": "https://www.sentinel-hub.com",
        "status": DataSourceStatus.ACTIVE,
        "description": "Copernicus Sentinel satellite imagery processing. Flood extent mapping via NDWI analysis. Used by: satellite_tool.py",
    },
    {
        "name": "OpenStreetMap",
        "source_type": SourceType.MANUAL,
        "base_url": "https://www.openstreetmap.org",
        "status": DataSourceStatus.ACTIVE,
        "description": "Open geographic database. Hospital and shelter location data. Used by: overpass API queries",
    },
    {
        "name": "Overpass API",
        "source_type": SourceType.MANUAL,
        "base_url": "https://overpass-api.de",
        "status": DataSourceStatus.ACTIVE,
        "description": "OpenStreetMap data query API. Used to find hospitals, shelters, roads in affected areas.",
    },
    {
        "name": "OpenRouteService",
        "source_type": SourceType.MANUAL,
        "base_url": "https://openrouteservice.org",
        "status": DataSourceStatus.ACTIVE,
        "description": "Open-source routing engine. Calculates optimal rescue routes. Used by: route_tool.py",
    },
    {
        "name": "Data.gov.in",
        "source_type": SourceType.NDMA,
        "base_url": "https://data.gov.in",
        "status": DataSourceStatus.ACTIVE,
        "description": "Indian Government Open Data Portal. NDRF unit locations, disaster statistics. Used for India-specific resource data.",
    },
    {
        "name": "Gemini API",
        "source_type": SourceType.MANUAL,
        "base_url": "https://ai.google.dev",
        "status": DataSourceStatus.ACTIVE,
        "description": "Google Gemini LLM API. Used as the AI backbone for all ADCC agents via LangChain/LangGraph.",
    },
]


# ===========================================================================
# SEED FUNCTIONS
# ===========================================================================

def seed_disasters(db) -> list:
    """Inserts 20 disaster records and returns the created objects."""
    logger.info("Seeding disasters...")
    created = []
    for d in DISASTERS:
        disaster = Disaster(**d)
        db.add(disaster)
        created.append(disaster)
    db.flush()  # Get IDs without committing
    logger.info(f"  ✅ {len(created)} disasters inserted")
    return created


def seed_resources(db) -> list:
    """Inserts 30 resource records."""
    logger.info("Seeding resources...")
    created = []
    for r in RESOURCES:
        resource = Resource(**r)
        db.add(resource)
        created.append(resource)
    db.flush()
    logger.info(f"  ✅ {len(created)} resources inserted")
    return created


def seed_hospitals(db) -> None:
    """Inserts 20 hospital records."""
    logger.info("Seeding hospitals...")
    for h in HOSPITALS:
        db.add(Hospital(**h))
    logger.info(f"  ✅ {len(HOSPITALS)} hospitals inserted")


def seed_shelters(db) -> None:
    """Inserts 20 shelter records."""
    logger.info("Seeding shelters...")
    for s in SHELTERS:
        db.add(Shelter(**s))
    logger.info(f"  ✅ {len(SHELTERS)} shelters inserted")


def seed_alerts(db) -> None:
    """Inserts 15 alert records."""
    logger.info("Seeding alerts...")
    for a in ALERTS:
        db.add(Alert(**a))
    logger.info(f"  ✅ {len(ALERTS)} alerts inserted")


def seed_data_sources(db) -> None:
    """Inserts 11 external API data source records."""
    logger.info("Seeding data sources...")
    for ds in DATA_SOURCES:
        db.add(DataSource(**ds))
    logger.info(f"  ✅ {len(DATA_SOURCES)} data sources inserted")


def seed_sample_allocations(db, disasters: list, resources: list) -> None:
    """Creates 5 sample ResourceAllocation records linking disasters to resources."""
    logger.info("Seeding sample resource allocations...")
    sample_allocations = [
        ResourceAllocation(
            disaster_id=disasters[0].id,
            resource_id=resources[0].id,
            quantity=2,
            allocation_reason="Mumbai flooding requires immediate boat deployment for rescue operations",
            status=AllocationStatus.ACTIVE,
        ),
        ResourceAllocation(
            disaster_id=disasters[0].id,
            resource_id=resources[10].id,
            quantity=1,
            allocation_reason="Medical team dispatched to Mumbai flood zone — 320 injured reported",
            status=AllocationStatus.ACTIVE,
        ),
        ResourceAllocation(
            disaster_id=disasters[1].id,
            resource_id=resources[3].id,
            quantity=2,
            allocation_reason="Assam flood — boats from Kolkata SDRF deployed to Brahmaputra basin",
            status=AllocationStatus.ACTIVE,
        ),
        ResourceAllocation(
            disaster_id=disasters[10].id,
            resource_id=resources[25].id,
            quantity=45,
            allocation_reason="Cyclone Tauktae — NDRF 5th Bn deployed to Maharashtra coast",
            status=AllocationStatus.ACTIVE,
        ),
        ResourceAllocation(
            disaster_id=disasters[15].id,
            resource_id=resources[22].id,
            quantity=25,
            allocation_reason="Gujarat earthquake — rescue team dispatched from Delhi for structural search & rescue",
            status=AllocationStatus.COMPLETED,
        ),
    ]
    for alloc in sample_allocations:
        db.add(alloc)
    logger.info(f"  ✅ {len(sample_allocations)} resource allocations inserted")


def seed_sample_simulation(db) -> None:
    """Creates sample SimulationRun records for Digital Twin testing."""
    logger.info("Seeding sample simulation runs...")
    simulations = [
        SimulationRun(
            scenario_name="Mumbai Flood — High Rainfall Surge (+100mm)",
            rainfall_change=100.0,
            wind_speed_change=0.0,
            population_change=50000,
            result_summary='{"predicted_area_km2": 45, "additional_evacuations": 120000, "resources_needed": {"boats": 15, "rescue_teams": 8}}',
            predicted_severity=SeverityLevel.CRITICAL,
        ),
        SimulationRun(
            scenario_name="Cyclone Amphan — Wind Intensification Scenario",
            rainfall_change=50.0,
            wind_speed_change=30.0,
            population_change=0,
            result_summary='{"structural_damage_pct": 35, "hospital_surge": 8500, "shelter_deficit": 250000}',
            predicted_severity=SeverityLevel.CRITICAL,
        ),
        SimulationRun(
            scenario_name="Bihar Flood — Moderate Rainfall Scenario",
            rainfall_change=60.0,
            wind_speed_change=0.0,
            population_change=20000,
            result_summary='{"additional_villages_affected": 45, "road_blockages": 12, "relief_camps_needed": 6}',
            predicted_severity=SeverityLevel.HIGH,
        ),
    ]
    for sim in simulations:
        db.add(sim)
    logger.info(f"  ✅ {len(simulations)} simulation runs inserted")


def seed_api_sync_log(db) -> None:
    """Creates initial ApiSyncLog entries."""
    logger.info("Seeding API sync logs...")
    logs = [
        ApiSyncLog(source_name="GDACS", sync_status=SyncStatus.SUCCESS, records_fetched=12, started_at=hours_ago(2), completed_at=hours_ago(2) + timedelta(seconds=4)),
        ApiSyncLog(source_name="USGS Earthquake API", sync_status=SyncStatus.SUCCESS, records_fetched=5, started_at=hours_ago(1), completed_at=hours_ago(1) + timedelta(seconds=2)),
        ApiSyncLog(source_name="Open-Meteo", sync_status=SyncStatus.SUCCESS, records_fetched=20, started_at=hours_ago(1), completed_at=hours_ago(1) + timedelta(seconds=3)),
        ApiSyncLog(source_name="NewsAPI", sync_status=SyncStatus.PARTIAL, records_fetched=7, error_message="Rate limit hit after 7 records", started_at=hours_ago(3), completed_at=hours_ago(3) + timedelta(seconds=8)),
    ]
    for log in logs:
        db.add(log)
    logger.info(f"  ✅ {len(logs)} API sync logs inserted")


# ===========================================================================
# MAIN SEED FUNCTION
# ===========================================================================

def seed_all(reset: bool = False) -> None:
    """
    Main function to seed all data into the database.

    Args:
        reset: If True, drops and recreates all tables before seeding.
               ⚠️  WARNING: Only use in development!
    """
    logger.info("=" * 60)
    logger.info("🌱 ADCC Database Seeding Started")
    logger.info("=" * 60)

    # Create tables
    create_tables()

    db = SessionLocal()
    try:
        if reset:
            logger.warning("⚠️  Reset mode: clearing all existing data...")
            db.query(ApiSyncLog).delete()
            db.query(SimulationRun).delete()
            db.query(ResourceAllocation).delete()
            db.query(VerificationLog).delete()
            db.query(Alert).delete()
            db.query(DataSource).delete()
            db.query(Resource).delete()
            db.query(Hospital).delete()
            db.query(Shelter).delete()
            db.query(Disaster).delete()
            db.commit()
            logger.info("  ✅ All tables cleared")

        # Check if already seeded
        existing = db.query(Disaster).count()
        if existing > 0 and not reset:
            logger.warning(f"⚠️  Database already has {existing} disasters. Use reset=True to re-seed.")
            return

        # Seed in dependency order
        disasters = seed_disasters(db)
        resources = seed_resources(db)
        seed_hospitals(db)
        seed_shelters(db)
        seed_alerts(db)
        seed_data_sources(db)
        seed_sample_allocations(db, disasters, resources)
        seed_sample_simulation(db)
        seed_api_sync_log(db)

        db.commit()
        logger.info("=" * 60)
        logger.info("✅ Database seeding completed successfully!")
        logger.info(f"   Disasters:       {len(DISASTERS)}")
        logger.info(f"   Resources:       {len(RESOURCES)}")
        logger.info(f"   Hospitals:       {len(HOSPITALS)}")
        logger.info(f"   Shelters:        {len(SHELTERS)}")
        logger.info(f"   Alerts:          {len(ALERTS)}")
        logger.info(f"   Data Sources:    {len(DATA_SOURCES)}")
        logger.info(f"   Allocations:     5 (sample)")
        logger.info(f"   Simulations:     3 (sample)")
        logger.info(f"   API Sync Logs:   4 (sample)")
        logger.info("=" * 60)

    except Exception as e:
        db.rollback()
        logger.error(f"❌ Seeding failed: {e}")
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Run directly: python -m database.seed_data
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    reset_flag = "--reset" in sys.argv
    seed_all(reset=reset_flag)
