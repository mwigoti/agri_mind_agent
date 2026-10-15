# Maize Health & Yield MCP Setup Guide

## 1. Purpose

This document describes the Phase 1 MCP setup for the maize health and yield module of the AgriVision project. It follows the architecture described in the hackathon guidance: a custom FastMCP server exposes agronomy-specific logic, while a borrowed third-party Postgres/PostGIS MCP server provides historical and spatial field data access.

This is the integration layer for the maize decision stack. It does not redefine the domain logic; instead, it exposes the maize health, yield, and agronomic advisory decisions defined in [MAIZE_HEALTH_YIELD_README.md](MAIZE_HEALTH_YIELD_README.md) as standard MCP tools so that an external agent can reason over them safely, consistently, and in a structured way.

The goal is to expose the maize analysis workflow as standard MCP tools so that agents, copilots, and workflow orchestrators can discover and use:

- field condition and crop status
- vegetation and weather telemetry
- soil and spatial field context
- maize yield estimates and limiting factors
- agronomic advisory actions with evidence tracking

---

## 2. Architecture for the maize health/yield layer

The recommended setup is split into two MCP layers:

### 2.1 Custom FastMCP server for agronomy intelligence

This server wraps AgriVision-specific logic, including:

- field status retrieval
- crop telemetry analysis
- maize growth-stage checks
- yield model output
- agronomic action generation
- advisory drafting with evidence references

This server should expose the stateful and action-oriented tools that are unique to the project.

### 2.2 Borrowed 3rd-party Postgres/PostGIS MCP server

This server is used to access:

- plot and field geometries in PostGIS
- historical field records and seasons
- past yield trends
- soil, weather, and geospatial tables
- archived agronomic datasets

The key idea is to reuse a maintained Postgres/PostGIS MCP server instead of writing redundant SQL wrappers.

---

## 3. Phase 1 requirements from the hackathon guide

The hackathon implementation guidance specifies the following for Phase 1:

1. Build a custom FastMCP server that wraps agronomy data and yield models.
2. Expose tools such as:
   - get_plot_status(plot_id)
   - analyze_crop_telemetry(plot_id)
   - evaluate_calendar_window(crop_stage, rain_anomaly, spray_risk)
   - draft_advisory(plot_id, action, evidence_ids, rationale)
3. Ensure the server runs over stdio with mcp.run().
4. Configure a borrowed third-party Postgres/PostGIS MCP server to read spatial and historical records.
5. Keep the 3rd-party server read-oriented so the agent can discover trends without custom SQL wrappers.

This is the exact pattern you should follow for the maize health/yield layer. The same conceptual objects are used throughout the stack: field status, maize health telemetry, yield estimate, limiting factors, evidence IDs, and agronomic advisory drafts. The orchestration layer in [MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md](MAIZE_HEALTH_YIELD_AGENT_ORCHESTRATION.md) builds directly on these tools and schemas.

---

## 4. Recommended database schema

Use PostGIS for the maize analytics layer with a schema that matches the project’s field and crop workflow.

### 4.1 Core tables

```sql
CREATE TABLE fields (
    id SERIAL PRIMARY KEY,
    field_name TEXT NOT NULL,
    owner_id TEXT,
    geom GEOMETRY(POLYGON, 4326),
    area_ha DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE crop_seasons (
    id SERIAL PRIMARY KEY,
    field_id INTEGER REFERENCES fields(id),
    crop_type TEXT NOT NULL DEFAULT 'maize',
    planting_date DATE,
    growth_stage TEXT,
    expected_yield_t_ha DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE soil_profiles (
    id SERIAL PRIMARY KEY,
    field_id INTEGER REFERENCES fields(id),
    ph DOUBLE PRECISION,
    organic_carbon DOUBLE PRECISION,
    clay_percent DOUBLE PRECISION,
    sand_percent DOUBLE PRECISION,
    field_capacity DOUBLE PRECISION,
    wilting_point DOUBLE PRECISION,
    cec DOUBLE PRECISION,
    measured_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE weather_observations (
    id SERIAL PRIMARY KEY,
    field_id INTEGER REFERENCES fields(id),
    timestamp TIMESTAMPTZ NOT NULL,
    temperature_c DOUBLE PRECISION,
    humidity_pct DOUBLE PRECISION,
    rainfall_mm DOUBLE PRECISION,
    wind_speed_kmh DOUBLE PRECISION,
    weather_condition TEXT
);

CREATE TABLE maize_health_snapshots (
    id SERIAL PRIMARY KEY,
    field_id INTEGER REFERENCES fields(id),
    season_id INTEGER REFERENCES crop_seasons(id),
    ndvi DOUBLE PRECISION,
    evi DOUBLE PRECISION,
    ndmi DOUBLE PRECISION,
    savi DOUBLE PRECISION,
    overall_health_score DOUBLE PRECISION,
    water_stress_index DOUBLE PRECISION,
    soil_health_score DOUBLE PRECISION,
    anomaly_flag BOOLEAN DEFAULT FALSE,
    evidence_id TEXT,
    captured_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE yield_predictions (
    id SERIAL PRIMARY KEY,
    field_id INTEGER REFERENCES fields(id),
    season_id INTEGER REFERENCES crop_seasons(id),
    predicted_yield_t_ha DOUBLE PRECISION,
    yield_category TEXT,
    limiting_factors JSONB,
    optimization_potential DOUBLE PRECISION,
    model_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE advisory_drafts (
    id SERIAL PRIMARY KEY,
    field_id INTEGER REFERENCES fields(id),
    action TEXT NOT NULL,
    rationale TEXT NOT NULL,
    evidence_ids JSONB,
    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

This schema keeps the database compatible with both spatial analysis and agronomic decision support.

---

## 5. Required Python dependencies

Install the MCP server and supporting libraries:

```bash
python -m venv .venv
source .venv/bin/activate
pip install "mcp[cli]" fastmcp sqlalchemy psycopg[binary] geoalchemy2 pandas numpy requests python-dotenv
```

If the project already has Django/PostGIS dependencies, keep those and add only the MCP-related packages.

---

## 6. Environment variables

Create a file such as `.env` in the project root:

```env
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=agrivision
POSTGRES_USER=agrivision_user
POSTGRES_PASSWORD=strong_password
POSTGIS_SCHEMA=public

OPENWEATHER_API_KEY=your_key_here
EARTHENGINE_PROJECT=your_earth_engine_project

AGRI_MCP_NAME=maize-health-yield
AGRI_MCP_LOG_LEVEL=INFO
```

These values are used by the custom MCP server and the borrowed Postgres/PostGIS server connection string.

---

## 7. Step 1: Build the custom FastMCP server

Create a file named `maize_health_yield_mcp.py` in the project root or under a dedicated `mcp/` directory.

### 7.1 Example server skeleton

```python
import os
import json
from datetime import datetime
from typing import List, Dict, Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from mcp.server.fastmcp import FastMCP

load_dotenv()

mcp = FastMCP("maize-health-yield")

DB_URL = (
    f"postgresql+psycopg://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}"
    f"@{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
)
engine: Engine = create_engine(DB_URL, future=True)


@mcp.tool()
def get_plot_status(plot_id: str) -> Dict[str, Any]:
    """Return field, crop, soil, and growth-stage information for a maize plot."""
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT f.id, f.field_name, cs.crop_type, cs.planting_date, cs.growth_stage,
                       ROUND(s.ph, 2) AS ph, ROUND(s.organic_carbon, 2) AS organic_carbon
                FROM fields f
                LEFT JOIN crop_seasons cs ON cs.field_id = f.id
                LEFT JOIN soil_profiles s ON s.field_id = f.id
                WHERE f.id = :plot_id
                ORDER BY cs.created_at DESC
                LIMIT 1
            """), {"plot_id": int(plot_id)}
        ).mappings().first()

    if row is None:
        return {"status": "not_found", "plot_id": plot_id}

    return {
        "plot_id": plot_id,
        "field_name": row["field_name"],
        "crop_type": row["crop_type"],
        "planting_date": str(row["planting_date"]),
        "growth_stage": row["growth_stage"],
        "soil_ph": row["ph"],
        "organic_carbon": row["organic_carbon"],
        "status": "ok"
    }


@mcp.tool()
def analyze_crop_telemetry(plot_id: str) -> Dict[str, Any]:
    """Return maize health telemetry and yield estimate for a field."""
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT hs.ndvi, hs.evi, hs.ndmi, hs.savi,
                       hs.overall_health_score,
                       hs.water_stress_index,
                       hs.soil_health_score,
                       yp.predicted_yield_t_ha,
                       yp.limiting_factors,
                       hs.evidence_id
                FROM maize_health_snapshots hs
                LEFT JOIN yield_predictions yp ON yp.field_id = hs.field_id
                WHERE hs.field_id = :plot_id
                ORDER BY hs.captured_at DESC
                LIMIT 1
            """), {"plot_id": int(plot_id)}
        ).mappings().first()

    if row is None:
        return {"status": "insufficient_data", "plot_id": plot_id}

    return {
        "plot_id": plot_id,
        "ndvi": row["ndvi"],
        "evi": row["evi"],
        "ndmi": row["ndmi"],
        "savi": row["savi"],
        "overall_health_score": row["overall_health_score"],
        "water_stress_index": row["water_stress_index"],
        "soil_health_score": row["soil_health_score"],
        "predicted_yield_t_ha": row["predicted_yield_t_ha"],
        "limiting_factors": row["limiting_factors"],
        "evidence_id": row["evidence_id"],
        "status": "ok"
    }


@mcp.tool()
def evaluate_calendar_window(crop_stage: str, rain_anomaly: float, spray_risk: bool) -> Dict[str, Any]:
    """Deterministic agronomic check for planting, spraying, and decision windows."""
    action = "HOLD"
    rationale = []

    if crop_stage in {"vegetative", "flowering", "grain_filling"}:
        if rain_anomaly < -20:
            action = "PLANT"
            rationale.append("Rainfall deficit is large enough to require moisture-aware agricultural planning.")
        elif rain_anomaly > 20 and spray_risk:
            action = "HOLD"
            rationale.append("High rainfall and spray risk indicate operations should be delayed.")
        else:
            action = "SPRAY"
            rationale.append("Conditions support an operational window with manageable weather risk.")
    else:
        action = "HOLD"
        rationale.append("Growth stage is outside the active intervention window.")

    return {
        "decision": action,
        "crop_stage": crop_stage,
        "rain_anomaly": rain_anomaly,
        "spray_risk": spray_risk,
        "rationale": rationale
    }


@mcp.tool()
def draft_advisory(plot_id: str, action: str, evidence_ids: List[str], rationale: str) -> Dict[str, Any]:
    """Persist a maize agronomy advisory draft with approval status."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                INSERT INTO advisory_drafts(field_id, action, rationale, evidence_ids, status)
                VALUES (:field_id, :action, :rationale, :evidence_ids::jsonb, 'PENDING_APPROVAL')
            """), {
                "field_id": int(plot_id),
                "action": action,
                "rationale": rationale,
                "evidence_ids": json.dumps(evidence_ids)
            }
        )
        conn.commit()

    return {
        "status": "saved",
        "plot_id": plot_id,
        "action": action,
        "evidence_ids": evidence_ids,
        "approval_status": "PENDING_APPROVAL"
    }


if __name__ == "__main__":
    mcp.run()
```

This example matches the Phase 1 hackathon requirements:

- tool-based interface
- structured output payloads
- evidence IDs for traceability
- action tool that writes a draft advisory record
- stdio MCP mode via mcp.run()

---

## 8. Step 2: Configure the borrowed 3rd-party Postgres/PostGIS MCP server

The hackathon guide explicitly asks for a borrowed, maintained third-party server instead of writing a redundant SQL layer. This is the correct approach for field history and geospatial analysis.

### 8.1 Preferred pattern

Use an official or trusted Postgres/PostGIS MCP server from the MCP ecosystem, or a maintained Dockerized server, and point it at your agricultural database.

### 8.2 Example config

```json
{
  "mcpServers": {
    "agri-postgis": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--network",
        "host",
        "ghcr.io/modelcontextprotocol/server-postgres",
        "--connection-string",
        "postgresql://agrivision_user:strong_password@localhost:5432/agrivision"
      ]
    }
  }
}
```

If the server is a Python MCP server rather than a Docker package, adapt the command to run the Python entry point instead.

### 8.3 Important requirement

The third-party server should be configured as a read-oriented data layer. The standard read tools should be enough for the agent to:

- query historical yield records
- inspect plot-level time series
- run geospatial lookups on field polygons
- discover relevant seasonal patterns without custom SQL wrappers

The custom AgriVision MCP server remains responsible for agronomy-specific logic and advisory drafting.

---

## 9. Recommended field-specific tool set

For the maize health/yield section, the MCP tool surface should include the following standard tools:

### 9.1 Read tools

- get_plot_status(plot_id)
- analyze_crop_telemetry(plot_id)
- get_historical_yield_trend(plot_id)
- get_soil_profile(plot_id)
- get_weather_window(plot_id, days=30)
- get_field_geometry(plot_id)

### 9.2 Decision tools

- evaluate_calendar_window(crop_stage, rain_anomaly, spray_risk)
- assess_maize_stress(plot_id)
- estimate_yield_risk(plot_id)

### 9.3 Action tools

- draft_advisory(plot_id, action, evidence_ids, rationale)

This matches the Phase 1 recommendation in the hackathon PDF and gives the agent a clear separation between data retrieval, analysis, and action.

---

## 10. How the external agent should use MCP

The orchestrator or agent should do the following:

1. Open a client session to the custom maize FastMCP server.
2. Open a second client session to the borrowed Postgres/PostGIS server.
3. Call session.list_tools() at startup.
4. Build tool wrappers from the returned JSON schemas.
5. Use the agent to select the right tools based on the field ID or plot ID.
6. Verify evidence before taking action.
7. Use draft_advisory only after enough evidence is present and before any human approval step.

---

## 11. Tooling and guardrails specific to maize

To prevent low-quality recommendations, include these guardrails:

- require at least two evidence IDs before drafting an advisory
- block decisions if crop telemetry or soil parameters are missing
- avoid operational recommendations during unsafe weather conditions
- treat maize flowering and grain-filling periods as high-risk windows
- log evidence sources for each recommendation

This is especially important because maize health is sensitive to:

- water stress
- heat stress
- rainfall anomaly
- weak soil retention
- pest pressure in humid conditions

---

## 12. Verification checklist

Before using the MCP layer in production, validate the following:

### 12.1 Custom server validation

```bash
python maize_health_yield_mcp.py
```

Then confirm that the server exposes the expected tools through MCP standard IO.

### 12.2 Postgres/PostGIS validation

Run a read-only query through the borrowed third-party MCP server to verify the connection:

```sql
SELECT id, field_name, ST_AsText(geom)
FROM fields
LIMIT 5;
```

### 12.3 Data flow validation

- get_plot_status("KE-001") returns crop and soil context
- analyze_crop_telemetry("KE-001") returns structured health and yield payload
- evaluate_calendar_window("flowering", -30, true) returns a deterministic decision
- draft_advisory(...) creates a PENDING_APPROVAL record

---

## 13. Practical deployment notes

- Keep the Postgres/PostGIS server read-only for most workflows.
- Keep advisory drafting inside the custom maize MCP server.
- Use evidence IDs and timestamps for traceability.
- Save audit records when officers approve or reject a recommendation.
- Keep the custom server small and focused on agronomy logic instead of raw database management.

---

## 14. Summary

The Phase 1 MCP layer for the maize health and yield section should follow the hackathon pattern exactly:

- custom FastMCP server for agronomy-specific intelligence
- borrowed third-party Postgres/PostGIS MCP server for field and historical datasets
- deterministic tool calls for crop and stress assessment
- structured advisory drafts with evidence tracking
- read-only third-party access to keep the system maintainable and reusable

This gives the project a clean separation between:

1. data access and historical context, and
2. agronomic analysis and decision support for maize health and yield estimation.

This is the correct architecture for integrating external third-party MCP access while preserving project-specific agronomic logic.
