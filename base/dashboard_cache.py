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
    if value >= 0.8:
        return "low"
    if value >= 0.55:
        return "moderate"
    return "high"


def _derive_metric_payload(field: Field, latest_metric: Any, latest_analysis: Any) -> Dict[str, Any]:
    bundle = latest_analysis.full_bundle or {} if latest_analysis else {}
    sat = bundle.get("satellite", {})
    climate = bundle.get("climate", {})
    soil = bundle.get("soil", {})
    scientific_yield = bundle.get("scientific_yield", {}) or {}

    ndvi_value = (
        latest_metric.ndvi
        if latest_metric and latest_metric.ndvi is not None
        else sat.get("ndvi_grain_filling")
        or sat.get("ndvi_latest")
        or sat.get("ndvi")
    )
    rainfall_value = (
        latest_metric.rainfall_mm
        if latest_metric and latest_metric.rainfall_mm is not None
        else climate.get("total_season_rainfall_mm")
        or climate.get("recent_rainfall_mm")
    )
    soil_value = (
        latest_metric.soil_moisture_pct
        if latest_metric and latest_metric.soil_moisture_pct is not None
        else soil.get("soil_moisture_pct")
        or soil.get("volumetric_water_content")
    )
    health_value = (
        latest_metric.health_score
        if latest_metric and latest_metric.health_score is not None
        else bundle.get("health_score")
        or sat.get("health_score")
    )
    yield_value = (
        latest_metric.yield_estimate_t_ha
        if latest_metric and latest_metric.yield_estimate_t_ha is not None
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
        analysis_qs.select_related("activity__crop").order_by("-updated_at").first()
        if analysis_qs is not None
        else None
    )

    pending_reviews = AdvisoryReview.objects.filter(field=field, status="pending").count()
    recent_reviews = list(
        AdvisoryReview.objects.filter(field=field)
        .order_by("-created_at")[:5]
        .values("id", "recommended_action", "status", "reviewer_comment", "created_at")
    )

    payload = {
        "field_id": field.id,
        "field_name": field.name,
        "latest_metric": None,
        "pending_reviews": pending_reviews,
        "recent_reviews": recent_reviews,
        "is_attention_required": pending_reviews > 0,
        "risk_level": "unknown",
        "yield_estimate_t_ha": None,
    }

    metric_payload = _derive_metric_payload(field, latest_metric, latest_analysis)
    payload["latest_metric"] = metric_payload
    payload["risk_level"] = metric_payload.get("risk_level")
    payload["yield_estimate_t_ha"] = metric_payload.get("yield_estimate_t_ha")

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
