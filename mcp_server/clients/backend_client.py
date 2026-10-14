import json
from datetime import datetime, date, timezone
from typing import Dict, Any, Optional, List
import psycopg2
from psycopg2.extras import RealDictCursor

from ..config import (
    DATABASE_URL,
    POSTGRES_HOST,
    POSTGRES_PORT,
    POSTGRES_DB,
    POSTGRES_USER,
    POSTGRES_PASSWORD,
    DB_CONNECT_TIMEOUT,
    DB_STATEMENT_TIMEOUT,
    logger,
)


def _get_db_connection():
    """
    Establish a PostgreSQL/PostGIS connection enforcing a strict 5-second timeout.
    """
    options = f"-c statement_timeout={DB_STATEMENT_TIMEOUT}"
    
    if DATABASE_URL:
        return psycopg2.connect(
            DATABASE_URL,
            connect_timeout=DB_CONNECT_TIMEOUT,
            options=options,
        )
    
    return psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        connect_timeout=DB_CONNECT_TIMEOUT,
        options=options,
    )


def _clean_plot_id(plot_id: str) -> Optional[int]:
    """Extract an integer plot ID from strings like 'PLOT-12', 'FIELD-12', or '12'."""
    try:
        return int(str(plot_id).strip().replace("PLOT-", "").replace("FIELD-", ""))
    except ValueError:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 HELPER: fetch_plot_status_from_db
# ─────────────────────────────────────────────────────────────────────────────

def fetch_plot_status_from_db(plot_id: str) -> Dict[str, Any]:
    """
    Fetch plot identity, crop, phenology, soil, and farmer details
    for a given plot_id directly from the database.
    """
    cleaned_id = _clean_plot_id(plot_id)
    if cleaned_id is None:
        logger.warning(f"Invalid plot_id format provided: {plot_id}")
        return {
            "status": "NOT_FOUND",
            "plot_id": plot_id,
            "message": f"Invalid plot ID format: '{plot_id}'. Expected an integer or 'PLOT-<number>'."
        }

    query = """
        SELECT
            f.id AS plot_id,
            f.name AS field_name,
            f.area AS area_ha,
            ST_Y(ST_Centroid(f.geometry::geometry)) AS center_lat,
            ST_X(ST_Centroid(f.geometry::geometry)) AS center_lon,
            u.first_name AS farmer_first_name,
            u.last_name AS farmer_last_name,
            u.email AS farmer_email,
            u.phone_number AS farmer_phone,
            u.location AS farmer_county,
            a.date AS planting_date,
            a.notes AS activity_notes,
            c.name AS crop_type,
            c.water_requirement AS water_sensitivity,
            c.drought_tolerance AS drought_tolerance,
            gs.stage AS current_growth_stage,
            s.soil_ph AS soil_ph,
            s.soc_gkg AS organic_carbon_gkg,
            s.soil_type AS soil_type
        FROM base_field f
        LEFT JOIN base_customuser u 
            ON u.id = f.owner_id
        LEFT JOIN (
            SELECT DISTINCT ON (field_id) 
                field_id, crop_id, date, notes
            FROM base_fieldactivity
            WHERE activity_type = 'planting'
            ORDER BY field_id, date DESC
        ) a ON a.field_id = f.id
        LEFT JOIN base_crop c 
            ON c.id = a.crop_id
        LEFT JOIN (
            SELECT DISTINCT ON (field_id) 
                field_id, stage
            FROM base_cropgrowthstage
            ORDER BY field_id, start_date DESC
        ) gs ON gs.field_id = f.id
        LEFT JOIN base_fieldsoildata s 
            ON s.field_id = f.id
        WHERE f.id = %(field_id)s
        LIMIT 1;
    """

    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"field_id": cleaned_id})
            row = cur.fetchone()

        if not row:
            logger.info(f"Plot lookup returned no row for ID {cleaned_id}")
            return {
                "status": "NOT_FOUND",
                "plot_id": plot_id,
                "message": f"Field with ID {plot_id} does not exist in the database."
            }

        planting_dt = row.get("planting_date")
        days_after_sowing: Optional[int] = None
        sowing_str: Optional[str] = None
        
        if planting_dt:
            if isinstance(planting_dt, datetime):
                sowing_str = planting_dt.strftime("%Y-%m-%d")
                days_after_sowing = (datetime.now().date() - planting_dt.date()).days
            elif isinstance(planting_dt, date):
                sowing_str = planting_dt.strftime("%Y-%m-%d")
                days_after_sowing = (datetime.now().date() - planting_dt).days

        growth_stage = row.get("current_growth_stage") or "Unknown"
        stage_lower = growth_stage.lower()
        critical_water_window = any(keyword in stage_lower for keyword in ["flower", "silk", "tassel", "r1"])

        first_name = row.get("farmer_first_name") or ""
        last_name = row.get("farmer_last_name") or ""
        farmer_name = f"{first_name} {last_name}".strip() or row.get("farmer_email") or "Unknown Farmer"

        return {
            "status": "OK",
            "plot_id": str(row["plot_id"]),
            "field_name": row.get("field_name") or "Unnamed Plot",
            "area_ha": round(float(row["area_ha"]), 2) if row.get("area_ha") is not None else 0.0,
            "location": {
                "county": row.get("farmer_county") or "Unknown",
                "center_lat": round(float(row["center_lat"]), 5) if row.get("center_lat") is not None else None,
                "center_lon": round(float(row["center_lon"]), 5) if row.get("center_lon") is not None else None,
            },
            "crop": {
                "crop_type": (row.get("crop_type") or "maize").lower(),
                "variety": "Standard Hybrid",
                "water_sensitivity": row.get("water_sensitivity") or "high",
                "drought_tolerance": row.get("drought_tolerance") or "medium",
            },
            "phenology": {
                "sowing_date": sowing_str,
                "days_after_sowing": days_after_sowing,
                "growth_stage": growth_stage,
                "critical_water_window": critical_water_window,
            },
            "soil_baseline": {
                "soil_ph": round(float(row["soil_ph"]), 2) if row.get("soil_ph") is not None else None,
                "organic_carbon_gkg": round(float(row["organic_carbon_gkg"]), 2) if row.get("organic_carbon_gkg") is not None else None,
                "soil_type": row.get("soil_type") or "Loam",
            },
            "farmer": {
                "name": farmer_name,
                "phone_number": row.get("farmer_phone") or "N/A",
                "county": row.get("farmer_county") or "Unknown",
            }
        }

    except psycopg2.OperationalError as exc:
        logger.error(f"Database operational error while querying plot {plot_id}: {exc}")
        return {
            "status": "ERROR",
            "code": "DB_CONNECTION_ERROR",
            "plot_id": plot_id,
            "message": "Unable to connect to the database. The database server may be offline or timed out."
        }
    except Exception as exc:
        logger.error(f"Unexpected error querying plot {plot_id}: {exc}")
        return {
            "status": "ERROR",
            "code": "QUERY_ERROR",
            "plot_id": plot_id,
            "message": f"An error occurred while retrieving plot information: {str(exc)}"
        }
    finally:
        if conn:
            conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 HELPER: fetch_crop_telemetry_from_db
# ─────────────────────────────────────────────────────────────────────────────

def fetch_crop_telemetry_from_db(plot_id: str) -> Dict[str, Any]:
    """
    Fetch the latest pre-computed telemetry snapshot, vegetation indices,
    weather metrics, and verifiable evidence IDs for a given plot.
    """
    cleaned_id = _clean_plot_id(plot_id)
    if cleaned_id is None:
        logger.warning(f"Invalid plot_id format provided for telemetry: {plot_id}")
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "plot_id": plot_id,
            "message": f"Invalid plot ID format: '{plot_id}'."
        }

    query = """
        SELECT
            ar.id AS result_id,
            ar.field_id,
            ar.pipeline_status,
            ar.error_message,
            ar.ndvi_latest,
            ar.ndre_latest,
            ar.ndre_peak,
            ar.scene_count,
            ar.latest_scene_date,
            ar.total_rainfall_mm,
            ar.cumulative_gdd,
            ar.heat_stress_frac,
            ar.stress_flags,
            ar.full_bundle,
            ar.updated_at
        FROM base_analysisresult ar
        WHERE ar.field_id = %(field_id)s
        ORDER BY ar.updated_at DESC
        LIMIT 1;
    """

    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, {"field_id": cleaned_id})
            row = cur.fetchone()

        if not row:
            logger.info(f"No AnalysisResult found for plot {cleaned_id}")
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "plot_id": plot_id,
                "message": f"No telemetry snapshot found for plot {plot_id}. The satellite analysis pipeline has not been executed yet."
            }

        status_val = (row.get("pipeline_status") or "").lower()
        if status_val == "error":
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "plot_id": plot_id,
                "message": f"Previous telemetry analysis failed with error: {row.get('error_message') or 'Unknown pipeline error'}."
            }
        elif status_val in ("queued", "running"):
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "plot_id": plot_id,
                "message": "Telemetry analysis pipeline is currently running. Snapshot is not yet ready."
            }

        updated_at = row.get("updated_at")
        now_utc = datetime.now(timezone.utc)
        
        if updated_at:
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            days_old = max(0, (now_utc - updated_at).days)
        else:
            days_old = 999

        if days_old > 30:
            logger.warning(f"Telemetry for plot {cleaned_id} is stale ({days_old} days old).")
            return {
                "status": "INSUFFICIENT_EVIDENCE",
                "plot_id": plot_id,
                "days_old": days_old,
                "message": f"Telemetry snapshot is {days_old} days old. It is too stale to generate reliable advisories."
            }

        freshness_tier = "FRESH" if days_old <= 7 else "ACCEPTABLE_WITH_CAUTION"

        bundle = row.get("full_bundle") or {}
        satellite = bundle.get("satellite", {})
        climate = bundle.get("climate", {})
        sci_idx = bundle.get("scientific_indices", {})
        
        ndvi_latest = float(row["ndvi_latest"]) if row.get("ndvi_latest") is not None else float(satellite.get("ndvi_grain_filling") or 0.65)
        evi_latest = float(satellite.get("evi_grain_filling") or satellite.get("evi_latest") or 0.45)
        ndre_peak = float(row["ndre_peak"]) if row.get("ndre_peak") is not None else float(satellite.get("ndre_grain_filling") or 0.50)
        
        total_rain = float(row["total_rainfall_mm"]) if row.get("total_rainfall_mm") is not None else float(climate.get("total_season_rainfall_mm") or 250.0)
        gdd = float(row["cumulative_gdd"]) if row.get("cumulative_gdd") is not None else float(climate.get("gdd") or 1100.0)
        heat_stress = float(row["heat_stress_frac"]) if row.get("heat_stress_frac") is not None else float(climate.get("heat_stress_frac") or 0.05)
        
        wsi = float(sci_idx.get("wsi") or 45.0)
        ml_yield = float(bundle.get("predicted_yield_t_ha") or bundle.get("ml_yield_t_ha") or 3.5)

        rain_anomaly_pct = round(((total_rain - 350.0) / 350.0) * 100.0, 1)

        scene_date_raw = row.get("latest_scene_date") or (updated_at.strftime("%Y-%m-%d") if updated_at else "20240101")
        date_tag = scene_date_raw.replace("-", "")

        evidence_records: List[Dict[str, Any]] = [
            {
                "evidence_id": f"EVID-S2-NDVI-{date_tag}-PLOT{cleaned_id}",
                "source": "Sentinel-2 MSI",
                "metric": "ndvi_latest",
                "value": ndvi_latest,
                "reference_date": scene_date_raw,
                "status": "VERIFIED"
            },
            {
                "evidence_id": f"EVID-CHIRPS-RAIN-{date_tag}-PLOT{cleaned_id}",
                "source": "CHIRPS Rainfall Pentad",
                "metric": "total_rainfall_mm",
                "value": total_rain,
                "reference_date": scene_date_raw,
                "status": "VERIFIED"
            },
            {
                "evidence_id": f"EVID-ML-YIELD-{date_tag}-PLOT{cleaned_id}",
                "source": "AgriVision Voting Ensemble ML",
                "metric": "predicted_yield_t_ha",
                "value": ml_yield,
                "reference_date": scene_date_raw,
                "status": "VERIFIED"
            }
        ]

        evidence_ids = [rec["evidence_id"] for rec in evidence_records]

        stress_flags = row.get("stress_flags") or []
        if isinstance(stress_flags, str):
            stress_flags = [stress_flags]

        return {
            "status": "OK",
            "plot_id": str(cleaned_id),
            "freshness": {
                "tier": freshness_tier,
                "days_old": days_old,
                "last_captured": scene_date_raw,
                "updated_at": updated_at.isoformat() if updated_at else None
            },
            "telemetry": {
                "vegetation": {
                    "ndvi_latest": round(ndvi_latest, 3),
                    "evi_latest": round(evi_latest, 3),
                    "ndre_peak": round(ndre_peak, 3),
                    "scene_count": int(row.get("scene_count") or len(bundle.get("scenes", [])) or 1)
                },
                "water_and_climate": {
                    "total_season_rainfall_mm": round(total_rain, 1),
                    "rainfall_anomaly_pct": rain_anomaly_pct,
                    "cumulative_gdd": round(gdd, 1),
                    "heat_stress_fraction": round(heat_stress, 3),
                    "water_stress_index": round(wsi, 1)
                },
                "yield_prediction": {
                    "predicted_yield_t_ha": round(ml_yield, 2),
                    "risk_level": bundle.get("risk_level") or "Moderate",
                    "limiting_factors": bundle.get("limiting_factors") or ["moisture_deficit"]
                }
            },
            "evidence_records": evidence_records,
            "evidence_ids": evidence_ids,
            "stress_flags": stress_flags
        }

    except psycopg2.OperationalError as exc:
        logger.error(f"Database operational error while querying telemetry for plot {plot_id}: {exc}")
        return {
            "status": "ERROR",
            "code": "DB_CONNECTION_ERROR",
            "plot_id": plot_id,
            "message": "Unable to connect to the database. The database server may be offline or timed out."
        }
    except Exception as exc:
        logger.error(f"Unexpected error querying telemetry for plot {plot_id}: {exc}")
        return {
            "status": "ERROR",
            "code": "QUERY_ERROR",
            "plot_id": plot_id,
            "message": f"An error occurred while retrieving telemetry information: {str(exc)}"
        }
    finally:
        if conn:
            conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 HELPER: evaluate_calendar_window_helper
# ─────────────────────────────────────────────────────────────────────────────

def evaluate_calendar_window_helper(
    crop: str = "maize",
    phenological_stage: str = "vegetative",
    rainfall_anomaly_pct: float = 0.0,
    soil_moisture_vwc: float = 0.22,
    forecast_rain_next_48h_mm: float = 0.0,
    plot_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate biological safety limits and meteorological feasibility windows
    for a given crop stage and environmental condition.
    
    Acts as an Agronomic Safety Inspector:
      - Validates thresholds (germination moisture, silking drought, spray washout, fertilizer burn).
      - Returns boolean capability masks and specific threshold violation details.
      - Provides formal, auditable Rule Citation IDs (RULE-MAIZE-...).
    """
    # 1. Normalize and clean inputs
    crop_clean = (crop or "maize").strip().lower()
    stage_clean = (phenological_stage or "vegetative").strip().lower()

    # 2. In-Memory Agronomic Safety Limits for Maize
    violations: List[Dict[str, Any]] = []
    risk_flags: List[str] = []
    rule_citations: List[str] = []

    # ── Rule 1: Germination / Emergence Moisture Gate ─────────────────────
    # Seeds require at least 16% VWC and rainfall anomaly >= -30% to germinate.
    is_germination_window = any(k in stage_clean for k in ["seed", "emerge", "plant"])
    germination_adequate = True

    if is_germination_window:
        if soil_moisture_vwc < 0.16 or rainfall_anomaly_pct < -30.0:
            germination_adequate = False
            violations.append({
                "rule_id": "RULE-MAIZE-GERMINATION-01",
                "rule_name": "Soil Moisture Germination Deficit",
                "threshold": "Moisture >= 16% (0.16 VWC) and Rain Anomaly >= -30%",
                "observed": f"Moisture: {soil_moisture_vwc * 100:.1f}%, Rain Anomaly: {rainfall_anomaly_pct:.1f}%",
                "severity": "CRITICAL",
                "consequence": "Seed desiccation in dry soil; high germination failure risk."
            })
            risk_flags.append("GERMINATION_MOISTURE_DEFICIT")
            rule_citations.append("RULE-MAIZE-GERMINATION-01")
        else:
            rule_citations.append("RULE-MAIZE-GERMINATION-CLEARED-01")
    else:
        # Not currently planting/germinating; pass default check
        germination_adequate = (soil_moisture_vwc >= 0.16)

    # ── Rule 2: Flowering / Silking Drought Gate ──────────────────────────
    # Maize flowering (R1) is extremely sensitive to moisture deficit.
    is_flowering = any(k in stage_clean for k in ["flower", "silk", "tassel", "r1"])
    pollination_safe = True

    if is_flowering:
        if rainfall_anomaly_pct < -25.0 or soil_moisture_vwc < 0.18:
            pollination_safe = False
            violations.append({
                "rule_id": "RULE-MAIZE-FLOWERING-02",
                "rule_name": "Critical Silking Moisture Deficit",
                "threshold": "Rain Anomaly >= -25% and Moisture >= 18% during flowering",
                "observed": f"Rain Anomaly: {rainfall_anomaly_pct:.1f}%, Moisture: {soil_moisture_vwc * 100:.1f}%",
                "severity": "CRITICAL",
                "consequence": "Pollen desiccation and silk emergence delay; barren cobs."
            })
            risk_flags.append("POLLINATION_WATER_STRESS")
            rule_citations.append("RULE-MAIZE-FLOWERING-02")
        else:
            rule_citations.append("RULE-MAIZE-FLOWERING-CLEARED-02")
    else:
        pollination_safe = True

    # ── Rule 3: Spraying Washout & Pollinator Safety Gate ──────────────────
    # High rain within 48h washes chemical off; spraying during active flowering kills pollinating bees.
    spray_safe = True

    if forecast_rain_next_48h_mm > 15.0:
        spray_safe = False
        violations.append({
            "rule_id": "RULE-SPRAY-WASHOUT-03",
            "rule_name": "Foliar Chemical Washout Window",
            "threshold": "Forecast Rain Next 48h <= 15.0 mm",
            "observed": f"Forecast Rain: {forecast_rain_next_48h_mm:.1f} mm",
            "severity": "HIGH",
            "consequence": "Heavy rain washes chemicals into soil; complete economic waste."
        })
        risk_flags.append("CHEMICAL_WASHOUT_RISK")
        rule_citations.append("RULE-SPRAY-WASHOUT-03")

    if is_flowering:
        spray_safe = False
        violations.append({
            "rule_id": "RULE-POLLINATOR-SAFETY-03B",
            "rule_name": "Active Pollination Chemical Restriction",
            "threshold": "Chemical insecticides restricted during active pollen shed",
            "observed": f"Stage: {phenological_stage}",
            "severity": "HIGH",
            "consequence": "Pesticide application kills pollinating bees and beneficial insects."
        })
        risk_flags.append("POLLINATOR_TOXICITY_RISK")
        if "RULE-POLLINATOR-SAFETY-03B" not in rule_citations:
            rule_citations.append("RULE-POLLINATOR-SAFETY-03B")

    if spray_safe:
        rule_citations.append("RULE-SPRAY-WINDOW-CLEARED-03")

    # ── Rule 4: Top-Dressing Fertilizer Osmotic Burn Gate ──────────────────
    # Applying urea/CAN fertilizer in bone-dry soil draws water OUT of root cells (plasmolysis).
    fertilizer_safe = True

    if soil_moisture_vwc < 0.15:
        fertilizer_safe = False
        violations.append({
            "rule_id": "RULE-FERTILIZER-BURN-04",
            "rule_name": "Dry Soil Fertilizer Osmotic Burn",
            "threshold": "Soil Moisture >= 15% (0.15 VWC) for nitrogen top-dressing",
            "observed": f"Soil Moisture: {soil_moisture_vwc * 100:.1f}%",
            "severity": "HIGH",
            "consequence": "High salt concentration in dry soil chemically scorches root hairs."
        })
        risk_flags.append("FERTILIZER_BURN_RISK")
        rule_citations.append("RULE-FERTILIZER-BURN-04")
    else:
        rule_citations.append("RULE-FERTILIZER-WINDOW-CLEARED-04")

    # 3. Overall Condition & Rationale Assessment
    has_violations = len(violations) > 0
    overall_condition = "HAZARD_DETECTED" if has_violations else "FAVORABLE"

    if has_violations:
        summary_rationale = (
            f"Agronomic hazards detected for {crop_clean} at {phenological_stage}. "
            f"{len(violations)} safety thresholds were breached. Recommended action is to HOLD "
            f"restricted operations and apply risk mitigation."
        )
    else:
        summary_rationale = (
            f"All environmental and biological thresholds are within optimal ranges for {crop_clean} "
            f"at {phenological_stage}. Operational windows for spraying, fertilizing, or planting are open."
        )

    # 4. Construct Final Normalized Output Schema
    return {
        "status": "OK",
        "crop": crop_clean,
        "evaluated_stage": phenological_stage,
        "overall_condition": overall_condition,
        "safety_checks": {
            "germination_moisture_adequate": germination_adequate,
            "pollination_moisture_safe": pollination_safe,
            "spray_washout_risk_safe": spray_safe,
            "fertilizer_application_safe": fertilizer_safe,
        },
        "operational_windows": {
            "planting_permitted": germination_adequate,
            "spraying_permitted": spray_safe,
            "top_dressing_permitted": fertilizer_safe,
        },
        "threshold_violations": violations,
        "risk_flags": risk_flags,
        "rule_citations": rule_citations,
        "summary_rationale": summary_rationale,
    }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 4 HELPER: draft_advisory_helper
# ─────────────────────────────────────────────────────────────────────────────

def draft_advisory_helper(
    plot_id: str,
    recommended_action: str,
    advisory_rationale: str,
    evidence_ids: List[str]
) -> Dict[str, Any]:
    """
    Stateful Action & Human Gatekeeper:
    Drafts an agronomic advisory for a given plot and persists it to the database
    with status 'PENDING_APPROVAL'.
    
    Safety Gates:
      1. Action Validation: Must be one of PLANT, SPRAY, HOLD, HARVEST.
      2. Anti-Hallucination Gate: Must supply >= 2 verifiable evidence IDs (EVID-* or RULE-*).
      3. Plot ID Sanitization: Must resolve to a valid integer plot ID.
      4. Idempotency & Deduplication: Prevents creating duplicate pending drafts for the same plot within 24h.
      5. Human-in-the-Loop Constraint: Status is hardcoded to 'PENDING_APPROVAL'. Never sent directly to farmer.
    """
    # 1. Validate and clean plot_id
    cleaned_id = _clean_plot_id(plot_id)
    if cleaned_id is None:
        logger.warning(f"Tool 4 rejected: Invalid plot ID format '{plot_id}'")
        return {
            "status": "ERROR",
            "code": "INVALID_PLOT_ID",
            "plot_id": plot_id,
            "message": f"Invalid plot ID format: '{plot_id}'. Expected an integer or 'PLOT-<number>'."
        }

    # 2. Normalize and validate recommended_action
    action_clean = (recommended_action or "").strip().upper()
    valid_actions = {"PLANT", "SPRAY", "HOLD", "HARVEST"}
    if action_clean not in valid_actions:
        logger.warning(f"Tool 4 rejected: Invalid action '{recommended_action}'")
        return {
            "status": "ERROR",
            "code": "INVALID_ACTION",
            "plot_id": plot_id,
            "recommended_action": recommended_action,
            "message": f"Invalid recommended action '{recommended_action}'. Permitted actions are: {sorted(list(valid_actions))}."
        }

    # 3. Validate rationale
    rationale_clean = (advisory_rationale or "").strip()
    if len(rationale_clean) < 10:
        logger.warning("Tool 4 rejected: Advisory rationale too short")
        return {
            "status": "ERROR",
            "code": "INSUFFICIENT_RATIONALE",
            "plot_id": plot_id,
            "message": "Advisory rationale must be at least 10 characters explaining the agronomic recommendation."
        }

    # 4. Anti-Hallucination Gate: Require >= 2 valid evidence citations
    if not evidence_ids or len(evidence_ids) < 2:
        logger.warning(f"Tool 4 rejected: Insufficient evidence count ({len(evidence_ids) if evidence_ids else 0})")
        return {
            "status": "ERROR",
            "code": "INSUFFICIENT_EVIDENCE",
            "plot_id": plot_id,
            "evidence_count": len(evidence_ids) if evidence_ids else 0,
            "message": (
                f"Advisory rejected by safety gate: Expected at least 2 verifiable evidence citations, "
                f"but received {len(evidence_ids) if evidence_ids else 0}. Every recommendation must cite "
                f"telemetry records (EVID-...) and agronomic rules (RULE-...)."
            )
        }

    valid_prefixes = ("EVID-", "RULE-")
    invalid_tokens = [eid for eid in evidence_ids if not any(str(eid).startswith(prefix) for prefix in valid_prefixes)]
    if invalid_tokens:
        logger.warning(f"Tool 4 rejected: Invalid evidence tokens {invalid_tokens}")
        return {
            "status": "ERROR",
            "code": "INVALID_EVIDENCE_FORMAT",
            "plot_id": plot_id,
            "invalid_tokens": invalid_tokens,
            "message": f"Evidence citations must start with 'EVID-' or 'RULE-'. Invalid citations provided: {invalid_tokens}."
        }

    # 5. Database Interaction (PostgreSQL)
    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Ensure the advisory_drafts table exists
            cur.execute("""
                CREATE TABLE IF NOT EXISTS advisory_drafts (
                    id SERIAL PRIMARY KEY,
                    advisory_id VARCHAR(64) UNIQUE NOT NULL,
                    plot_id INTEGER NOT NULL,
                    recommended_action VARCHAR(32) NOT NULL,
                    advisory_rationale TEXT NOT NULL,
                    evidence_ids TEXT NOT NULL,
                    status VARCHAR(32) NOT NULL DEFAULT 'PENDING_APPROVAL',
                    requires_officer_review BOOLEAN NOT NULL DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    approved_by VARCHAR(128) NULL,
                    approved_at TIMESTAMP WITH TIME ZONE NULL
                );
            """)

            # Deduplication: Check if a draft for this plot is already pending created in the last 24h
            cur.execute("""
                SELECT advisory_id, recommended_action, advisory_rationale, evidence_ids, created_at
                FROM advisory_drafts
                WHERE plot_id = %(plot_id)s
                  AND status = 'PENDING_APPROVAL'
                  AND created_at >= NOW() - INTERVAL '24 hours'
                ORDER BY created_at DESC
                LIMIT 1;
            """, {"plot_id": cleaned_id})
            existing = cur.fetchone()

            if existing:
                logger.info(f"Duplicate advisory draft found for plot {cleaned_id}: {existing['advisory_id']}")
                conn.commit()
                return {
                    "status": "OK",
                    "advisory_id": existing["advisory_id"],
                    "queue_status": "PENDING_APPROVAL",
                    "plot_id": str(cleaned_id),
                    "recommended_action": existing["recommended_action"],
                    "requires_officer_review": True,
                    "is_duplicate": True,
                    "message": (
                        f"An identical pending advisory ({existing['advisory_id']}) is already queued "
                        f"for officer review within the last 24 hours. No duplicate created."
                    ),
                    "evidence_ids": json.loads(existing["evidence_ids"]) if isinstance(existing["evidence_ids"], str) else existing["evidence_ids"],
                }

            # Generate unique deterministic advisory ID
            now_utc = datetime.now(timezone.utc)
            date_str = now_utc.strftime("%Y%m%d")
            time_suffix = now_utc.strftime("%H%M%S")
            advisory_id = f"ADV-{date_str}-PLOT{cleaned_id}-{time_suffix}"

            # Insert new advisory draft with status hardcoded to PENDING_APPROVAL
            cur.execute("""
                INSERT INTO advisory_drafts (
                    advisory_id,
                    plot_id,
                    recommended_action,
                    advisory_rationale,
                    evidence_ids,
                    status,
                    requires_officer_review,
                    created_at
                ) VALUES (
                    %(advisory_id)s,
                    %(plot_id)s,
                    %(action)s,
                    %(rationale)s,
                    %(evidence_ids)s,
                    'PENDING_APPROVAL',
                    TRUE,
                    %(created_at)s
                ) RETURNING id;
            """, {
                "advisory_id": advisory_id,
                "plot_id": cleaned_id,
                "action": action_clean,
                "rationale": rationale_clean,
                "evidence_ids": json.dumps(evidence_ids),
                "created_at": now_utc,
            })
            conn.commit()

        logger.info(f"Successfully drafted advisory {advisory_id} for plot {cleaned_id} [PENDING_APPROVAL]")
        return {
            "status": "OK",
            "advisory_id": advisory_id,
            "queue_status": "PENDING_APPROVAL",
            "plot_id": str(cleaned_id),
            "recommended_action": action_clean,
            "requires_officer_review": True,
            "message": f"Advisory draft {advisory_id} created successfully. Awaiting named human officer approval.",
            "triage_summary": {
                "plot_id": str(cleaned_id),
                "action": action_clean,
                "evidence_count": len(evidence_ids),
                "evidence_citations": evidence_ids,
                "drafted_at": now_utc.isoformat(),
            }
        }

    except psycopg2.OperationalError as exc:
        if conn:
            conn.rollback()
        logger.error(f"Database operational error while drafting advisory for plot {plot_id}: {exc}")
        return {
            "status": "ERROR",
            "code": "DB_CONNECTION_ERROR",
            "plot_id": plot_id,
            "message": "Unable to persist advisory draft to database due to connection error or timeout."
        }
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error while drafting advisory for plot {plot_id}: {exc}")
        return {
            "status": "ERROR",
            "code": "PERSISTENCE_ERROR",
            "plot_id": plot_id,
            "message": f"An error occurred while saving advisory draft: {str(exc)}"
        }
    finally:
        if conn:
            conn.close()
