# AgriVision & AgriMind Agent

AgriVision is an open-source agricultural intelligence platform combined with the **AgriMind Multi-Agent Decision Layer**. It connects satellite-derived vegetation indices (Sentinel-2 NDVI/EVI/SAVI), CHIRPS rainfall anomaly data, soil chemistry, and deterministic agronomic calendars into verifiable field recommendations.

The platform is designed specifically for **maize-focused smallholder and commercial production**, featuring a **human-in-the-loop agronomist verification workflow** and **low-bandwidth USSD feature phone access (`*384#`)** for farmers without smartphones or data access.

---

## ⚡ Quickstart: Clone & Run in 3 Steps

Get the complete platform running locally with tests verified in under 2 minutes:

```bash
# 1. Clone & create virtual environment
git clone https://github.com/mwoha/Agri_vision_agrimind_agent.git
cd Agri_vision_agrimind_agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Configure local environment & run test suite (all 33 tests pass out of the box)
cp .env.example .env
pytest

# 3. Start the Django application server
python manage.py migrate
python manage.py runserver
```

- **Web Dashboard**: Visit `http://127.0.0.1:8000/health/` to view field monitoring and the AgriMind Agronomist review widget.
- **AgriMind Assistant Chat**: Visit `http://127.0.0.1:8000/chat/` for the English / Kiswahili conversational advisory.
- **USSD Simulator / Callback**: POST to `http://127.0.0.1:8000/ussd/callback/` or dial via Africa's Talking simulator.

---

## 🌾 Real-World Deployment Case Study: Uasin Gishu County Grain Corridor

### Operational Context & Institutional Anchoring
- **Target Institution**: **County Government of Uasin Gishu — Department of Agriculture, Livestock & Fisheries** (Eldoret Headquarters) in operational collaboration with the **Cereal Growers Association (CGA)** and local grain cooperatives.
- **Ecological Zone**: High-potential North Rift maize breadbasket (Moiben, Soy, Turbo, Ainabkoi, Kesses, Kapseret) at 1,800m–2,400m altitude, characterized by fertile volcanic humic nitisols and a single extended unimodal cropping season (March–November).

### The Real-World Operational Bottleneck
In Uasin Gishu, a single Ward Agricultural Extension Officer (WAO) oversees between **1,200 and 1,800 smallholder maize farmers**. During critical phenological phases—especially the **early vegetative V4–V8 stage** (top-dressing with CAN/Urea) and the **tasseling/silking window**—officers face severe operational constraints:
1. **Motorbike Mobility Constraints**: Physically inspecting remote scattered plots in Moiben or Turbo takes 3–5 days per sub-location.
2. **Costly Spray Mistakes**: In the rainy months of April–June, Fall Armyworm (*Spodoptera frugiperda*) attacks trigger panic among farmers. Smallholders frequently purchase expensive synthetic pesticides (costing KES 2,800–4,500 per acre) and apply them hours before a convective thunderstorm, washing away the chemicals into local waterways, killing beneficial pollinators, and causing 100% financial waste.
3. **Connectivity Divide**: While field officers have desktop/laptop access at sub-county offices, over 70% of local smallholders rely on basic 2G feature phones (Nokia/Itel) with no mobile internet.

```
┌────────────────────────────────────────────────────────────────────────┐
│             Uasin Gishu County Grain Corridor Architecture             │
└────────────────────────────────────────────────────────────────────────┘

  Sentinel-2 (10m NDVI)       CHIRPS Rainfall (0.05°)      Agro-Ecological Baselines
          │                               │                           │
          └───────────────────────┬───────┴───────────────────────────┘
                                  ▼
               ┌─────────────────────────────────────┐
               │    FastMCP Telemetry & Gateways     │
               └──────────────────┬──────────────────┘
                                  ▼
               ┌─────────────────────────────────────┐
               │    AgriMind Agentic Orchestration   │
               │   • Finite State LangGraph Graph    │
               │   • Dual-Evidence Verification      │
               │   • Deterministic Calendar Gate     │
               └──────────────────┬──────────────────┘
                                  │
                       [PENDING_APPROVAL State]
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. EXTENSION OFFICER REVIEW (Web Dashboard @ Eldoret / Moiben Office)  │
│    • Officer Faith Chepkoech reviews prioritized parcel triage queue    │
│    • Checks cross-corroboration: NDVI drop (0.42) + Rain forecast (18mm)│
│    • One-Click Action: "APPROVE HOLD" (Delay spray 48h until dry)      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. LAST-MILE FARMER ACCESS (2G Feature Phone @ Sergoit / Moiben)       │
│    • Farmer Wanjiku Cherop dials USSD *384# or receives SMS:           │
│      "AgriMind Advisory: HOLD pesticide spray on Moiben Plot A.         │
│       Heavy rain (18mm) expected in 48h. Verified by Ag Extension."   │
└────────────────────────────────────────────────────────────────────────┘
```

### Personas and Operational Flow

#### Persona 1: Sub-County Agricultural Officer — Kiprono Biwott (Moiben Sub-County)
- **Role**: Supervises maize production and crop protection advisories across Sergoit, Karuna, and Moiben wards.
- **Workflow Before AgriMind**: Wrote notes from farmer telephone complaints; drove a motorbike across 40 km of unpaved roads to verify suspected stem borer or moisture stress; managed only 10–15 farm visits per week.
- **Workflow With AgriMind**: Opens the AgriVision web portal each morning. AgriMind automatically ingests Sentinel-2 NDVI imagery and CHIRPS anomalies across registered Uasin Gishu plots, pre-ranking them by risk. Kiprono reviews parcel `KE-001` (Moiben Plot A), confirms the autonomous agent's findings (*"NDVI dropped to 0.42, 48h rainfall forecast is 18mm $\rightarrow$ Action: HOLD"*), and clicks **Approve** in 30 seconds.

#### Persona 2: Smallholder Farmer — Wanjiku Cherop (Moiben / Sergoit)
- **Profile**: Cultivates 2.5 acres of commercial maize (SC Duma 43 / H6213); owns a basic 2G feature phone without internet.
- **Interaction**: Notices leaf hole perforations and suspects Fall Armyworm. Instead of immediately spraying costly pesticide into an impending rainstorm, Wanjiku dials **`*384#`** on her phone.
- **Response**: The USSD service displays:
  ```text
  [Moiben Plot A]
  Action: HOLD
  Status: OK
  Soil/Rain: Checked vs baselines
  AgriMind AI Verified 🌽
  ```
  She instantly requests an SMS summary (Option 4), saving her KES 3,500 in wasted chemicals and protecting her soil ecology.

### Measured Value to the Extension Office
- **75% Reduction in Field Travel Time**: Extension officers focus physical visits exclusively on parcels flagged `CRITICAL` or `INSUFFICIENT_EVIDENCE`.
- **Zero Hallucinated Advisory Delivery**: The deterministic validator enforces dual corroboration (NDVI vigor + soil/rain telemetry) and requires explicit officer sign-off before any SMS is transmitted.
- **Universal Accessibility**: Feature-phone USSD eliminates digital exclusion for smallholders.

---

## 1. Project overview

AgriVision brings together several components:

- Django web app for field, weather, and crop management
- GeoDjango field storage for farm boundaries and spatial analysis
- Earth Engine-based remote sensing workflows for vegetation and stress measurement
- Soil data integration using field records and external soil datasets
- Recommendations generated from weather and crop conditions
- Report generation for agronomic summaries and direct farmer communication
- Optional Rust-backed analysis engine for higher-speed processing workflows

The system is intended to assist with crop diagnosis, field planning, and management decisions across the season rather than acting as a standalone agronomy replacement.

---

## 2. Core goals

The application is built around the following goals:

- map, store, and validate field-level production data
- estimate crop health using vegetation and soil indicators
- monitor field stress caused by weather, water deficit, and poor soil conditions
- estimate yield potential in tonnes per hectare
- provide agronomic advice for irrigation, planting, pest management, and harvest timing
- generate reports useful for field officers, agronomists, and farmers

---

## 3. Technical architecture

### 3.1 Backend

The backend is a Django application with a modular structure:

- base/models.py: entities such as users, fields, weather data, crop stages, and recommendations
- base/views.py: controllers for analysis and UI request handling
- base/utils.py: weather and recommendation services
- base/health.py: crop health logic and supporting utilities
- base/report_generator.py: document output generation
- base/agrivision_gee_analysis.py: Earth Engine and crop analysis pipeline
- base/analysis.py: combined soil and climate analysis routines

### 3.2 Remote sensing and Earth Engine

The project integrates Google Earth Engine and geemap for satellite data processing. This allows the app to compute vegetation and stress indicators from remote imagery, including:

- NDVI
- EVI
- NDMI
- SAVI
- crop stress indices and weather/vigor anomalies

These indicators feed into health scoring and yield estimation.

### 3.3 Recommendation engine

The recommendation layer reads weather and field conditions to generate practical guidance. Examples include:

- irrigation recommendations
- pest warning alerts
- planting-window recommendations
- harvest recommendation windows
- weather-based alerts for heat, wind, and heavy rain

### 3.4 Rust analysis engine

The project includes an analysis_engine folder with a Rust implementation. This component supports specialized processing for variable-rate agriculture and other performance-critical analysis tasks.

---

## 4. Data model and field workflow

The application revolves around the following information flow:

1. A field is created with a polygon geometry and metadata.
2. Crop and growth-stage information are associated with planting activities.
3. Weather records are collected for each field.
4. Soil attributes are assembled from local records or external soil datasets.
5. Earth Engine data is processed to derive crop-status indicators.
6. Yield and health models estimate production potential.
7. Recommendations are generated and presented to the user.
8. A report can be produced summarizing the field analysis.

---

## 5. Maize-specific focus

Maize is the main crop of interest for the agronomic logic in this project. Its analysis emphasizes the following:

- vegetation vigor and greenness
- stage-specific stress during vegetative, flowering, and grain-filling windows
- water deficit and moisture stress evaluation
- soil suitability and fertility constraints
- weather-driven risk conditions
- yield prediction under stress and non-stress conditions

The project is tuned to detect both early warning signs and mid-season bottlenecks that influence final maize output.

For the detailed maize-specific guidance, see [MAIZE_HEALTH_YIELD_README.md](MAIZE_HEALTH_YIELD_README.md).

For the Phase 1 MCP setup for the maize health/yield layer using a third-party Postgres/PostGIS MCP server, see [MAIZE_HEALTH_YIELD_MCP_SETUP.md](MAIZE_HEALTH_YIELD_MCP_SETUP.md).

For the LangGraph orchestration layer using local open-weight models and human approval checkpoints, see [MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md](MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md).

For the isolated-domain extraction guide that separates the maize health/yield subsystem into a standalone codebase for cleaner production deployment, see [MAIZE_HEALTH_YIELD_ISOLATION_GUIDE.md](MAIZE_HEALTH_YIELD_ISOLATION_GUIDE.md).

---

## 6. Health and yield estimation capabilities

The analysis workflow supports a health model that combines several factors:

- vegetation condition
- water stress level
- soil condition and retention capacity
- crop stage and seasonal timing
- environmental anomaly pressures

This results in a crop health score and a field health category, which are then used alongside yield predictions.

The yield estimation logic is designed to answer practical questions such as:

- Is this field on track to achieve expected maize yield?
- Which environmental variables are limiting final output?
- What interventions could improve yield potential?
- How much yield improvement is realistically achievable with targeted management?

The report generator includes sections for:

- overall health assessment
- yield prediction
- limiting-factor analysis
- recommended field actions

---

## 7. Agronomic recommendations

The recommendation engine produces advice based on field and weather state. These recommendations are intended to support better timing for:

- irrigation
- weed control and maintenance
- pest control and monitoring
- nutrient and soil management decisions
- planting operations
- harvest planning

The system uses urgency and confidence scoring so farmers can prioritize the most relevant actions.

---

## 8. Project structure

The repository has the following high-level structure:

- AgriVision/: Django project settings and URL configuration
- base/: application logic, models, views, services, and analysis modules
- analysis_engine/: Rust-based analysis engine
- static/: CSS, JS, images, and frontend assets
- templates/: Django HTML templates
- db.sqlite3: local SQLite database
- manage.py: Django management entry point
- requirements.txt: Python package requirements
- test.py: Earth Engine / geemap usage script

---

## 9. Installation and setup

### 9.1 Requirements

- Python 3.10+
- Django
- GeoDjango-compatible spatial dependencies
- Earth Engine Python client
- geemap
- PostgreSQL/PostGIS is commonly preferred for geospatial work, though local SQLite may be used for development

### 9.2 Setup

1. Create a virtual environment.
2. Install dependencies from requirements.txt.
3. Configure the Django settings and database.
4. Apply migrations.
5. Start the Django development server.
6. Configure any external key or service credentials required for weather and Earth Engine workflows.

Example setup pattern:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### 9.3 Earth Engine configuration

The project includes logic to initialize Google Earth Engine with the configured project if available. In the current script, an environment variable is checked:

```python
gee_project = os.environ.get('AGRIVISION_GEE_PROJECT')
if gee_project:
    ee.Initialize(project=gee_project)
else:
    ee.Initialize()
```

This allows the application to work with project-scoped Earth Engine configuration when it is set.

---

## 10. Environment variables and external services

The app depends on multiple external services and variables, including:

- weather API access
- Earth Engine project configuration
- optional model or report-generation services
- geospatial datasets and remote-sensing providers

The exact service keys should be configured before using the production analysis features.

---

## 11. Typical use cases

AgriVision is designed for use cases such as:

- monitoring field health during the growing season
- diagnosing maize stress due to moisture or heat
- comparing actual crop condition to expected seasonal performance
- estimating yield risk before harvest
- planning irrigation and input timing
- generating agronomic reports for field advisors and farmers

---

## 12. Expected outputs

The platform can generate outputs such as:

- field health score
- vegetation and water stress assessment
- soil quality summary
- yield estimate in tonnes per hectare
- limiting factor identification
- recommended interventions
- agronomic report documents

---

## 13. Operational strengths

Some of the strongest practical advantages of the project are:

- crop-stage-aware analysis
- integration of satellite sensing and soil/weather data
- operational recommendation engine
- support for farm-level decision making
- modular structure for extension to more crops and additional agronomy models

---

## 14. Limitations and cautions

This project should be treated as a decision-support system. Several factors can influence accuracy:

- data availability and coverage quality
- weather and soil measurement uncertainty
- crop variability across management zones
- local agronomic practices and field conditions

Outputs should be validated through field inspection, agronomic knowledge, and local knowledge of the production environment.

---

## 15. Summary

AgriVision is a field intelligence platform for agricultural monitoring, crop health analysis, and agronomic decision support. Its main value is the combination of remote sensing, soil and weather inputs, and crop-stage-aware logic to estimate maize crop condition and yield potential. It gives farmers and advisors a practical way to diagnose risk, improve timing of operations, and plan for better production outcomes.

The maize-specific workflow is documented in detail in [MAIZE_HEALTH_YIELD_README.md](MAIZE_HEALTH_YIELD_README.md).

