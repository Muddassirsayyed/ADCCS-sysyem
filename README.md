# Disaster-AI 🌋🛡️

Disaster-AI is an intelligent agentic system designed for automated disaster monitoring, verification, severity assessment, resource allocation, and real-time response orchestration.

---

## 📂 Project Structure

Below is the directory layout of the `disaster-ai` system:

```text
disaster-ai/
│
├── app.py                      # Main application entry point
│
├── agents/                     # Multi-agent orchestrators
│   ├── data_collection_agent.py # Agent for gathering external feeds
│   ├── verification_agent.py    # Agent for validating incidents
│   ├── severity_agent.py        # Agent for assessing impact & severity
│   ├── allocation_agent.py      # Agent for dispatching resources
│   ├── shelter_agent.py         # Agent for managing evacuation & shelter capacity
│   ├── replanning_agent.py      # Agent for dynamic path & resource adjustments
│   └── command_center.py        # Central coordination agent
│
├── tools/                      # API wrappers and integration tools
│   ├── weather_tool.py          # Weather updates and forecasting APIs
│   ├── news_tool.py             # Global/local news ingestion tool
│   ├── disaster_tool.py         # Specialized disaster data streams
│   ├── satellite_tool.py        # Satellite imagery and analysis tools
│   ├── gdacs_tool.py            # Global Disaster Alert and Coordination System
│   ├── route_tool.py            # Routing and distance calculations (e.g., OSRM, Google Maps)
│   ├── notification_tool.py     # SMS, Email, and Push alert systems
│   ├── resource_tool.py         # Resource tracking and inventory lookup
│   └── social_media_tool.py     # Social media scraping and NLP analysis
│
├── workflows/                  # LangGraph-based workflow orchestrations
│   ├── graph.py                 # Graph definition and state machine routing
│   ├── state.py                 # State definitions and context management
│   └── nodes.py                 # Core node execution steps
│
├── services/                   # Business logic engines
│   ├── confidence_engine.py     # Algorithms to score incident report reliability
│   ├── prediction_engine.py     # AI models for impact and hazard prediction
│   ├── normalizer.py            # Raw data normalization and standardization
│   └── simulation_engine.py     # Disaster impact scenario simulator
│
├── database/                   # Database schemas and connections
│   ├── models.py                # Database tables and ORM definitions
│   ├── seed_data.py             # Mock data for bootstrapping the system
│   └── postgres.py              # PostgreSQL database client and connection pool
│
├── dashboard/                  # Frontend user interface
│   ├── pages/                   # Main dashboard view components
│   │   ├── incidents.py         # Incident tracking & management screen
│   │   ├── resources.py         # Resource mapping & supply levels
│   │   ├── maps.py              # Geospatial visualization layer
│   │   └── command_center.py    # Live operation center control panel
│   └── components/              # Shared UI widgets and reusable elements
│
├── data/                       # Local static datasets
│   ├── shelters.csv             # Database of relief camp locations & capacities
│   ├── hospitals.csv            # Hospital coordinates and bed availability
│   ├── ndrf_units.csv           # Locations of National Disaster Response Force teams
│   └── resources.csv            # Emergency materials inventory list
│
├── tests/                      # Automated test suite
│
├── requirements.txt            # Python dependencies
│
└── README.md                   # Project documentation (this file)
```

---

## 🤖 Agents and Responsibilities

1. **`data_collection_agent.py`**
   - Continuously monitors live data streams using integration tools (weather, news, satellite, disaster APIs, and social media feeds) to identify potential emergency signals.
   
2. **`verification_agent.py`**
   - Corroborates reports across multiple data sources using the **Confidence Engine** to filter out false alarms and duplicates.

3. **`severity_agent.py`**
   - Evaluates the magnitude, population exposure, and critical infrastructure risk using prediction and simulation engines.

4. **`allocation_agent.py`**
   - Computes optimal distribution of relief packages, medical supplies, and personnel based on NDRF coordinates.

5. **`shelter_agent.py`**
   - Monitors shelter occupancy, routes evacuees to the nearest safe zones, and handles capacity forecasting.

6. **`replanning_agent.py`**
   - Runs continuously during an active crisis to recalculate routes and re-allocate resources if routes become blocked or conditions worsen.

7. **`command_center.py`**
   - Serves as the master orchestrator, synthesizing decisions from all sub-agents and displaying them on the live operator dashboard.

---

## 🛠️ Integrated Tools

* **Weather Tool:** Ingests live meteorological data, cyclone tracking, and rainfall levels.
* **News & Social Media Tools:** Monitors news sites and platform feeds for hyper-local incident updates.
* **Satellite & GDACS Tools:** Integrates global alert systems and processes satellite images to detect floods, landslides, and wildfire perimeters.
* **Route & Resource Tools:** Plans evacuation routes and manages inventory availability at warehouse centers.

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL database

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/disaster-ai.git
   cd disaster-ai
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Initialize the database and run seed data:
   ```bash
   python database/seed_data.py
   ```
4. Run the main application:
   ```bash
   python app.py
   ```
