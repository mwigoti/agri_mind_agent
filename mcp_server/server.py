import sys
import hmac
import os
from typing import Dict, Any, Optional, List
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from .config import logger
from .clients.backend_client import (
    fetch_plot_status_from_db,
    fetch_crop_telemetry_from_db,
    evaluate_calendar_window_helper,
    draft_advisory_helper,
)

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()
MCP_HTTP_HOST = os.getenv("MCP_HTTP_HOST", "127.0.0.1")
MCP_HTTP_PORT = int(os.getenv("MCP_HTTP_PORT", "8002"))
MCP_HTTP_TOKEN = os.getenv("MCP_HTTP_BEARER_TOKEN", "")
MCP_HTTP_PATH = os.getenv("MCP_HTTP_PATH", "/mcp")
MCP_ALLOWED_HOSTS = [host.strip() for host in os.getenv("MCP_ALLOWED_HOSTS", f"127.0.0.1:{MCP_HTTP_PORT},localhost:{MCP_HTTP_PORT}").split(",") if host.strip()]
MCP_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("MCP_ALLOWED_ORIGINS", "").split(",") if origin.strip()]

security = None
if MCP_TRANSPORT == "streamable-http":
    security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=MCP_ALLOWED_HOSTS,
        allowed_origins=MCP_ALLOWED_ORIGINS,
    )

# Keep stdio as the local default; remote MCP clients use authenticated Streamable HTTP.
mcp = FastMCP(
    "AgriMind",
    host=MCP_HTTP_HOST,
    port=MCP_HTTP_PORT,
    streamable_http_path=MCP_HTTP_PATH,
    stateless_http=True,
    transport_security=security,
)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1: get_plot_status
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_plot_status(plot_id: str) -> Dict[str, Any]:
    """
    Establish identity and ground-truth phenological baseline for a maize plot.
    
    This must be the agent's very first cognitive action before evaluating 
    environmental or remote sensing telemetry:
      1. Validates that the plot exists in the GIS database.
      2. Returns crop variety and water/drought sensitivities.
      3. Identifies the current phenological growth stage (e.g., Silking R1 vs Maturity R6).
      4. Provides farmer contact details for downstream advisory dispatch.
    
    Args:
        plot_id (str): The unique plot identifier (e.g., '12' or 'PLOT-12').
        
    Returns:
        Dict[str, Any]: A deterministic JSON dictionary containing plot identity, 
                        crop sensitivity, phenology baseline, soil data, and farmer details.
                        Returns {"status": "NOT_FOUND"} or {"status": "ERROR"} on failure.
    """
    logger.info(f"Tool invoked: get_plot_status with plot_id='{plot_id}'")
    return fetch_plot_status_from_db(plot_id)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2: analyze_crop_telemetry
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def analyze_crop_telemetry(plot_id: str) -> Dict[str, Any]:
    """
    Retrieve satellite vegetation indices, rainfall anomalies, soil moisture,
    predicted yield metrics, and auditable Evidence IDs for a plot.
    
    The agent uses this tool to observe empirical stresses acting on the crop:
      1. Evaluates vegetative vigor (Sentinel-2 NDVI, EVI, NDRE peak).
      2. Checks moisture and climate deficits (CHIRPS rainfall anomaly, WSI).
      3. Reviews ML yield predictions and identified limiting factors.
      4. Collects verifiable Evidence IDs required before an advisory can be drafted.
    
    Args:
        plot_id (str): The unique plot identifier (e.g., '12' or 'PLOT-12').
        
    Returns:
        Dict[str, Any]: A structured telemetry payload containing:
          - 'status': 'OK' on success, 'INSUFFICIENT_EVIDENCE' if data is missing or stale.
          - 'freshness': Timestamp analysis verifying data validity.
          - 'telemetry': Aggregated vegetation, climate, and ML yield predictions.
          - 'evidence_records': List of auditable evidence objects with deterministic IDs.
          - 'evidence_ids': Clean list of string IDs ready for Tool 4 justification.
          - 'stress_flags': Detected agronomic risk alerts.
    """
    logger.info(f"Tool invoked: analyze_crop_telemetry with plot_id='{plot_id}'")
    return fetch_crop_telemetry_from_db(plot_id)


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3: evaluate_calendar_window
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def evaluate_calendar_window(
    crop: str = "maize",
    phenological_stage: str = "vegetative",
    rainfall_anomaly_pct: Optional[float] = None,
    soil_moisture_vwc: Optional[float] = None,
    forecast_rain_next_48h_mm: Optional[float] = None,
    plot_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate biological safety limits, chemical washout risks, and operational feasibility windows.
    
    Acts as an Agronomic Safety Inspector before drafting any field recommendation:
      1. Evaluates critical biological windows (e.g., silking drought sensitivity, germination moisture).
      2. Checks meteorological spray limits (washout risk if rain > 15mm, pollinator safety during flowering).
      3. Checks fertilizer root scorch limits (soil moisture below osmotic wilting threshold).
      4. Produces auditable Rule Citation IDs (e.g., 'RULE-MAIZE-FLOWERING-02') to justify actions.
    
    Args:
        crop (str): The crop name (default: 'maize').
        phenological_stage (str): Current crop growth stage (e.g., 'Vegetative_V6', 'Silking_R1').
        rainfall_anomaly_pct (Optional[float]): CHIRPS seasonal anomaly vs the same planting-to-observation period in the previous five years.
        soil_moisture_vwc (Optional[float]): Volumetric soil water content fraction (e.g., 0.14 = 14%); null when no recent measurement is saved.
        forecast_rain_next_48h_mm (Optional[float]): Sum of fresh saved forecast precipitation for the next two calendar days; null when unavailable.
        plot_id (Optional[str]): Optional plot ID for reference.
        
    Returns:
        Dict[str, Any]: A deterministic feasibility assessment containing:
          - 'safety_checks': Booleans indicating if individual operations are physically safe.
          - 'operational_windows': Status of planting, spraying, and top-dressing windows.
          - 'threshold_violations': Specific breaches with observed values and biological impacts.
          - 'rule_citations': List of formal rule IDs (required citation proof for Tool 4).
    """
    logger.info(
        f"Tool invoked: evaluate_calendar_window for crop='{crop}', "
        f"stage='{phenological_stage}', rain_anomaly={rainfall_anomaly_pct}%, "
        f"moisture={soil_moisture_vwc}, forecast_rain={forecast_rain_next_48h_mm}mm"
    )
    return evaluate_calendar_window_helper(
        crop=crop,
        phenological_stage=phenological_stage,
        rainfall_anomaly_pct=rainfall_anomaly_pct,
        soil_moisture_vwc=soil_moisture_vwc,
        forecast_rain_next_48h_mm=forecast_rain_next_48h_mm,
        plot_id=plot_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4: draft_advisory_for_approval (Stateful Action & Human Gatekeeper)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def draft_advisory_for_approval(
    plot_id: str,
    recommended_action: str,
    advisory_rationale: str,
    evidence_ids: List[str]
) -> Dict[str, Any]:
    """
    Draft an agronomic advisory for a plot and queue it for mandatory human officer review.
    
    This is the stateful mutating action tool of AgriMind. It enforces the non-negotiable
    human-in-the-loop safety protocol:
      1. Every recommendation is persisted to the database with status 'PENDING_APPROVAL'.
      2. No advisory is ever sent directly to a farmer without named officer authorization.
      3. Anti-Hallucination Gate: Strictly requires at least 2 verifiable evidence citations
         (telemetry tokens EVID-... and agronomic rules RULE-...). Submissions with < 2 citations
         are rejected without mutating the database.
      4. Deduplication: Idempotent within a 24-hour window to prevent queue spamming.
    
    Args:
        plot_id (str): The target plot identifier (e.g., '101' or 'PLOT-101').
        recommended_action (str): The operational directive ('PLANT', 'SPRAY', 'HOLD', 'HARVEST').
        advisory_rationale (str): Plain-language agronomic explanation and guidance for the officer/farmer.
        evidence_ids (List[str]): List of >= 2 verifiable evidence citation IDs from Tools 2 and 3
                                  (e.g., ['EVID-CHIRPS-RAIN-101-20261012', 'RULE-MAIZE-FLOWERING-02']).
        
    Returns:
        Dict[str, Any]: Confirmation receipt containing:
          - 'status': 'OK' on success, or 'ERROR' / 'INSUFFICIENT_EVIDENCE'.
          - 'advisory_id': The unique audit tracking ID (e.g., 'ADV-20261012-PLOT101-143022').
          - 'queue_status': Hardcoded to 'PENDING_APPROVAL'.
          - 'requires_officer_review': True.
          - 'triage_summary': Summary payload for human extension desk triage.
    """
    logger.info(
        f"Tool invoked: draft_advisory_for_approval for plot_id='{plot_id}', "
        f"action='{recommended_action}', citations={len(evidence_ids) if evidence_ids else 0}"
    )
    return draft_advisory_helper(
        plot_id=plot_id,
        recommended_action=recommended_action,
        advisory_rationale=advisory_rationale,
        evidence_ids=evidence_ids,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 5: compute_vra_prescription (Variable Rate Application & Resource Optimization)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def compute_vra_prescription(
    plot_id: str,
    target_input: str = "CAN_nitrogen_top_dressing",
    num_zones: int = 3,
) -> Dict[str, Any]:
    """
    Check whether measured zonal data and validated rates are available for a VRA prescription.

    Args:
        plot_id (str): The unique plot identifier (e.g., '101' or 'PLOT-101').
        target_input (str): Target fertilizer or nutrient type.
        num_zones (int): Number of management clusters (default: 3).

    Returns:
        Dict[str, Any]: An explicit evidence gap until required zonal inputs are available.
    """
    logger.info(f"Tool invoked: compute_vra_prescription for plot_id='{plot_id}', input='{target_input}'")
    return {
        "status": "INSUFFICIENT_EVIDENCE",
        "plot_id": plot_id,
        "target_input": target_input,
        "requested_zones": num_zones,
        "message": "A prescription requires field-level zonal raster values and a validated agronomic rate. Aggregate field telemetry cannot support zone prescriptions.",
        "missing_inputs": ["zonal_ndvi_or_soil_grid", "validated_rate_by_zone", "area_by_zone"],
    }


class BearerTokenMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request, call_next):
        supplied = request.headers.get("authorization", "")
        expected = f"Bearer {self.token}"
        if not hmac.compare_digest(supplied, expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        return await call_next(request)


if __name__ == "__main__":
    if MCP_TRANSPORT == "streamable-http":
        if not MCP_HTTP_TOKEN:
            raise RuntimeError("MCP_HTTP_BEARER_TOKEN is required for Streamable HTTP transport")
        import uvicorn

        app = mcp.streamable_http_app()
        app.add_middleware(BearerTokenMiddleware, token=MCP_HTTP_TOKEN)
        logger.info("Starting AgriMind FastMCP Server over authenticated Streamable HTTP on %s:%s%s", MCP_HTTP_HOST, MCP_HTTP_PORT, MCP_HTTP_PATH)
        uvicorn.run(app, host=MCP_HTTP_HOST, port=MCP_HTTP_PORT)
    else:
        logger.info("Starting AgriMind FastMCP Server over stdio...")
        mcp.run()
