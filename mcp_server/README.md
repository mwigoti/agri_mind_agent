# AgriMind MCP Gateway (Layer 3)

This directory houses the **Model Context Protocol (MCP) Gateway** for the AgriMind agricultural decision-support system. It acts as the secure, protocol-compliant translation layer connecting:
* **Layer 2 (LangGraph Autonomous Orchestrator):** The reasoning loop that plans, calls tools, and grounds decisions.
* **Layer 4 (PostgreSQL/PostGIS + Satellite + ML Foundation):** Live geospatial plot boundaries, soil baselines, pre-computed Earth observation telemetry, and ML yield predictions.

---

## Architecture Overview

```
                      ┌────────────────────────────────────────┐
                      │   Layer 2: LangGraph Agent Host        │
                      └──────────────┬──────────────────┬──────┘
                                     │                  │
                Pipe A (stdio)       │                  │  Pipe B (stdio)
        ┌────────────────────────────▼───┐          ┌───▼────────────────────────────┐
        │  Custom FastMCP Gateway (Agri) │          │  Borrowed MCP (mcp-sqlite)     │
        │  Server: mcp_server.server     │          │  Official mcp-server-sqlite    │
        │                                │          │                                │
        │  1. get_plot_status            │          │  5. read_query                 │
        │  2. analyze_crop_telemetry     │          │  6. list_tables                │
        │  3. evaluate_calendar_window   │          │  7. describe_table             │
        │  4. draft_advisory_for_approval│          │                                │
        │     (Stateful Mutating Action) │          │  (Read-Only Historical DB)     │
        └────────────────┬───────────────┘          └───────────────┬────────────────┘
                         │                                          │
                         ▼                                          ▼
            ┌─────────────────────────┐               ┌───────────────────────────┐
            │ Live PostgreSQL/PostGIS │               │ Local SQLite File         │
            │ (base_field, analysis,  │               │ data/historical_records.db│
            │  advisory_drafts queue) │               │ (County baselines & norms)│
            └─────────────────────────┘               └───────────────────────────┘
```

---

## Directory Structure

```
mcp_server/
├── __init__.py               # Package initializer
├── config.py                 # DB connection parameters, 5.0s timeouts, stderr logging
├── server.py                 # FastMCP server instance ('AgriMind') exposing Tools 1-4
├── clients/
│   ├── __init__.py           # Clients subpackage
│   └── backend_client.py     # SQL query implementations, rule engine, & safety validators
└── README.md                 # This integration guide
```

---

## Quickstart & Environment Setup

### 1. Install Dependencies
Ensure the project virtual environment is active and required packages are installed:
```bash
pip install mcp>=1.6.0 mcp-server-sqlite>=2025.4.25 psycopg2-binary python-dotenv
```

### 2. Configure Environment (`.env`)
Create or update `.env` in the project root:
```ini
# PostgreSQL / PostGIS Database (Layer 4)
DATABASE_URL=postgres://agri_user:agri_password@localhost:5432/agrivision_db
DB_CONNECT_TIMEOUT=5.0
DB_STATEMENT_TIMEOUT=5000

# Logging
MCP_LOG_LEVEL=INFO
```

### 3. Launching the Servers

#### A. Launch Custom Gateway (AgriMind)
Runs over standard input/output (`stdio`) JSON-RPC 2.0:
```bash
python -m mcp_server.server
```

#### B. Launch Borrowed SQLite Server (Historical Archive)
Points to the self-contained reference database:
```bash
python -c "import mcp_server_sqlite; mcp_server_sqlite.main()" --db-path ./data/historical_records.db
```
*(If `data/historical_records.db` is not yet generated, run `python scripts/seed_historical_db.py` once)*.

---

## Tool Contracts & Schemas

### Tool 1: `get_plot_status`
* **Role:** Identity & Phenological Ground Truth.
* **Type:** Read-Only.
* **When to call:** **Must be the agent's very first tool call** for any plot analysis.

#### Input Contract
| Argument | Type | Description |
| :--- | :--- | :--- |
| `plot_id` | `str` | Plot identifier (e.g., `'101'` or `'PLOT-101'`). |

#### Output Response (`status: "OK"`)
```json
{
  "status": "OK",
  "plot_id": "101",
  "field_name": "Kiprono North Plot",
  "area_ha": 2.45,
  "location": {
    "county": "Nakuru",
    "center_lat": -0.2831,
    "center_lon": 36.0642
  },
  "crop": {
    "crop_type": "maize",
    "variety": "Standard Hybrid",
    "water_sensitivity": "high",
    "drought_tolerance": "medium"
  },
  "phenology": {
    "sowing_date": "2026-03-15",
    "days_after_sowing": 72,
    "growth_stage": "Flowering_R1",
    "critical_water_window": true
  },
  "soil_baseline": {
    "soil_ph": 6.2,
    "organic_carbon_gkg": 22.5,
    "soil_type": "Humic Nitisols"
  },
  "farmer": {
    "name": "John Kiprono",
    "phone_number": "+254712345678",
    "county": "Nakuru"
  }
}
```

---

### Tool 2: `analyze_crop_telemetry`
* **Role:** Remote Sensing Snapshot & Evidence Stamping.
* **Type:** Read-Only.
* **Staleness Guardrail:** If the latest telemetry record is $>30$ days old, returns `INSUFFICIENT_EVIDENCE`.

#### Input Contract
| Argument | Type | Description |
| :--- | :--- | :--- |
| `plot_id` | `str` | Plot identifier (e.g., `'101'`). |

#### Output Response (`status: "OK"`)
```json
{
  "status": "OK",
  "plot_id": "101",
  "latest_scene_date": "2026-10-10",
  "data_age_days": 2,
  "telemetry": {
    "vegetation_indices": {
      "ndvi_latest": 0.442,
      "evi_latest": 0.381,
      "ndre_peak": 0.512,
      "scene_count": 8
    },
    "water_and_climate": {
      "total_season_rainfall_mm": 310.5,
      "rainfall_anomaly_pct": -34.2,
      "cumulative_gdd": 1150.2,
      "heat_stress_fraction": 0.082,
      "water_stress_index": 58.4
    },
    "yield_prediction": {
      "predicted_yield_t_ha": 2.15,
      "risk_level": "High",
      "limiting_factors": ["moisture_deficit", "heat_stress"]
    }
  },
  "evidence_records": [
    {
      "evidence_id": "EVID-S2-NDVI-101-20261012",
      "source_sensor": "Sentinel-2 MSI Level-2A",
      "metric_name": "NDVI_Vegetative_Latest",
      "metric_value": 0.442
    },
    {
      "evidence_id": "EVID-CHIRPS-RAIN-101-20261012",
      "source_sensor": "CHIRPS Pentad Climatology",
      "metric_name": "Rainfall_Deficit_Anomaly_Pct",
      "metric_value": -34.2
    },
    {
      "evidence_id": "EVID-ML-YIELD-101-20261012",
      "source_sensor": "AgriVision Ensemble Voting Regressor",
      "metric_name": "Predicted_Yield_T_HA",
      "metric_value": 2.15
    }
  ],
  "evidence_ids": [
    "EVID-S2-NDVI-101-20261012",
    "EVID-CHIRPS-RAIN-101-20261012",
    "EVID-ML-YIELD-101-20261012"
  ],
  "stress_flags": [
    "Water stress detected (WSI > 50 %)",
    "Significant rainfall deficit (-34.2%)"
  ]
}
```

---

### Tool 3: `evaluate_calendar_window`
* **Role:** Biological Safety Guardrail & Physics Engine.
* **Type:** In-Memory / Deterministic (0 DB queries, 0 ms network latency).
* **Checks 4 Critical Biological Gates:**
  1. **Germination Moisture Gate:** Moisture $\ge 16\%$ and Rain Anomaly $\ge -30\%$.
  2. **Flowering Drought Gate:** Moisture $\ge 18\%$ and Rain Anomaly $\ge -25\%$ during Silking/Tasseling.
  3. **Spraying Washout & Pollinator Gate:** Forecast rain $\le 15.0\text{ mm}$ in next 48h; chemical spraying strictly forbidden during active pollination.
  4. **Fertilizer Osmotic Burn Gate:** Soil moisture $\ge 15\%$ for nitrogen top-dressing to prevent root plasmolysis.

#### Input Contract
| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `crop` | `str` | `"maize"` | Target crop name. |
| `phenological_stage`| `str` | `"vegetative"` | Current growth stage from Tool 1. |
| `rainfall_anomaly_pct` | `float` | `0.0` | Deficit/surplus percentage from Tool 2. |
| `soil_moisture_vwc` | `float` | `0.22` | Volumetric soil water content fraction (e.g. `0.14` = 14%). |
| `forecast_rain_next_48h_mm` | `float` | `0.0` | Forecasted rainfall in next 48 hours. |
| `plot_id` | `Optional[str]` | `None` | Optional plot ID for reference. |

#### Output Response (`overall_condition: "HAZARD_DETECTED"`)
```json
{
  "status": "OK",
  "crop": "maize",
  "evaluated_stage": "Flowering_R1",
  "overall_condition": "HAZARD_DETECTED",
  "safety_checks": {
    "germination_moisture_adequate": true,
    "pollination_moisture_safe": false,
    "spray_washout_risk_safe": false,
    "fertilizer_application_safe": false
  },
  "operational_windows": {
    "planting_permitted": true,
    "spraying_permitted": false,
    "top_dressing_permitted": false
  },
  "threshold_violations": [
    {
      "rule_id": "RULE-MAIZE-FLOWERING-02",
      "rule_name": "Critical Silking Moisture Deficit",
      "threshold": "Rain Anomaly >= -25% and Moisture >= 18% during flowering",
      "observed": "Rain Anomaly: -34.2%, Moisture: 14.0%",
      "severity": "CRITICAL",
      "consequence": "Pollen desiccation and silk emergence delay; barren cobs."
    },
    {
      "rule_id": "RULE-FERTILIZER-BURN-04",
      "rule_name": "Dry Soil Fertilizer Osmotic Burn",
      "threshold": "Soil Moisture >= 15% (0.15 VWC) for nitrogen top-dressing",
      "observed": "Soil Moisture: 14.0%",
      "severity": "HIGH",
      "consequence": "High salt concentration in dry soil chemically scorches root hairs."
    }
  ],
  "risk_flags": [
    "POLLINATION_WATER_STRESS",
    "FERTILIZER_BURN_RISK"
  ],
  "rule_citations": [
    "RULE-MAIZE-FLOWERING-02",
    "RULE-FERTILIZER-BURN-04"
  ],
  "summary_rationale": "Agronomic hazards detected for maize at Flowering_R1. 2 safety thresholds were breached. Recommended action is to HOLD restricted operations and apply risk mitigation."
}
```

---

### Tool 4: `draft_advisory_for_approval`
* **Role:** Stateful Mutating Action & Mandatory Human Gatekeeper.
* **Type:** Stateful Write (Inserts row into PostgreSQL `advisory_drafts`).
* **Non-Negotiable Guardrails:**
  1. **Strictly Hardcoded Status:** Always sets `status = 'PENDING_APPROVAL'`. The LLM has zero capability to self-approve or dispatch directly to farmers.
  2. **Anti-Hallucination Gate:** Rejects any request with fewer than 2 verifiable citations (`len(evidence_ids) < 2`), or invalid prefixes (must start with `EVID-` or `RULE-`).
  3. **24-Hour Deduplication:** If an identical pending draft was created for this plot in the last 24h, returns the existing draft ID instead of cluttering the review queue.

#### Input Contract
| Argument | Type | Description |
| :--- | :--- | :--- |
| `plot_id` | `str` | Target plot identifier (e.g., `'101'`). |
| `recommended_action` | `str` | Directive: must be `'PLANT'`, `'SPRAY'`, `'HOLD'`, or `'HARVEST'`. |
| `advisory_rationale` | `str` | Clear agronomic explanation for the human officer and farmer ($\ge 10$ chars). |
| `evidence_ids` | `List[str]` | List of $\ge 2$ citation tokens collected from Tools 2 and 3. |

#### Output Confirmation Receipt (`status: "OK"`)
```json
{
  "status": "OK",
  "advisory_id": "ADV-20261012-PLOT101-155409",
  "queue_status": "PENDING_APPROVAL",
  "plot_id": "101",
  "recommended_action": "HOLD",
  "requires_officer_review": true,
  "message": "Advisory draft ADV-20261012-PLOT101-155409 created successfully. Awaiting named human officer approval.",
  "triage_summary": {
    "plot_id": "101",
    "action": "HOLD",
    "evidence_count": 3,
    "evidence_citations": [
      "EVID-CHIRPS-RAIN-101-20261012",
      "RULE-MAIZE-FLOWERING-02",
      "RULE-FERTILIZER-BURN-04"
    ],
    "drafted_at": "2026-10-12T12:54:09.123456+00:00"
  }
}
```

---

## Borrowed 3rd-Party Server (`mcp-server-sqlite`)

To fulfill the hackathon mandate (*"One MCP server you did not write"*), we integrate the official Anthropic/community **`mcp-server-sqlite`**.

### Database: `data/historical_records.db`
Contains two pre-seeded reference tables:
1. `agro_ecological_baselines`: Published KALRO/FAO constants for Kenyan counties (elevation, 5-year mean NDVI, seasonal rainfall, benchmark yield).
2. `farmer_seasonal_history`: Past multi-season yield records for plots across 2023, 2024, and 2025.

### Tools Exposed by Borrowed Server
| Tool Name | Arguments | Description |
| :--- | :--- | :--- |
| `list_tables` | None | Returns list of all tables in the SQLite archive. |
| `describe_table` | `table_name: str` | Returns column names and data types (schema reflection). |
| `read_query` | `query: str` | Executes read-only SQL queries (`SELECT ...`) and returns JSON rows. |

### Sample Agent Query Pattern
```sql
SELECT county, historical_mean_ndvi, benchmark_yield_t_ha 
FROM agro_ecological_baselines 
WHERE county = 'Nakuru';
```

---

## Integration Guide for LangGraph (Layer 2)

For the teammate developing the LangGraph agent, here is the dual-server configuration snippet:

```python
# langgraph_mcp_config.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

MCP_SERVERS = {
    # 1. Custom Gateway (Layer 3 - Real-Time Telemetry & Stateful Drafting)
    "agrimind_gateway": {
        "command": sys.executable,
        "args": ["-m", "mcp_server.server"],
        "cwd": str(PROJECT_ROOT)
    },
    
    # 2. Borrowed Server (Layer 3 - Read-Only Historical Baseline Archive)
    "historical_archive": {
        "command": sys.executable,
        "args": [
            "-c",
            "import mcp_server_sqlite; mcp_server_sqlite.main()",
            "--db-path",
            str(PROJECT_ROOT / "data" / "historical_records.db")
        ],
        "cwd": str(PROJECT_ROOT)
    }
}
```

### Agent Tool Invocation Sequence
```
1. get_plot_status(plot_id)                    ──► Ground truth crop, stage, county
2. read_query("SELECT ... WHERE county=...")   ──► Query county 5-year baselines from SQLite
3. analyze_crop_telemetry(plot_id)             ──► Current NDVI, rainfall deficit, EVID-*
4. evaluate_calendar_window(...)               ──► Biological safety limits, RULE-*
5. draft_advisory_for_approval(...)            ──► Mutate DB queue (status='PENDING_APPROVAL')
```

---

## Production Guardrails Enforced

1. **Stdio JSON-RPC Integrity:** Zero `print()` statements exist in server code. All logs route strictly to `sys.stderr` via `logger`.
2. **Hard Timeouts:** All PostgreSQL connections and queries enforce a strict `5.0-second` timeout (`connect_timeout=5`, `statement_timeout=5000`).
3. **Structured Error Dictionaries:** Tools never raise uncaught exceptions. Database network failures return structured error payloads:
   `{"status": "ERROR", "code": "DB_CONNECTION_ERROR", "message": "..."}`.
4. **Data Staleness Rejection:** Analysis results older than 30 days are rejected as `INSUFFICIENT_EVIDENCE`.
5. **Human Authorization Boundary:** Advisories can never be marked as `'APPROVED'` or `'SENT'` by the AI agent; dispatch is exclusively triggered after a named human officer approves the draft on the Layer 1 dashboard.
