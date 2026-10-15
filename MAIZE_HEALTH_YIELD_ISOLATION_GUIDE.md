# AgriVision Maize Health & Yield Isolation Guide

## 0. Scope, Non-scope, Deliverables, and Acceptance Criteria

### Scope

This isolation project covers the extraction, refactoring, and packaging of the maize health and yield subsystem from the broader AgriVision application into a standalone, production-ready domain service.

The extracted scope includes:

- maize field and crop state management
- soil and climate context analysis
- satellite and vegetation index interpretation
- maize-specific crop health scoring
- yield estimation and limiting-factor analysis
- agronomic recommendation generation
- structured evidence and advisory drafting
- integration points for the Phase 1 MCP server and the Phase 2 LangGraph orchestration workflow

### Non-scope

The extracted service does not include:

- general user authentication and account management
- billing, subscriptions, payments, or commercial workflows
- unrelated crop or non-maize domain logic
- generic dashboard, portal, or UI shell functionality
- non-maize business administration and operational tooling
- full application-wide deployment concerns unrelated to the maize decision workflow

### Deliverables

The output of this work should be a standalone service or repository that includes:

- clean domain models for maize health and yield
- repositories and services for soil, weather, health, yield, and recommendations
- API or MCP-facing tool contracts for field status, telemetry, yield assessment, and advisory generation
- structured schema definitions for evidence, crop health, yield output, and agronomic actions
- local validation and test coverage for field health and yield logic
- integration hooks for the MCP and LangGraph layers
- deployment documentation suitable for a production-ready implementation

### Acceptance Criteria

The extraction is considered successful only if:

1. All maize health and yield logic is separated from unrelated AgriVision concerns.
2. The standalone service exposes clear, typed interfaces for crop status, field telemetry, yield estimate, and advisory generation.
3. The service can operate without depending on the main Django app UI or generic web-layer state.
4. The service is compatible with the MCP tool contract defined in [MAIZE_HEALTH_YIELD_MCP_SETUP.md](MAIZE_HEALTH_YIELD_MCP_SETUP.md).
5. The service can be consumed by the LangGraph orchestration workflow defined in [MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md](MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md).
6. Evidence-backed decisions are traceable and auditable.
7. The final result is production-ready, testable, and independently deployable.

---

## 1. Objective

This document is a complete extraction and migration guide for isolating the maize health and yield functionality from the main AgriVision application and packaging it as a standalone service or codebase that can be implemented cleanly alongside the Phase 1 MCP layer and the Phase 2 LangGraph orchestration layer.

The goal is to separate the maize-specific operational logic from the broader agribusiness application so that it can be:

- maintained independently
- deployed as a distinct microservice or backend module
- connected to the maize MCP tool layer and agent orchestration stack
- versioned and evolved without interfering with the rest of the AgriVision platform
- prepared for cleaner production deployment

This guide is intentionally detailed because the extraction is not just a file copy: it is a functional decomposition of a real agricultural intelligence subsystem that must align with the domain logic defined in [MAIZE_HEALTH_YIELD_README.md](MAIZE_HEALTH_YIELD_README.md), the MCP contract in [MAIZE_HEALTH_YIELD_MCP_SETUP.md](MAIZE_HEALTH_YIELD_MCP_SETUP.md), and the orchestration flow in [MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md](MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md).

---

## 2. What is being isolated

The maize health and yield subsystem includes the following functional domains:

### 2.1 Crop and field state

- field boundary and plot geometry
- maize crop type definition
- planting timeline and stage tracking
- field owner or farm ownership metadata
- seasonal activity tracking

### 2.2 Soil context

- soil pH
- organic carbon
- clay and sand percentages
- cation exchange capacity
- bulk density
- field capacity and wilting point
- soil health scoring

### 2.3 Weather and climate context

- temperature range and averages
- rainfall and anomaly measures
- humidity and wind conditions
- seasonal climate suitability
- stress events such as heat, drought, heavy rain, and wind risk

### 2.4 Remote sensing and vegetation analytics

- NDVI
- EVI
- NDMI
- SAVI
- anomaly detection
- crop vigor trend evaluation
- stress scoring and health aggregation

### 2.5 Yield estimation

- predicted yield in tonnes per hectare
- yield category or risk band
- limiting factor analysis
- optimization potential
- confidence and credibility context

### 2.6 Agronomic recommendations

- irrigation timing guidance
- pest risk monitoring
- weather-related warnings
- planting window recommendations
- harvest timing recommendations
- crop-stage-aware decision support

### 2.7 Reporting and output layer

- field summary report generation
- health assessment narration
- yield and risk explanation
- recommendation output for farmers or extension officers

---

## 3. Why this extraction is needed

The current AgriVision project mixes multiple concerns in one Django app, but the maize health and yield subsystem must be treated as a clean domain slice with clear interfaces to the MCP and orchestration layers:

- authentication and user management
- field and spatial records
- weather and soil logic
- recommendation engine
- report generation
- remote sensing analytics
- crop analysis logic
- potentially Rust-based analysis engine integration

For production hardening, it is better to extract the maize health and yield functionality into a dedicated service that has a single purpose: to produce evidence-backed maize health assessments, yield estimates, and agronomic advisories that can be exposed through MCP tools and acted on by the LangGraph workflow.

The isolated service should therefore be responsible for:

- collecting and validating evidence
- assessing maize crop condition
- estimating yield risk and yield potential
- generating agronomic actions with structured rationale
- handing off the result to MCP and agent workflows

This makes the service easier to test, version, secure, and evolve independently while keeping it aligned with the rest of the maize stack.

---

## 4. Architecture of the isolated service

The extracted maize module should have a clean structure built around these responsibilities:

### 4.1 Data access layer

This layer handles access to:

- Postgres/PostGIS data
- weather sources
- soil profile records
- historical field data
- maize health snapshots
- yield prediction records

### 4.2 Analysis core

This layer performs:

- crop health aggregation
- vegetation index interpretation
- water stress calculation
- soil suitability assessment
- anomaly detection
- yield estimate generation

### 4.3 Recommendation layer

This layer generates action recommendations such as:

- irrigation
- pest monitoring
- harvest timing
- spray timing
- hold decisions
- planting support

### 4.4 Orchestration adapter layer

This layer exposes operations to:

- MCP tools
- LangGraph agent workflows
- external service calls
- human approval interfaces

### 4.5 Output and reporting layer

This layer creates:

- JSON responses
- advisory summaries
- structured evidence records
- field reports for officers and farmers

---

## 5. Recommended target repository structure

The new standalone repo should be structured like this:

```text
maize-health-yield-service/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── Makefile
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── settings.py
│   ├── database.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── field.py
│   │   ├── crop_season.py
│   │   ├── soil_profile.py
│   │   ├── weather_observation.py
│   │   ├── maize_health_snapshot.py
│   │   ├── yield_prediction.py
│   │   └── advisory_draft.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── field.py
│   │   ├── telemetry.py
│   │   ├── health.py
│   │   ├── yield.py
│   │   └── advisory.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── soil_service.py
│   │   ├── weather_service.py
│   │   ├── monitoring_service.py
│   │   ├── yield_service.py
│   │   ├── recommendation_service.py
│   │   └── report_service.py
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── vegetation_indices.py
│   │   ├── crop_health.py
│   │   ├── anomaly_detection.py
│   │   ├── stress_index.py
│   │   └── yield_model.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── field_repository.py
│   │   ├── telemetry_repository.py
│   │   ├── yield_repository.py
│   │   └── advisory_repository.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   ├── health.py
│   │   ├── field.py
│   │   ├── telemetry.py
│   │   ├── advisory.py
│   │   └── report.py
│   ├── mcp/
│   │   ├── __init__.py
│   │   ├── server.py
│   │   ├── tools.py
│   │   └── registry.py
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── state.py
│   │   ├── graph.py
│   │   ├── validators.py
│   │   ├── prompts.py
│   │   └── dispatch.py
│   ├── worker/
│   │   ├── __init__.py
│   │   ├── tasks.py
│   │   └── scheduler.py
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       ├── cache.py
│       ├── retry.py
│       └── evidence.py
├── tests/
│   ├── test_soil_service.py
│   ├── test_weather_service.py
│   ├── test_yield_service.py
│   ├── test_recommendation_service.py
│   ├── test_mcp_tools.py
│   └── test_graph_flow.py
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── api.md
│   └── deployment.md
└── scripts/
    ├── bootstrap_db.py
    ├── seed_demo_fields.py
    ├── run_mcp.py
    └── run_agent.py
```

This structure keeps responsibilities clean and easy to move into a new repo.

---

## 6. What to move out of the original app

From the current AgriVision codebase, the following areas should be extracted:

### 6.1 Django models that are directly tied to maize logic

From [base/models.py](base/models.py):

- Crop
- CropGrowthStage
- WeatherData
- FieldActivity
- SmartRecommendation
- potential field-related models needed for crop analysis

### 6.2 Health and analysis code

From [base/agrivision_gee_analysis.py](base/agrivision_gee_analysis.py):

- polygon_to_coords
- derive_growth_stages
- stages_from_growth_stage_qs
- soil_context_from_db
- weather_from_db
- crop index calculations
- vegetation metric calculations
- health scoring logic

### 6.3 Recommendation logic

From [base/recommendation_engine.py](base/recommendation_engine.py):

- recommendation generation methods
- weather-based recommendations
- irrigation recommendations
- pest warnings
- planting and harvest guidance
- scoring and urgency calculations

### 6.4 Report generation

From [base/report_generator.py](base/report_generator.py):

- executive summaries
- health section generation
- yield section generation
- recommendation section generation
- report document generation

### 6.5 Soil/weather utility logic

From [base/utils.py](base/utils.py) and [base/weather_utils.py](base/weather_utils.py):

- weather service logic
- recommendation engine interfaces
- suitability scores

### 6.6 Views and endpoints specific to maize analysis

From [base/views.py](base/views.py):

- analysis endpoints
- field health endpoints
- weather and soil analysis routes
- crop report generation and API handlers

This is the operational subset that should become the new standalone service.

---

## 7. What should remain in the main app

Not everything should be extracted. Keep the following in the original application if needed:

- user authentication and account management
- general web UI shell and navigation
- non-agronomic business features
- payment and subscription features
- non-maize crop logic if introduced later
- general dashboard pages unrelated to maize analysis

The separation should be purpose-driven: keep only the maize health and yield workflow in the new standalone service while the original app retains broader business features.

---

## 8. Functional boundaries for the extraction

The extracted subsystem should own these responsibilities completely:

### 8.1 It owns:

- maize crop state and field metadata
- soil monitoring data and interpretation
- weather-driven risk analysis
- vegetation and stress analysis
- yield estimation and risk scoring
- advisory generation
- evidence-based recommendation output

### 8.2 It does not own:

- the user auth system
- payment or billing
- unrelated crop modules
- UI generic infrastructure
- broad business admin features

---

## 9. Input contract for the isolated service

The standalone maize service should expose a clear contract for all input and output.

### 9.1 Input payload example

```json
{
  "plot_id": "KE-001",
  "crop_type": "maize",
  "field_geometry": {
    "type": "Polygon",
    "coordinates": [[[36.8, -1.2], [36.82, -1.2], [36.82, -1.22], [36.8, -1.22], [36.8, -1.2]]]
  },
  "planting_date": "2026-03-02",
  "soil_profile": {
    "ph": 6.1,
    "organic_carbon": 1.8,
    "clay_percent": 28,
    "sand_percent": 45
  },
  "weather": {
    "temperature_avg": 24,
    "rainfall_mm": 18,
    "humidity_pct": 66,
    "wind_speed_kmh": 11
  }
}
```

### 9.2 Output object example

```json
{
  "plot_id": "KE-001",
  "overall_health_score": 72.4,
  "health_category": "Moderate",
  "water_stress_index": 28.5,
  "soil_health_score": 74.0,
  "predicted_yield_t_ha": 5.8,
  "yield_category": "Good",
  "limiting_factors": [
    "water_stress",
    "soil_moisture_gap"
  ],
  "recommendations": [
    {
      "action": "IRRIGATE",
      "urgency": "medium",
      "message": "Irrigation recommended within 24 hours due to moisture stress."
    }
  ],
  "evidence_ids": [
    "EVID-WEATHER-01",
    "EVID-SOIL-01",
    "EVID-NDVI-01"
  ]
}
```

This interface is suitable for MCP call adaptation and LangGraph reasoning.

---

## 10. Data model to extract

The new repo should define a clean maize-specific model set. These are the most important data structures to extract and preserve.

### 10.1 Field

- id
- name
- geometry
- owner_id
- area_ha
- created_at

### 10.2 CropSeason

- id
- field_id
- crop_type
- planting_date
- stage
- expected_yield_t_ha
- created_at

### 10.3 SoilProfile

- id
- field_id
- ph
- organic_carbon
- clay_percent
- sand_percent
- field_capacity
- wilting_point
- cec
- measured_at

### 10.4 WeatherObservation

- id
- field_id
- timestamp
- temperature_c
- rainfall_mm
- humidity_pct
- wind_speed_kmh
- weather_condition

### 10.5 MaizeHealthSnapshot

- id
- field_id
- season_id
- ndvi
- evi
- ndmi
- savi
- overall_health_score
- water_stress_index
- soil_health_score
- anomaly_flag
- evidence_id
- captured_at

### 10.6 YieldPrediction

- id
- field_id
- season_id
- predicted_yield_t_ha
- yield_category
- limiting_factors
- optimization_potential
- model_version
- created_at

### 10.7 AdvisoryDraft

- id
- field_id
- action
- rationale
- evidence_ids
- status
- created_at

This stripped-down set is enough for a clean, modular maize health/yield domain.

---

## 11. Logic to isolate and refactor

The extraction should be performed in a very explicit sequence to avoid mixing domain logic with web framework concerns.

### 11.1 Step 1: Identify all maize-specific domain logic

Search the project for maize-related entries, including:

- NDVI, EVI, NDMI, SAVI usage
- crop health scoring
- yield prediction logic
- recommendation engine logic
- growth stage logic
- planting or harvest window logic
- soil and weather suitability logic

### 11.2 Step 2: Remove web-specific dependencies

The extracted service should not import Django views or templates directly. Remove all:

- request objects
- HTTP response objects
- template rendering calls
- user session code
- app-specific UI dependencies

### 11.3 Step 3: Extract pure business logic

Move business logic into service classes such as:

- SoilAnalysisService
- WeatherAnalysisService
- VegetationHealthService
- YieldPredictionService
- RecommendationService
- MaizeAdvisoryService

### 11.4 Step 4: Separate data access from decision logic

Use repository classes for database access; keep algorithmic logic in services.

### 11.5 Step 5: Standardize outputs

All services should return structured JSON or dataclasses rather than mixing raw database objects with UI-specific structures.

---

## 12. Extraction checklist by file

### 12.1 File-by-file recommended extraction

#### [base/models.py](base/models.py)

Extract:

- Crop
- FieldActivity
- WeatherData
- CropGrowthStage
- SmartRecommendation

Convert these into a domain model layer for the maize service.

#### [base/agrivision_gee_analysis.py](base/agrivision_gee_analysis.py)

Extract all remote-sensing and field analysis logic and convert it into:

- vegetation_indices.py
- crop_health.py
- anomaly_detection.py
- stress_index.py
- yield_model.py

#### [base/recommendation_engine.py](base/recommendation_engine.py)

Extract into:

- recommendation_service.py
- advisory generation logic
- risk classification and urgency scoring

#### [base/report_generator.py](base/report_generator.py)

Extract into:

- report_service.py
- summarizer and output formatting classes

#### [base/utils.py](base/utils.py)

Extract the general utility functions and weather-related helpers that support maize analysis.

#### [base/weather_utils.py](base/weather_utils.py)

Extract and normalize the weather suitability scoring logic into a dedicated analysis service.

#### [base/views.py](base/views.py)

Only extract the endpoints semantically tied to maize analysis and turn them into service API routes for the standalone service.

---

## 13. Dependency minimization strategy

The isolated maize service should avoid dependencies on the rest of the monolith.

### 13.1 Remove these from the extracted service

- Django admin classes
- template rendering
- database-specific session management
- authentication context
- old UI integration logic
- broad app settings from the full project

### 13.2 Keep these in the isolated service

- SQLAlchemy or Postgres access
- pydantic schemas
- weather API clients
- EO/remote sensing libraries only if needed
- local model interfaces if the service performs direct inference
- MCP server interfaces

---

## 14. Service API design

The standalone system should expose clean APIs suitable for MCP and agent orchestration. The most important endpoints are:

### 14.1 Health and status API

```http
GET /api/v1/health
```

Response:

```json
{
  "status": "ok",
  "service": "maize-health-yield",
  "version": "1.0.0"
}
```

### 14.2 Plot status API

```http
GET /api/v1/plots/{plot_id}/status
```

### 14.3 Telemetry analysis API

```http
GET /api/v1/plots/{plot_id}/telemetry
```

### 14.4 Yield estimation API

```http
POST /api/v1/plots/{plot_id}/yield-estimate
```

### 14.5 Advisory draft API

```http
POST /api/v1/plots/{plot_id}/advisory
```

### 14.6 Report generation API

```http
POST /api/v1/plots/{plot_id}/report
```

These APIs will later be wrapped by the MCP server tools and consumed by the LangGraph agent.

---

## 15. MCP integration contract for the extracted service

After extraction, the new repo should expose the following tool-level contract:

- get_plot_status(plot_id)
- analyze_crop_telemetry(plot_id)
- evaluate_calendar_window(crop_stage, rain_anomaly, spray_risk)
- estimate_yield(plot_id)
- draft_advisory(plot_id, action, evidence_ids, rationale)
- generate_report(plot_id)

This contract is exactly aligned with the MCP and orchestration design already created for the project.

---

## 16. Production-ready extraction principles

The isolated repo should be designed with the following rules:

### 16.1 Single responsibility

The maize service should only handle maize crop intelligence and advisory logic.

### 16.2 Loose coupling

It should not depend on the rest of the AgriVision application’s web or user logic.

### 16.3 Clear contracts

All service and MCP interfaces should have type-safe inputs and outputs.

### 16.4 Observability

Every call should log:

- plot ID
- request type
- evidence IDs
- model version
- action chosen
- warning state

### 16.5 Auditable decisions

Every recommendation should retain evidence and human approval context.

### 16.6 Resilience

The service should gracefully handle missing soil data, missing weather data, and incomplete remote-sensing data.

---

## 17. Data-handling strategy

### 17.1 Missing data handling

The service should clearly handle the following conditions:

- no field geometry available
- no soil profile available
- no recent weather data available
- no satellite imagery available
- no planting data available

In these cases, the workflow should return a structured state such as:

```json
{
  "status": "insufficient_data",
  "message": "No recent maize health telemetry available for this plot.",
  "required_fields": ["soil_profile", "weather", "vegetation_indices"]
}
```

### 17.2 Evidence provenance

Each health or yield evaluation should include an evidence source list, such as:

- soil-profile lookup
- weather observation
- NDVI snapshot
- yield model output
- historical yield trend

This is critical for the officer approval and MCP agent pipeline.

---

## 18. Validation strategy for the isolated service

Before the new repo is considered production-ready, test the following:

### 18.1 Unit tests

- yield estimate for a healthy maize plot
- yield estimate for a moisture-stressed plot
- soil constraints reduce yield potential
- weather anomaly triggers recommendation logic
- missing telemetry leads to insufficient_data status
- action service drafts valid advisory records

### 18.2 Integration tests

- Postgres/PostGIS data is queryable
- weather service returns valid data
- vegetation analysis service returns expected NDVI/EVI/NDMI values
- recommendation service generates correct actions
- MCP server exposes the correct tool list
- LangGraph state machine reaches the approval node

### 18.3 Contract tests

- JSON schemas match the MCP tool inputs/outputs
- data types are stable across all endpoints
- evidence IDs always appear in action payloads

---

## 19. Migration path from the current monolith

### 19.1 Phase A: Extract domain code

- move the maize-related models into the new repo
- extract service logic
- remove all Django UI references

### 19.2 Phase B: Define MCP interface

- wrap domain services as MCP tools
- make the tools deterministic and structured

### 19.3 Phase C: Connect orchestration

- link the new service to LangGraph
- validate the graph end-to-end with a synthetic field

### 19.4 Phase D: Production hardening

- add monitoring
- add persistent audit storage
- add retry and circuit breaker policies
- add deployment configuration and health checks

---

## 20. Implementation priorities

If you plan to do the extraction in an ordered sequence, this is the recommended order:

1. isolate the maize crop model and field metadata
2. isolate soil and weather services
3. isolate vegetation and stress analytics
4. isolate yield prediction logic
5. isolate recommendation engine
6. isolate reporting and advisory drafts
7. expose the domain as MCP tools
8. connect to LangGraph orchestration
9. harden for production and deployment

This order reduces risk and keeps domain logic stable before connecting it to external orchestration systems.

---

## 21. Recommended domain names

Use clear names that reflect the maize-only service:

- maize-health-yield-service
- agrivision-maize-core
- maize-field-intelligence
- maize-crop-monitoring-service
- maize-yield-advisory-engine

Choose one name that is deliberately domain-specific and not a generic AgriVision word that might keep the service entangled with unrelated modules.

---

## 22. Recommended development conventions

### 22.1 Typing

Use Python type hints everywhere:

- dataclasses
- pydantic models
- Literal enums for action types
- strict typed DTOs for API and MCP payloads

### 22.2 Testing

Use:

- pytest
- fixture-based dataset tests
- mock-free logic tests where feasible
- end-to-end tests for MCP and graph workflow

### 22.3 Logging

Use structured logging with fields such as:

- plot_id
- crop_type
- stage
- decision
- evidence_count
- confidence

---

## 23. Example summary of the isolated service

The standalone maize service should behave like this:

- accept a field or plot identifier
- read field, soil, weather, vegetation, and historical context
- compute health, moisture stress, and yield potential
- generate a recommendation based on stage-aware agronomic rules
- attach evidence IDs and rationale
- require human approval before final advisory submission
- return safe, structured, auditable output to the agent or caller

This is the true production-ready form of the maize intelligence subsystem.

---

## 24. Final recommendation

The cleanest approach is to treat the isolated maize service as a separate domain service rather than a thin wrapper around the main Django app. It should become a proper agricultural intelligence backend whose responsibilities are explicit and bounded.

This service should be the component that is later connected to:

- the third-party Postgres/PostGIS MCP server
- the custom maize FastMCP server
- the local open-weight LangGraph orchestrator
- the final officer approval workflow

By isolating it in this way, the production-ready version becomes far easier to deploy, scale, test, and maintain.

---

## 25. Closing statement

This extraction is not just a code move. It is a productization step. It transforms the maize health and yield system from a portion of a larger app into a purpose-built analytic backend capable of interfacing with MCP and agent orchestration in a clean, auditable, and production-ready manner.

That is the correct way to prepare the maize functionality for independent implementation and deployment.
