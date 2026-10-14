# AgriVision

AgriVision is a Django-based agricultural intelligence platform designed to support field monitoring, crop health analysis, weather-aware recommendations, and crop yield estimation. The project combines farm field data, satellite-derived vegetation indices, soil properties, and agronomic logic to help farmers and agronomic teams assess crop condition and take timely action.

This project is especially designed for maize-focused production decision support, with emphasis on health monitoring, yield estimation, and agronomic advisory.

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