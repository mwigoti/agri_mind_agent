"""
agrivision/gee_pipeline.py

Pipeline 2 — Satellite Data Collection
========================================
Triggered when the frontend calls POST /api/analyze-crop/.

Receives:  field_id  (from farms.Field model)
           activity_id  (from FieldActivity — the planting record)

Does:
  1. Load field geometry + centroid from the DB (Field.geometry PolygonField)
  2. Load planting date + crop type from FieldActivity
  3. Pull cloud-masked Sentinel-2 (NDVI / NDRE / EVI / SAVI / GNDVI)
     for every 10-day window from planting → today
  4. Pull CHIRPS rainfall (cumulative per 10-day window)
  5. Pull ERA5 daily max/min temp → GDD accumulation
  6. Pull SoilGrids 250 m (SOC, Clay, pH, BulkDensity, Nitrogen) — cached
  7. Return a structured dict ready for Pipeline 3 (ML yield + health model)
     and store raw results in the DB via AnalysisResult model.

Integration notes for later pipelines
--------------------------------------
  Pipeline 3 (ML):  call  run_pipeline_2(field_id, activity_id)  and receive
                    the returned feature_bundle dict.  All GEE data is already
                    Z-score normalised per county historical mean/std where
                    relevant (rainfall anomaly).  Raw values are also kept.

  Pipeline 4 (LLM advisory):  feature_bundle["stress_flags"] is a plain-text
                    list suitable for prompt injection.

  Field-level yield map (Option A):  pixel_stacks in feature_bundle contain
                    the per-pixel arrays needed for spatial transfer.
"""

import logging
import sys
from datetime import datetime, timedelta, date
from typing import Any

import ee
from django.conf import settings

# ── Terminal logger — prints everything to stdout in real time ──
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
    force=True,
)
logger = logging.getLogger("agrivision.pipeline")

# ─────────────────────────────────────────────────────────────
#  GEE INITIALISATION  (once per process)
# ─────────────────────────────────────────────────────────────
def _init_gee():
    """
    Authenticate via service-account key stored in Django settings.
    Falls back to application-default credentials for local dev.
    Add to settings.py:
        GEE_SERVICE_ACCOUNT = "agrivision@project.iam.gserviceaccount.com"
        GEE_KEY_FILE        = "/run/secrets/gee-sa-key.json"
        GEE_PROJECT         = "your-gcp-project-id"
    """
    try:
        sa_email = getattr(settings, "GEE_SERVICE_ACCOUNT", None)
        key_file  = getattr(settings, "GEE_KEY_FILE", None)
        project   = getattr(settings, "GEE_PROJECT", "ee-henrymwoha02")

        if sa_email and key_file:
            creds = ee.ServiceAccountCredentials(email=sa_email, key_file=key_file)
            ee.Initialize(credentials=creds, project=project)
        else:
            # Local dev — run `earthengine authenticate` once
            ee.Initialize(project=project)

        logger.info("GEE initialised ✓")
    except Exception as exc:
        logger.error("GEE init failed: %s", exc)
        raise


# Call once at import time so it is ready for any request
_init_gee()


# ─────────────────────────────────────────────────────────────
#  CROP CONSTANTS  (extend for any crop in the Crop model)
# ─────────────────────────────────────────────────────────────
CROP_CONFIG: dict[str, dict] = {
    "maize": {
        "t_base": 10.0,           # GDD base °C
        "t_stress": 35.0,         # Heat stress threshold °C
        "typical_season_days": 120,
    },
    "wheat": {
        "t_base": 4.4,
        "t_stress": 30.0,
        "typical_season_days": 150,
    },
    "rice": {
        "t_base": 10.0,
        "t_stress": 38.0,
        "typical_season_days": 130,
    },
    "soybean": {
        "t_base": 10.0,
        "t_stress": 35.0,
        "typical_season_days": 110,
    },
    "potato": {
        "t_base": 7.0,
        "t_stress": 30.0,
        "typical_season_days": 100,
    },
    "tomato": {
        "t_base": 10.0,
        "t_stress": 35.0,
        "typical_season_days": 90,
    },
    # Default fallback
    "_default": {
        "t_base": 10.0,
        "t_stress": 35.0,
        "typical_season_days": 120,
    },
}

# Sentinel-2 SCL values treated as "clear" (no cloud / shadow)
_S2_CLEAR_SCL = [4, 5, 6, 7]   # vegetation, bare soil, water, unclassified
_MAX_CLOUD_PCT = 30             # reject scenes with >30 % cloud over AOI
_S2_SCALE_M   = 10             # Sentinel-2 native pixel scale (metres)
_ERA5_SCALE_M = 11132           # ERA5-Land ~0.1° in metres
_CHIRPS_SCALE_M = 5566          # CHIRPS 0.05° in metres
_SOIL_SCALE_M   = 250               # SoilGrids
_IMERG_SCALE_M  = 1000             # IMERG ~10 km


# ─────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────
def run_pipeline_2(field_id: int, activity_id: int) -> dict[str, Any]:

    logger.info("=" * 60)
    logger.info("PIPELINE 2 START — field_id=%s activity_id=%s", field_id, activity_id)
    logger.info("=" * 60)

    from .models import Field, FieldActivity

    field    = Field.objects.get(pk=field_id)
    activity = FieldActivity.objects.select_related("crop").get(pk=activity_id)

    crop_name   = activity.crop.name.lower() if activity.crop else "maize"
    planting_dt = activity.date.date() if hasattr(activity.date, "date") else activity.date
    today       = date.today()
    S2_END      = today - timedelta(days=5)
    ERA5_END    = today - timedelta(days=7)
    cfg         = CROP_CONFIG.get(crop_name, CROP_CONFIG["_default"])

    logger.info("Field      : %s", field.name)
    logger.info("Crop       : %s", crop_name)
    logger.info("Planted    : %s", planting_dt)
    logger.info("S2 window  : %s → %s", planting_dt + timedelta(days=7), S2_END)
    logger.info("ERA5 window: %s → %s", planting_dt, ERA5_END)
    logger.info("Centroid   : lat=%.4f lon=%.4f", field.geometry.centroid.y, field.geometry.centroid.x)
    logger.info("Field area : %.2f ha", field.area)

    monitoring_start = planting_dt + timedelta(days=7)
    if monitoring_start > today:
        logger.warning("Too early — planting was %s days ago, need at least 7", (today - planting_dt).days)
        return _early_return(field, activity, planting_dt, crop_name)

    # Geometry
    import json
    aoi_full    = ee.Geometry(json.loads(field.geometry.geojson))
    aoi         = aoi_full.buffer(-10)
    centroid    = field.geometry.centroid
    centroid_pt = ee.Geometry.Point([centroid.x, centroid.y])

    # ── Sentinel-2 ───────────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 1: Sentinel-2 extraction...")
    try:
        sentinel_result = _extract_sentinel2(
            aoi=aoi,
            start=monitoring_start,
            end=S2_END,
            field_area_ha=field.area,
        )
        logger.info("  ✓ Scenes found   : %s", sentinel_result.get("scene_count"))
        logger.info("  ✓ NDVI latest    : %s", sentinel_result.get("ndvi_latest"))
        logger.info("  ✓ NDRE latest    : %s", sentinel_result.get("ndre_latest"))
        logger.info("  ✓ EVI latest     : %s", sentinel_result.get("evi_latest"))
        logger.info("  ✓ NDVI AUC       : %s", sentinel_result.get("ndvi_auc"))
        logger.info("  ✓ NDRE peak      : %s", sentinel_result.get("ndre_peak"))
        logger.info("  ✓ Latest scene   : %s", sentinel_result.get("latest_date"))
    except Exception as exc:
        logger.error("  ✗ Sentinel-2 FAILED: %s", exc, exc_info=True)
        sentinel_result = {"scene_count": 0, "scenes": [], "ndvi_latest": None,
                           "ndre_latest": None, "evi_latest": None,
                           "ndvi_auc": None, "ndre_peak": None}

    # ── Sentinel-1 SAR ───────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 1b: Sentinel-1 SAR extraction...")
    try:
        sar_result = _extract_sentinel1(
            aoi=aoi,
            start=monitoring_start,
            end=S2_END,
        )
        logger.info("  ✓ SAR scenes     : %s", sar_result.get("scene_count"))
        logger.info("  ✓ VH latest      : %s", sar_result.get("vh_latest"))
    except Exception as exc:
        logger.error("  ✗ Sentinel-1 SAR FAILED: %s", exc, exc_info=True)
        sar_result = {"scene_count": 0, "scenes": [], "vv_latest": None,
                      "vh_latest": None, "ratio_latest": None, "vh_auc": None}

    # ── CHIRPS + IMERG ───────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 2: Rainfall extraction (CHIRPS + IMERG)...")
    try:
        chirps_result = _extract_chirps(
            point=centroid_pt,
            start=monitoring_start,
            end=today,
        )
        logger.info("  ✓ Total rainfall : %.1f mm", chirps_result.get("total_mm") or 0)
        logger.info("  ✓ CHIRPS portion : %.1f mm", chirps_result.get("chirps_mm") or 0)
        logger.info("  ✓ IMERG portion  : %.1f mm", chirps_result.get("imerg_mm") or 0)
        logger.info("  ✓ Windows        : %s", chirps_result.get("window_count"))
        logger.info("  ✓ Source         : %s", chirps_result.get("source_note"))
    except Exception as exc:
        logger.error("  ✗ Rainfall FAILED: %s", exc, exc_info=True)
        chirps_result = {"total_mm": 0, "chirps_mm": 0, "imerg_mm": 0, "windows": []}

    # ── ERA5 ─────────────────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 3: ERA5 temperature / GDD extraction...")
    try:
        era5_result = _extract_era5(
            point=centroid_pt,
            start=planting_dt,
            end=ERA5_END,
            t_base=cfg["t_base"],
            t_stress=cfg["t_stress"],
        )
        logger.info("  ✓ Cumulative GDD : %.1f °C·d", era5_result.get("cumulative_gdd") or 0)
        logger.info("  ✓ Heat stress    : %.1f%% of days", (era5_result.get("heat_stress_frac") or 0) * 100)
        logger.info("  ✓ Stress days    : %s / %s", era5_result.get("heat_stress_days"), era5_result.get("total_days"))
        logger.info("  ✓ Recent Tmax    : %.1f °C", era5_result.get("recent_tmax_c") or 0)
        logger.info("  ✓ Recent Tmin    : %.1f °C", era5_result.get("recent_tmin_c") or 0)
    except Exception as exc:
        logger.error("  ✗ ERA5 FAILED: %s", exc, exc_info=True)
        era5_result = {"cumulative_gdd": 0, "heat_stress_frac": 0,
                       "heat_stress_days": 0, "total_days": 0}

    # ── SoilGrids ────────────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 4: Soil data (ISQAper DB cache)...")
    try:
        soil_result = _extract_soilgrids(centroid_pt, aoi, field_id=field_id)
        logger.info("  ✓ SOC            : %s g/kg",  soil_result.get("soc_gkg"))
        logger.info("  ✓ Clay           : %s %%",    soil_result.get("clay_pct"))
        logger.info("  ✓ pH             : %s",       soil_result.get("soil_ph"))
        logger.info("  ✓ Nitrogen       : %s g/kg",  soil_result.get("total_nitrogen"))
        logger.info("  ✓ Phosphorus     : %s mg/kg", soil_result.get("phosphorus_olsen_mgkg"))
        logger.info("  ✓ Soil type      : %s",       soil_result.get("soil_type"))
        logger.info("  ✓ Erosion class  : %s",       soil_result.get("erosion_class"))
    except Exception as exc:
        logger.error("  ✗ Soil FAILED: %s", exc, exc_info=True)
        soil_result = {}

    # ── Stress flags ─────────────────────────────────────────
    logger.info("-" * 40)
    logger.info("STEP 5: Building stress flags...")
    stress_flags = _build_stress_flags(
        sentinel=sentinel_result,
        era5=era5_result,
        chirps=chirps_result,
        soil=soil_result,
        cfg=cfg,
    )
    if stress_flags:
        for flag in stress_flags:
            logger.warning("  ⚠ %s", flag)
    else:
        logger.info("  ✓ No stress flags detected")

    # ── Assemble ─────────────────────────────────────────────
    feature_bundle = {
        "meta": {
            "field_id":       field_id,
            "field_name":     field.name,
            "activity_id":    activity_id,
            "crop_type":      crop_name,
            "planting_date":  planting_dt.isoformat(),
            "days_monitored": (today - monitoring_start).days,
            "centroid_lat":   centroid.y,
            "centroid_lon":   centroid.x,
            "field_area_ha":  field.area,
        },
        "sentinel":     sentinel_result,
        "chirps":       chirps_result,
        "era5":         era5_result,
        "soil":         soil_result,
        "stress_flags": stress_flags,
        "ready_for_ml": sentinel_result.get("scene_count", 0) >= 2,
    }

    # ── S2 + SAR fusion ──────────────────────────────────────
    fused_result = _fuse_s2_sar(sentinel_result, sar_result)
    feature_bundle["fused"] = fused_result
    logger.info("  ✓ Fused timeline : %s observations (%s S2 + %s SAR gap-fills)",
                len(fused_result["timeline"]),
                fused_result["s2_scene_count"],
                fused_result["gap_fill_count"])

    _save_to_db(field_id, activity_id, feature_bundle)

    logger.info("=" * 60)
    logger.info("PIPELINE 2 COMPLETE")
    logger.info("  Scenes     : %s", sentinel_result.get("scene_count"))
    logger.info("  Rainfall   : %.1f mm", chirps_result.get("total_mm") or 0)
    logger.info("  GDD        : %.1f °C·d", era5_result.get("cumulative_gdd") or 0)
    logger.info("  Stress flags: %s", len(stress_flags))
    logger.info("  Ready for ML: %s", feature_bundle["ready_for_ml"])
    logger.info("=" * 60)

    return feature_bundle
 
# ─────────────────────────────────────────────────────────────
#  SENTINEL-2 EXTRACTION
# ─────────────────────────────────────────────────────────────
def _extract_sentinel2(
    aoi: ee.Geometry,
    start: date,
    end: date,
    field_area_ha: float,
) -> dict:
    """
    Pull all cloud-free Sentinel-2 scenes over the AOI between start→end.
    Computes NDVI, NDRE, EVI, SAVI, GNDVI per scene.
    Returns per-scene list + season-level summary statistics.
    """
    start_str = start.strftime("%Y-%m-%d")
    end_str   = (end + timedelta(days=1)).strftime("%Y-%m-%d")  # exclusive

    # ── Cloud masking ────────────────────────────────────────
    def mask_clouds(img):
        scl  = img.select("SCL")
        mask = scl.remap(_S2_CLEAR_SCL, [1] * len(_S2_CLEAR_SCL), 0)
        return img.updateMask(mask)

    # ── Band maths ───────────────────────────────────────────
    def add_indices(img):
        # B4=Red B5=RedEdge B8=NIR B2=Blue B3=Green
        ndvi  = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndre  = img.normalizedDifference(["B8", "B5"]).rename("NDRE")
        gndvi = img.normalizedDifference(["B8", "B3"]).rename("GNDVI")

        evi = img.expression(
            "2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)",
            {"NIR": img.select("B8"), "RED": img.select("B4"), "BLUE": img.select("B2")},
        ).rename("EVI")

        # SAVI — L=0.5, good for low-cover early season
        savi = img.expression(
            "1.5 * (NIR - RED) / (NIR + RED + 0.5)",
            {"NIR": img.select("B8"), "RED": img.select("B4")},
        ).rename("SAVI")

        return img.addBands([ndvi, ndre, evi, savi, gndvi])

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterDate(start_str, end_str)
        .filterBounds(aoi)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", _MAX_CLOUD_PCT))
        .map(mask_clouds)
        .map(add_indices)
    )

    scene_count = collection.size().getInfo()

    if scene_count == 0:
        logger.warning("No clear Sentinel-2 scenes found for field %s", aoi)
        return {
            "scene_count":  0,
            "scenes":       [],
            "ndvi_latest":  None,
            "ndre_latest":  None,
            "evi_latest":   None,
            "ndvi_auc":     None,
            "ndre_peak":    None,
        }

    # ── Per-scene reduction ──────────────────────────────────
    def reduce_scene(img):
        stats = img.select(["NDVI", "NDRE", "EVI", "SAVI", "GNDVI"]).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=_S2_SCALE_M,
            maxPixels=1e9,
            bestEffort=True,         # avoids memory errors on large fields
        )
        return ee.Feature(None, stats.set("date", img.date().format("YYYY-MM-dd")))

    scenes_fc  = collection.map(reduce_scene)
    scenes_raw = scenes_fc.getInfo()["features"]

    # Build clean Python list, skipping scenes where all indices are null
    scenes = []
    for feat in scenes_raw:
        props = feat["properties"]
        if props.get("NDVI") is None:
            continue
        scenes.append({
            "date":  props["date"],
            "ndvi":  round(props.get("NDVI")  or 0, 4),
            "ndre":  round(props.get("NDRE")  or 0, 4),
            "evi":   round(props.get("EVI")   or 0, 4),
            "savi":  round(props.get("SAVI")  or 0, 4),
            "gndvi": round(props.get("GNDVI") or 0, 4),
        })

    if not scenes:
        return {"scene_count": scene_count, "scenes": [], "ndvi_latest": None,
                "ndre_latest": None, "evi_latest": None, "ndvi_auc": None, "ndre_peak": None}

    # Sort chronologically
    scenes.sort(key=lambda s: s["date"])

    latest = scenes[-1]

    # NDVI AUC — trapezoidal approximation over the series
    ndvi_auc = _trapezoid_auc([s["ndvi"] for s in scenes])
    ndre_peak = max(s["ndre"] for s in scenes)

    # ── Pixel stack for field-level Option A (later pipeline) ─
    # We store the latest cloud-free composite as a GEE asset reference.
    # The actual pixel export is deferred to Pipeline 3 on demand.
    latest_composite_ref = {
        "collection_id": "COPERNICUS/S2_SR_HARMONIZED",
        "start": scenes[-1]["date"],
        "end":   (datetime.strptime(scenes[-1]["date"], "%Y-%m-%d") + timedelta(days=10)).strftime("%Y-%m-%d"),
        "aoi_geojson": aoi.getInfo(),
    }

    return {
        "scene_count":     len(scenes),
        "scenes":          scenes,            # [{date, ndvi, ndre, evi, savi, gndvi}, ...]
        "ndvi_latest":     latest["ndvi"],
        "ndre_latest":     latest["ndre"],
        "evi_latest":      latest["evi"],
        "savi_latest":     latest["savi"],
        "gndvi_latest":    latest["gndvi"],
        "ndvi_auc":        round(ndvi_auc, 3),
        "ndre_peak":       round(ndre_peak, 4),
        "latest_date":     latest["date"],
        "latest_composite_ref": latest_composite_ref,  # ← Pipeline 3 hook
    }
def _extract_sentinel1(
    aoi: ee.Geometry,
    start: date,
    end: date,
) -> dict:
    """
    Sentinel-1 SAR backscatter extraction.
    VV  — sensitive to soil moisture and surface roughness
    VH  — sensitive to vegetation volume / canopy structure
    VH/VV ratio — proxy for canopy density (analogous to NDVI)
    Works through clouds — fills S2 gaps.
    """
    start_str = start.strftime("%Y-%m-%d")
    end_str   = (end + timedelta(days=1)).strftime("%Y-%m-%d")

    s1 = (
        ee.ImageCollection("COPERNICUS/S1_GRD")
        .filterDate(start_str, end_str)
        .filterBounds(aoi)
        .filter(ee.Filter.eq("instrumentMode", "IW"))          # Interferometric Wide swath
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
        .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
        .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))  # more consistent over Kenya
        .select(["VV", "VH"])
    )

    scene_count = s1.size().getInfo()

    if scene_count == 0:
        logger.warning("No Sentinel-1 scenes found")
        return {
            "scene_count": 0,
            "scenes":      [],
            "vv_latest":   None,
            "vh_latest":   None,
            "ratio_latest":None,
            "vh_auc":      None,
        }

    def add_ratio(img):
        # VH/VV ratio in dB space = VH - VV
        ratio = img.select("VH").subtract(img.select("VV")).rename("VH_VV_ratio")
        return img.addBands(ratio)

    s1 = s1.map(add_ratio)

    def reduce_scene(img):
        stats = img.select(["VV", "VH", "VH_VV_ratio"]).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=10,
            maxPixels=1e9,
            bestEffort=True,
        )
        return ee.Feature(None, stats.set("date", img.date().format("YYYY-MM-dd")))

    scenes_raw = s1.map(reduce_scene).getInfo()["features"]

    scenes = []
    for feat in scenes_raw:
        p = feat["properties"]
        if p.get("VV") is None:
            continue
        scenes.append({
            "date":      p["date"],
            "vv":        round(p.get("VV")           or 0, 4),
            "vh":        round(p.get("VH")           or 0, 4),
            "vh_vv":     round(p.get("VH_VV_ratio")  or 0, 4),
        })

    scenes.sort(key=lambda s: s["date"])

    if not scenes:
        return {"scene_count": 0, "scenes": [], "vv_latest": None,
                "vh_latest": None, "ratio_latest": None, "vh_auc": None}

    latest  = scenes[-1]
    vh_auc  = _trapezoid_auc([s["vh"] for s in scenes])

    return {
        "scene_count":  len(scenes),
        "scenes":       scenes,
        "vv_latest":    latest["vv"],
        "vh_latest":    latest["vh"],
        "ratio_latest": latest["vh_vv"],
        "vh_auc":       round(vh_auc, 3),
        "latest_date":  latest["date"],
    }
def _fuse_s2_sar(sentinel: dict, sar: dict) -> dict:
    """
    Fuse Sentinel-2 optical and Sentinel-1 SAR into a unified
    vegetation timeline. Where S2 has cloud gaps, SAR fills in.

    SAR VH is converted to a pseudo-NDVI using a linear scaling
    calibrated for East Africa maize:
        pseudo_ndvi = (VH + 25) / 20
    (VH typically ranges -25 to -5 dB for bare soil to dense crop)
    """
    s2_scenes  = {s["date"]: s for s in sentinel.get("scenes", [])}
    sar_scenes = {s["date"]: s for s in sar.get("scenes", [])}

    all_dates = sorted(set(list(s2_scenes.keys()) + list(sar_scenes.keys())))

    fused = []
    for d in all_dates:
        if d in s2_scenes:
            # S2 available — use real NDVI
            s = s2_scenes[d]
            fused.append({
                "date":         d,
                "ndvi":         s["ndvi"],
                "ndre":         s["ndre"],
                "source":       "S2",
                "pseudo_ndvi":  s["ndvi"],
            })
        elif d in sar_scenes:
            # S2 gap — derive pseudo-NDVI from SAR VH
            vh = sar_scenes[d]["vh"]
            pseudo_ndvi = round(min(max((vh + 25) / 20, 0), 1), 4)
            fused.append({
                "date":        d,
                "ndvi":        pseudo_ndvi,
                "ndre":        None,          # SAR cannot estimate NDRE
                "source":      "SAR",
                "pseudo_ndvi": pseudo_ndvi,
                "vh_db":       vh,
            })

    fused_ndvi_auc = _trapezoid_auc([f["ndvi"] for f in fused])

    return {
        "timeline":        fused,
        "fused_ndvi_auc":  round(fused_ndvi_auc, 3),
        "s2_scene_count":  len(s2_scenes),
        "sar_scene_count": len(sar_scenes),
        "gap_fill_count":  len([f for f in fused if f["source"] == "SAR"]),
    }
# ─────────────────────────────────────────────────────────────
#  CHIRPS + IMERG TIERED RAINFALL EXTRACTION
# ─────────────────────────────────────────────────────────────
def _extract_chirps(
    point: ee.Geometry,
    start: date,
    end: date,
) -> dict:
    """
    Tiered rainfall extraction:
      - CHIRPS Daily  : planting → (today - 21 days)  [accurate, calibrated]
      - IMERG V07     : (today - 21 days) → today      [1-day lag, fills gap]
    Both are free NASA/UCSB products on GEE.
    """
    CHIRPS_LAG_DAYS = 21
    chirps_end   = end - timedelta(days=CHIRPS_LAG_DAYS)
    imerg_start  = chirps_end + timedelta(days=1)

    chirps_mm    = 0.0
    imerg_mm     = 0.0
    chirps_windows = []
    imerg_windows  = []

    # ── CHIRPS portion (start → today-21d) ───────────────────
    if chirps_end >= start:
        chirps_mm, chirps_windows = _sum_rainfall_windows(
            collection=ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY")
                         .filterDate(
                             start.strftime("%Y-%m-%d"),
                             (chirps_end + timedelta(days=1)).strftime("%Y-%m-%d"),
                         )
                         .select("precipitation"),
            point=point,
            scale=_CHIRPS_SCALE_M,
            start=start,
            end=chirps_end,
            band="precipitation",
            unit_multiplier=1.0,   # already mm/day
        )

    # ── IMERG portion (today-21d → today) ────────────────────
    if imerg_start <= end:
        # IMERG is mm/hr in 30-min intervals — sum gives mm/hr totals
        # multiply by 0.5 to convert each 30-min observation → mm
        imerg_mm, imerg_windows = _sum_rainfall_windows(
            collection=ee.ImageCollection("NASA/GPM_L3/IMERG_V07")
                         .filterDate(
                             imerg_start.strftime("%Y-%m-%d"),
                             (end + timedelta(days=1)).strftime("%Y-%m-%d"),
                         )
                         .select("precipitation"),
            point=point,
            scale=1000,            # IMERG native ~10 km but GEE resamples
            start=imerg_start,
            end=end,
            band="precipitation",
            unit_multiplier=0.5,   # mm/hr × 0.5hr per observation = mm
        )

    total_mm = round(chirps_mm + imerg_mm, 1)

    return {
        "total_mm":      total_mm,
        "chirps_mm":     round(chirps_mm, 1),
        "imerg_mm":      round(imerg_mm, 1),
        "windows":       chirps_windows + imerg_windows,   # combined timeline
        "window_count":  len(chirps_windows) + len(imerg_windows),
        "source_note":   (
            f"CHIRPS {start.isoformat()}→{chirps_end.isoformat()} + "
            f"IMERG {imerg_start.isoformat()}→{end.isoformat()}"
        ),
    }


def _sum_rainfall_windows(
    collection: ee.ImageCollection,
    point: ee.Geometry,
    scale: int,
    start: date,
    end: date,
    band: str,
    unit_multiplier: float,
) -> tuple[float, list]:

    # ── Guard: return zeros if collection is empty ────────────
    if collection.size().getInfo() == 0:
        return 0.0, []

    # Total over full period
    total_img  = collection.sum().multiply(unit_multiplier)
    total_dict = total_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=point,
        scale=scale,
        maxPixels=1e9,
    ).getInfo()
    total_mm = total_dict.get(band) or 0.0

    # 10-day windows
    windows = []
    cursor  = start
    while cursor <= end:
        w_end = min(cursor + timedelta(days=9), end)
        w_col = collection.filterDate(
            cursor.strftime("%Y-%m-%d"),
            (w_end + timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        # ── Guard per window too ──────────────────────────────
        if w_col.size().getInfo() == 0:
            windows.append({"window_start": cursor.isoformat(), "mm": 0.0})
            cursor = w_end + timedelta(days=1)
            continue

        val_dict = (
            w_col.sum()
            .multiply(unit_multiplier)
            .reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=point,
                scale=scale,
                maxPixels=1e9,
            ).getInfo()
        )
        windows.append({
            "window_start": cursor.isoformat(),
            "mm":           round(val_dict.get(band) or 0, 1),
        })
        cursor = w_end + timedelta(days=1)

    return total_mm, windows
# ─────────────────────────────────────────────────────────────
#  ERA5 — GDD + HEAT STRESS
# ─────────────────────────────────────────────────────────────
def _extract_era5(
    point: ee.Geometry,
    start: date,
    end: date,
    t_base: float,
    t_stress: float,
) -> dict:
    """
    ERA5-Land daily temperature → cumulative GDD and heat-stress fraction.
    Temperatures in ERA5 are in Kelvin — we convert to °C.
    """
    start_str = start.strftime("%Y-%m-%d")
    end_str   = (end + timedelta(days=1)).strftime("%Y-%m-%d")

    era5 = (
        ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_RAW")
        .filterDate(start_str, end_str)
        .filterBounds(point)
        .select(["temperature_2m_max", "temperature_2m_min"])
    )

    # Convert K → °C and add GDD + stress bands
    def process(img):
        tmax = img.select("temperature_2m_max").subtract(273.15)
        tmin = img.select("temperature_2m_min").subtract(273.15)
        tavg = tmax.add(tmin).divide(2)
        gdd  = tavg.subtract(t_base).max(0).rename("gdd")
        stress = tmax.gt(t_stress).rename("stress")
        return img.addBands([tmax.rename("tmax_c"), tmin.rename("tmin_c"), gdd, stress])

    processed = era5.map(process)

    # Cumulative GDD
    cum_gdd_val = (
        processed.select("gdd").sum()
        .reduceRegion(ee.Reducer.mean(), point, _ERA5_SCALE_M, maxPixels=1e9)
        .get("gdd")
        .getInfo()
    )

    # Fraction of days above heat-stress threshold
    total_days  = era5.size().getInfo()
    stress_days = (
        processed.select("stress").sum()
        .reduceRegion(ee.Reducer.mean(), point, _ERA5_SCALE_M, maxPixels=1e9)
        .get("stress")
        .getInfo()
    )

    # Latest 7-day temperature for UI display
    recent_start = (end - timedelta(days=6)).strftime("%Y-%m-%d")
    recent = processed.filterDate(recent_start, end_str)
    recent_tmax = (
        recent.select("tmax_c").mean()
        .reduceRegion(ee.Reducer.mean(), point, _ERA5_SCALE_M, maxPixels=1e9)
        .get("tmax_c")
        .getInfo()
    )
    recent_tmin = (
        recent.select("tmin_c").mean()
        .reduceRegion(ee.Reducer.mean(), point, _ERA5_SCALE_M, maxPixels=1e9)
        .get("tmin_c")
        .getInfo()
    )

    heat_stress_frac = round((stress_days or 0) / max(total_days, 1), 3)

    return {
        "cumulative_gdd":     round(cum_gdd_val or 0, 1),
        "heat_stress_frac":   heat_stress_frac,     # fraction 0–1
        "heat_stress_days":   round(stress_days or 0),
        "total_days":         total_days,
        "recent_tmax_c":      round(recent_tmax or 0, 1),
        "recent_tmin_c":      round(recent_tmin or 0, 1),
        "t_base_used":        t_base,
        "t_stress_used":      t_stress,
    }


# ─────────────────────────────────────────────────────────────
#  SOILGRIDS (STATIC — CACHED)
# ─────────────────────────────────────────────────────────────
def _extract_soilgrids(point: ee.Geometry, aoi: ee.Geometry, field_id: int) -> dict:
    """
    Read soil data from DB (cached from ISQAper REST API).
    No GEE calls — soil is fetched once via soil_service.py and cached.
    """
    from .models import FieldSoilData
    from .soil_service import fetch_and_store_soil
    from django.utils.timezone import now

    try:
        soil = FieldSoilData.objects.get(field_id=field_id)
        # Refresh if older than 180 days
        if (now() - soil.fetched_at).days > 180:
            soil = fetch_and_store_soil(field_id)
    except FieldSoilData.DoesNotExist:
        # First time — fetch from ISQAper and cache
        soil = fetch_and_store_soil(field_id)

    return {
        # Core ML features (Pipeline 3)
        "soc_gkg":               float(soil.soc_gkg)               if soil.soc_gkg               else None,
        "clay_pct":              float(soil.clay_pct)               if soil.clay_pct              else None,
        "soil_ph":               float(soil.soil_ph)                if soil.soil_ph               else None,
        "bulk_density":          float(soil.bulk_density)           if soil.bulk_density          else None,
        "total_nitrogen":        float(soil.nitrogen_gkg)           if soil.nitrogen_gkg          else None,
        "sand_pct":              float(soil.sand_pct)               if soil.sand_pct              else None,
        "silt_pct":              float(soil.silt_pct)               if soil.silt_pct              else None,
        # Extended nutrients
        "total_phosphorus_mgkg": float(soil.total_phosphorus_mgkg)  if soil.total_phosphorus_mgkg else None,
        "total_potassium_mgkg":  float(soil.total_potassium_mgkg)   if soil.total_potassium_mgkg  else None,
        "phosphorus_olsen_mgkg": float(soil.phosphorus_olsen_mgkg)  if soil.phosphorus_olsen_mgkg else None,
        "exchangeable_k":        float(soil.exchangeable_k)         if soil.exchangeable_k        else None,
        "cec":                   float(soil.cec)                    if soil.cec                   else None,
        # Water
        "plant_available_water": float(soil.plant_available_water)  if soil.plant_available_water else None,
        "wilting_point":         float(soil.wilting_point)          if soil.wilting_point         else None,
        # Context
        "soil_type":             soil.soil_type,
        "elevation_m":           float(soil.elevation_m)            if soil.elevation_m           else None,
        "slope_pct":             float(soil.slope_pct)              if soil.slope_pct             else None,
        "erosion_class":         soil.erosion_class,
        "annual_precip_mm":      float(soil.annual_precip_mm)       if soil.annual_precip_mm      else None,
    }
# ─────────────────────────────────────────────────────────────
#  STRESS FLAG BUILDER  (feeds Pipeline 4 LLM)
# ─────────────────────────────────────────────────────────────
def _build_stress_flags(
    sentinel: dict,
    era5: dict,
    chirps: dict,
    soil: dict,
    cfg: dict,
) -> list[str]:
    """
    Build a plain-text list of agronomic stress flags.
    These map directly to the LLM advisory prompt in Pipeline 4.
    Thresholds are crop-type aware via cfg.
    """
    flags = []

    # ── Vegetation ───────────────────────────────────────────
    ndvi = sentinel.get("ndvi_latest")
    ndre = sentinel.get("ndre_latest")
    if ndvi is not None and ndvi < 0.35:
        flags.append(f"Low canopy greenness (NDVI={ndvi:.2f}) — possible sparse stand, nutrient stress, or early pest damage")
    if ndre is not None and ndre < 0.20:
        flags.append(f"Low chlorophyll/nitrogen signal (NDRE={ndre:.2f}) — consider top-dressing nitrogen fertiliser")

    # ── Heat stress ──────────────────────────────────────────
    hsfrac = era5.get("heat_stress_frac", 0)
    if hsfrac > 0.20:
        flags.append(
            f"Significant heat stress: {era5.get('heat_stress_days')} days above "
            f"{cfg['t_stress']}°C ({hsfrac*100:.0f}% of monitoring period)"
        )

    # ── Rainfall ─────────────────────────────────────────────
    total_mm  = chirps.get("total_mm", 0)
    days_mon  = max(sentinel.get("scene_count", 1), 1)
    # Simple proxy: <2 mm/day average is drought-like in highland Kenya
    rain_rate = total_mm / max((days_mon * 10), 1)  # rough daily rate
    if rain_rate < 2.0:
        flags.append(f"Below-average rainfall ({total_mm:.0f} mm total) — monitor soil moisture; consider supplemental irrigation")

    # ── Soil ─────────────────────────────────────────────────
    soc = soil.get("soc_gkg")
    if soc is not None and soc < 5.0:
        flags.append(f"Low soil organic carbon ({soc:.1f} g/kg) — consider organic amendments to improve water retention")
    ph = soil.get("soil_ph")
    if ph is not None and (ph < 5.5 or ph > 7.5):
        flags.append(f"Soil pH {ph:.1f} may limit nutrient availability — liming or acidification recommended")

    return flags


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────
def _trapezoid_auc(values: list[float]) -> float:
    """Trapezoidal numerical integration (equal time steps assumed)."""
    if len(values) < 2:
        return values[0] if values else 0.0
    total = 0.0
    for i in range(1, len(values)):
        total += (values[i - 1] + values[i]) / 2
    return total


def _early_return(field, activity, planting_dt: date, crop_name: str) -> dict:
    """Return a minimal bundle when data is not yet available (< 7 days post-planting)."""
    return {
        "meta": {
            "field_id":       field.pk,
            "field_name":     field.name,
            "activity_id":    activity.pk,
            "crop_type":      crop_name,
            "planting_date":  planting_dt.isoformat(),
            "days_monitored": 0,
            "centroid_lat":   field.geometry.centroid.y,
            "centroid_lon":   field.geometry.centroid.x,
            "field_area_ha":  field.area,
        },
        "sentinel":     {"scene_count": 0, "scenes": [], "ndvi_latest": None,
                         "ndre_latest": None, "evi_latest": None, "ndvi_auc": None,
                         "ndre_peak": None},
        "chirps":       {"total_mm": 0, "windows": []},
        "era5":         {"cumulative_gdd": 0, "heat_stress_frac": 0, "heat_stress_days": 0},
        "soil":         {},
        "stress_flags": [],
        "ready_for_ml": False,
    }


def _save_to_db(field_id: int, activity_id: int, bundle: dict) -> None:
    """
    Persist the feature bundle to the AnalysisResult model.
    Import is lazy so this module can be imported before Django is fully set up.
    """
    try:
        from .models import AnalysisResult  # defined below — add to models.py
        AnalysisResult.objects.update_or_create(
            field_id=field_id,
            activity_id=activity_id,
            defaults={
                "ndvi_latest":      bundle["sentinel"].get("ndvi_latest"),
                "ndre_latest":      bundle["sentinel"].get("ndre_latest"),
                "ndvi_auc":         bundle["sentinel"].get("ndvi_auc"),
                "ndre_peak":        bundle["sentinel"].get("ndre_peak"),
                "scene_count":      bundle["sentinel"].get("scene_count", 0),
                "total_rainfall_mm":bundle["chirps"].get("total_mm"),
                "cumulative_gdd":   bundle["era5"].get("cumulative_gdd"),
                "heat_stress_frac": bundle["era5"].get("heat_stress_frac"),
                "soc_gkg":          bundle["soil"].get("soc_gkg"),
                "soil_ph":          bundle["soil"].get("soil_ph"),
                "stress_flags":     bundle["stress_flags"],
                "full_bundle":      bundle,   # JSONField — full payload for Pipeline 3/4
                "latest_scene_date":bundle["sentinel"].get("latest_date"),
            },
        )
    except Exception as exc:
        # Non-fatal — log and continue; pipeline result is still returned
        logger.error("Failed to save AnalysisResult to DB: %s", exc)