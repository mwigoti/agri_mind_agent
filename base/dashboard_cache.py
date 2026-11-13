from __future__ import annotations

from typing import Any, Dict, Optional

from django.core.cache import cache

from .models import AdvisoryReview, Field

FIELD_DASHBOARD_CACHE_PREFIX = "field_dashboard_summary"


def _as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _risk_level_from_score(score: Optional[float]) -> str:
    if score is None:
        return "unknown"
    value = float(score)
    if value > 1:
        value /= 100
    if value >= 0.8:
        return "low"
    if value >= 0.55:
        return "moderate"
    return "high"


def _metric_value(metric: Any, name: str) -> Any:
    if metric is None:
        return None
    metadata = metric.metadata or {}
    provided_fields = metadata.get("provided_fields")
    if provided_fields is not None and name not in provided_fields:
        return None
    value = getattr(metric, name, None)
    if name == "health_score" and value == 0 and not metadata.get("health_score_provided", False):
        return None
    if name == "yield_estimate_t_ha" and value == 0 and not metadata.get("yield_estimate_provided", False):
        return None
    return value


def _derive_metric_payload(field: Field, latest_metric: Any, latest_analysis: Any) -> Dict[str, Any]:
    bundle = latest_analysis.full_bundle or {} if latest_analysis else {}
    sat = bundle.get("satellite", {})
    climate = bundle.get("climate", {})
    soil = bundle.get("soil", {})
    scientific_indices = bundle.get("scientific_indices", {}) or {}
    scientific_yield = bundle.get("scientific_yield", {}) or {}

    # Only use persisted NDVI observations or a real Sentinel-2 scene series.
    # Older bundles used hard-coded fallback indices and did not mark their source.
    ndvi_value = _metric_value(latest_metric, "ndvi")
    if ndvi_value is None and sat.get("data_source") == "sentinel2":
        ndvi_value = sat.get("ndvi_grain_filling")
        if ndvi_value is None:
            ndvi_value = sat.get("ndvi_vegetative")
    rainfall_value = (
        _metric_value(latest_metric, "rainfall_mm")
        if _metric_value(latest_metric, "rainfall_mm") is not None
        else climate.get("total_season_rainfall_mm")
        or climate.get("recent_rainfall_mm")
    )
    soil_value = (
        _metric_value(latest_metric, "soil_moisture_pct")
        if _metric_value(latest_metric, "soil_moisture_pct") is not None
        else soil.get("soil_moisture_pct")
        or soil.get("volumetric_water_content")
    )
    analysis_health = scientific_indices.get("chi")
    if analysis_health is None:
        analysis_health = bundle.get("health_score")
    if analysis_health is None:
        analysis_health = sat.get("health_score")
    metric_health = _metric_value(latest_metric, "health_score")
    if latest_metric and metric_health == 0 and not (latest_metric.metadata or {}).get("health_score_provided", False):
        metric_health = None
    health_value = metric_health if metric_health is not None else analysis_health
    if health_value is None:
        health_coverage = None
        health_components = []
    elif latest_metric and metric_health is not None:
        metric_metadata = latest_metric.metadata or {}
        health_coverage = metric_metadata.get("health_score_coverage_pct")
        health_components = metric_metadata.get("health_score_components", [])
        if health_coverage is None:
            health_coverage = scientific_indices.get("chi_coverage_pct", 100)
        if not health_components:
            health_components = scientific_indices.get("chi_components_used", [])
    else:
        health_coverage = scientific_indices.get("chi_coverage_pct", 100)
        health_components = scientific_indices.get("chi_components_used", [])
    ndvi_numeric = _as_float(ndvi_value)
    if health_value is None and ndvi_numeric is not None:
        # VCI-style fallback from an actual saved Sentinel-2 NDVI observation.
        ndvi_score = max(0.0, min(1.0, (ndvi_numeric - 0.25) / (0.88 - 0.25)))
        health_value = round(ndvi_score * 100, 2)
        health_coverage = 30.0
        health_components = ["vegetation_index"]
    yield_value = (
        _metric_value(latest_metric, "yield_estimate_t_ha")
        if _metric_value(latest_metric, "yield_estimate_t_ha") is not None
        else bundle.get("predicted_yield_t_ha")
        or bundle.get("ml_yield_t_ha")
        or scientific_yield.get("predicted_yield_t_ha")
    )

    metric_payload = {
        "id": latest_metric.id if latest_metric else None,
        "captured_at": latest_metric.captured_at.isoformat() if latest_metric and latest_metric.captured_at else None,
        "ndvi": _as_float(ndvi_value),
        "evi": _as_float(latest_metric.evi if latest_metric else sat.get("evi_grain_filling") or sat.get("evi_latest") or sat.get("evi")),
        "savi": _as_float(latest_metric.savi if latest_metric else sat.get("savi")),
        "ndmi": _as_float(latest_metric.ndmi if latest_metric else sat.get("ndmi")),
        "rainfall_mm": _as_float(rainfall_value),
        "temperature_c": _as_float(latest_metric.temperature_c if latest_metric else climate.get("recent_tmax_c")),
        "humidity_pct": _as_float(latest_metric.humidity_pct if latest_metric else climate.get("relative_humidity_pct")),
        "soil_moisture_pct": _as_float(soil_value),
        "health_score": _as_float(health_value),
        "overall_health_score": _as_float(health_value),
        "health_score_coverage_pct": _as_float(health_coverage),
        "health_score_components": health_components,
        "yield_estimate_t_ha": _as_float(yield_value),
        "nutrient_status": latest_metric.nutrient_status if latest_metric else "unknown",
        "pest_pressure": _as_float(latest_metric.pest_pressure if latest_metric else None),
        "risk_level": (bundle.get("risk_level") or _risk_level_from_score(_as_float(health_value))).upper(),
    }
    return metric_payload


def build_field_dashboard_summary(field: Field) -> Dict[str, Any]:
    latest_metric = field.metrics.order_by("-captured_at").first() if hasattr(field, "metrics") else None
    analysis_qs = getattr(field, "analysis_results", None)
    latest_analysis = (
        analysis_qs.filter(pipeline_status="done")
        .select_related("activity__crop")
        .order_by("-updated_at")
        .first()
        if analysis_qs is not None
        else None
    )
    latest_attempt = analysis_qs.order_by("-updated_at").first() if analysis_qs is not None else None

    pending_reviews = AdvisoryReview.objects.filter(field=field, status="pending").count()
    recent_reviews = list(
        AdvisoryReview.objects.filter(field=field)
        .order_by("-created_at")[:5]
        .values("id", "recommended_action", "status", "reviewer_comment", "created_at")
    )

    payload = {
        "field_id": field.id,
        "field_name": field.name,
        "area_ha": _as_float(field.area),
        "latest_metric": None,
        "pending_reviews": pending_reviews,
        "recent_reviews": recent_reviews,
        "is_attention_required": pending_reviews > 0,
        "latest_analysis_status": latest_attempt.pipeline_status if latest_attempt else None,
        "latest_analysis_error": latest_attempt.error_message if latest_attempt and latest_attempt.pipeline_status == "error" else None,
        "has_saved_analysis": latest_analysis is not None,
        "risk_level": "unknown",
        "yield_estimate_t_ha": None,
        "vegetation_trend": [],
        "vegetation_status": "No crop analysis has been saved for this field.",
    }

    metric_payload = _derive_metric_payload(field, latest_metric, latest_analysis)
    payload["latest_metric"] = metric_payload
    payload["risk_level"] = metric_payload.get("risk_level")
    payload["yield_estimate_t_ha"] = metric_payload.get("yield_estimate_t_ha")
    if payload["yield_estimate_t_ha"] is not None and payload["area_ha"] is not None:
        payload["estimated_yield_t"] = round(payload["yield_estimate_t_ha"] * payload["area_ha"], 2)
    else:
        payload["estimated_yield_t"] = None
    observations = list(
        field.metrics.filter(ndvi__isnull=False)
        .order_by("-captured_at")[:12]
        .values("captured_at", "ndvi")
    )
    payload["vegetation_trend"] = [
        {"date": point["captured_at"].isoformat(), "ndvi": _as_float(point["ndvi"])}
        for point in reversed(observations)
    ]
    bundle = latest_analysis.full_bundle or {} if latest_analysis else {}
    satellite = bundle.get("satellite", {}) or {}
    if not payload["vegetation_trend"] and satellite.get("data_source") == "sentinel2":
        ndvi = satellite.get("ndvi_grain_filling")
        if ndvi is None:
            ndvi = satellite.get("ndvi_vegetative")
        if ndvi is not None and satellite.get("latest_scene_date"):
            payload["vegetation_trend"] = [{"date": satellite["latest_scene_date"], "ndvi": _as_float(ndvi)}]
    if payload["vegetation_trend"]:
        payload["vegetation_status"] = f"{len(payload['vegetation_trend'])} saved Sentinel-2 observation(s)"
    elif latest_attempt is not None:
        if latest_attempt.pipeline_status in ("queued", "running"):
            payload["vegetation_status"] = "Crop analysis is still running."
        elif latest_attempt.pipeline_status == "error":
            payload["vegetation_status"] = latest_attempt.error_message or "The latest crop analysis failed."
        else:
            status = satellite.get("data_status")
            messages = {
                "gee_unavailable": "Earth Engine did not initialize. Check server logs, credentials, and AGRIVISION_GEE_PROJECT.",
                "no_scenes": "Sentinel-2 returned no scenes for the crop stage date windows.",
                "query_error": "Sentinel-2 query failed. Check the Django server logs for the GEE error.",
                "scene_series_unavailable": "A satellite composite was found, but dated scene NDVI could not be extracted.",
            }
            payload["vegetation_status"] = messages.get(
                status,
                "This saved analysis has no dated NDVI observations. Run a new crop analysis to collect them.",
            )
    return payload


def warmup_field_dashboard_summary(field_id: int) -> Dict[str, Any]:
    field = Field.objects.select_related("owner").get(pk=field_id)
    payload = build_field_dashboard_summary(field)
    cache.set(f"{FIELD_DASHBOARD_CACHE_PREFIX}:{field_id}", payload, 300)
    return payload


def warmup_all_field_summaries():
    summaries = {}
    for field in Field.objects.all():
        summaries[field.id] = warmup_field_dashboard_summary(field.id)
    return summaries
