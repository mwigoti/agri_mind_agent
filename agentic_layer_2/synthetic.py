"""Clearly synthetic local fixtures; these values are not field observations."""
from __future__ import annotations

from typing import Any

_ROWS = {
    # Values transcribed from the paper's figure 5/6; intervals are illustrative in the paper.
    "KE-001": {"health": 0.42, "rain": -32.0, "yield": 2.1, "interval_relation": "below_reference", "stage": "Flowering_R1"},
    "KE-002": {"health": 0.78, "rain": -4.0, "yield": 4.6, "interval_relation": "above_reference", "stage": "Maturity_R6"},
    "KE-003": {"health": 0.61, "rain": -18.0, "yield": 3.4, "interval_relation": "crosses_reference", "stage": "Vegetative_V8"},
}


def get_plot(plot_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    row = _ROWS.get(plot_id)
    if not row:
        return {"status": "NOT_FOUND", "plot_id": plot_id}, {"status": "NOT_FOUND"}, {"status": "ERROR"}
    stamp = "2026-10-14T00:00:00+00:00"
    plot = {"status": "OK", "plot_id": plot_id, "synthetic": True, "crop": {"crop_type": "maize"}, "phenology": {"growth_stage": row["stage"]}, "soil_baseline": {}}
    records = [
        {"evidence_id": f"EVID-SYN-HEALTH-{plot_id}", "source_sensor": "SYNTHETIC paper figure 5", "metric_name": "Crop-health score", "metric_value": row["health"]},
        {"evidence_id": f"EVID-SYN-RAIN-{plot_id}", "source_sensor": "SYNTHETIC fixture", "metric_name": "Rainfall anomaly", "metric_value": row["rain"]},
        {"evidence_id": f"EVID-SYN-YIELD-{plot_id}", "source_sensor": "SYNTHETIC paper figure 6", "metric_name": "Predicted yield t/ha", "metric_value": row["yield"]},
    ]
    telemetry = {
        "status": "OK", "synthetic": True, "retrieved_at": stamp, "latest_scene_date": "2026-10-14",
        "telemetry": {"vegetation_indices": {"crop_health_score": row["health"]}, "water_and_climate": {"rainfall_anomaly_pct": row["rain"], "soil_moisture_vwc": None}, "yield_prediction": {"predicted_yield_t_ha": row["yield"], "reference_yield_t_ha": 3.5, "interval_relation": row["interval_relation"], "interval_width_is_illustrative": True}},
        "evidence_records": records,
    }
    calendar = {
        "status": "INSUFFICIENT_EVIDENCE", "synthetic": True, "overall_condition": "NOT_EVALUATED",
        "operational_windows": {"planting_permitted": None, "spraying_permitted": None},
        "rule_citations": [], "threshold_violations": [],
    }
    return plot, telemetry, calendar


def ranking() -> list[dict[str, Any]]:
    """Sort using paper inputs; identifiers do not participate in scoring."""
    ranked = []
    for plot_id in _ROWS:
        _, telemetry, _ = get_plot(plot_id)
        metrics = telemetry["telemetry"]
        water = metrics["water_and_climate"]
        health = metrics["vegetation_indices"]["crop_health_score"]
        # Demo heuristic: larger deficit and poorer health raise attention priority.
        score = max(0.0, -water["rainfall_anomaly_pct"]) + (1.0 - health) * 100
        priority = "HIGH" if score >= 55 else "MEDIUM" if score >= 35 else "LOW"
        prediction = metrics["yield_prediction"]
        # A prediction interval that crosses the reference keeps the item at MEDIUM.
        if prediction["interval_relation"] == "crosses_reference" and priority == "HIGH":
            priority = "MEDIUM"
        ranked.append({"plot_id": plot_id, "priority": priority, "score": round(score, 2), "predicted_yield_t_ha": prediction["predicted_yield_t_ha"], "yield_interval_relation": prediction["interval_relation"], "basis": ["synthetic crop-health score", "synthetic rainfall anomaly", "synthetic yield estimate"]})
    return sorted(ranked, key=lambda item: item["score"], reverse=True)
