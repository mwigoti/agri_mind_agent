from __future__ import annotations

from typing import Any

from .state import AgriState


def collect_evidence(state: AgriState) -> dict[str, dict[str, Any]]:
    store: dict[str, dict[str, Any]] = {}
    telemetry = state.get("telemetry", {})
    now = telemetry.get("retrieved_at")
    for row in telemetry.get("evidence_records", []):
        evidence_id = row.get("evidence_id")
        if not evidence_id:
            continue
        store[evidence_id] = {
            "evidence_id": evidence_id, "source": row.get("source_sensor", "upstream telemetry"),
            "type": row.get("metric_name", "observation"), "value": row.get("metric_value"),
            "retrieved_at": now or telemetry.get("latest_scene_date"), "valid": telemetry.get("status") == "OK",
            "observation_key": f"{row.get('source_sensor')}:{row.get('metric_name')}:{telemetry.get('latest_scene_date')}",
        }
    calendar = state.get("calendar", {})
    for rule_id in calendar.get("rule_citations", []):
        store[rule_id] = {
            "evidence_id": rule_id, "source": "AgriMind deterministic calendar evaluator", "type": "rule",
            "value": next((v for v in calendar.get("threshold_violations", []) if v.get("rule_id") == rule_id), rule_id),
            "retrieved_at": now, "valid": calendar.get("status") == "OK", "observation_key": f"rule:{rule_id}",
        }
    return store


def validate(state: AgriState) -> tuple[bool, list[str]]:
    errors: list[str] = []
    action = state.get("selected_action")
    if state.get("telemetry", {}).get("status") != "OK":
        errors.append("Current telemetry is missing, stale, or unavailable")
    values = state.get("telemetry", {}).get("telemetry", {})
    vegetation = values.get("vegetation_indices", {})
    climate = values.get("water_and_climate", {})
    if vegetation.get("ndvi_latest") is None and vegetation.get("crop_health_score") is None:
        errors.append("Critical vegetation observation is missing")
    if climate.get("rainfall_anomaly_pct") is None:
        errors.append("Critical rainfall anomaly is missing")
    if action in {"PLANT", "SPRAY"} and climate.get("soil_moisture_vwc") is None:
        errors.append("Soil moisture is required to validate this action")
    if state.get("plot_status", {}).get("status") != "OK":
        errors.append("Plot status could not be verified")
    action = state.get("selected_action")
    if action not in {"PLANT", "SPRAY", "HOLD"}:
        errors.append("Action must be PLANT, SPRAY, or HOLD")
    if action == "SPRAY" and state.get("calendar", {}).get("operational_windows", {}).get("spraying_permitted") is not True:
        errors.append("Deterministic calendar does not confirm spraying is permitted")
    store = state.get("evidence_store", {})
    ids = state.get("evidence_ids", [])
    if len(set(ids)) < 2:
        errors.append("At least two distinct evidence IDs are required")
    if any(eid not in store or not store[eid].get("valid") for eid in ids):
        errors.append("One or more cited evidence IDs are absent or invalid")
    keys = [store[eid].get("observation_key") for eid in ids if eid in store]
    if len({key for key in keys if key}) < 2:
        errors.append("Evidence citations do not provide independent corroboration")
    if action == "PLANT" and not state.get("calendar", {}).get("operational_windows", {}).get("planting_permitted", False):
        errors.append("Planting is not confirmed as permitted by the calendar evaluator")
    if not state.get("rationale", "").strip():
        errors.append("A rationale is required")
    return not errors, errors
