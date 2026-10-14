# base/soil_service.py
import requests
import logging
from typing import Optional, Dict, Any
from .models import Field, FieldSoilData

logger = logging.getLogger(__name__)

ISQAPER_URL = "https://isqaper.isric.org/isqaper-rest/api/1.0/query"


# ─────────────────────────────────────────────────────────────
#  RAW FETCH
# ─────────────────────────────────────────────────────────────
def _fetch_raw(lon: float, lat: float, timeout: int = 30) -> Optional[Dict]:
    try:
        response = requests.get(
            f"{ISQAPER_URL}?lon={lon}&lat={lat}",
            timeout=timeout,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("features"):
            logger.warning("ISQAper returned no features for lon=%s lat=%s", lon, lat)
            return None
        return data
    except requests.RequestException as exc:
        logger.error("ISQAper request failed: %s", exc)
        return None


# ─────────────────────────────────────────────────────────────
#  SAFE EXTRACTOR
# ─────────────────────────────────────────────────────────────
def _get(data: Dict, *keys: str, default: Any = None) -> Any:
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    return current if current is not None else default


# ─────────────────────────────────────────────────────────────
#  PARSE
# ─────────────────────────────────────────────────────────────
def _parse(raw: Dict) -> Dict:
    feature = raw["features"][0]
    props   = feature.get("properties", {}).get("properties", {})
    geo     = feature.get("properties", {})

    # ── Physical ─────────────────────────────────────────────
    sand         = _get(props, "SNDPPT_M_sl1_250m_ll_0-30cm.tif",            "value")
    clay         = _get(props, "CLYPPT_M_sl1_250m_ll_0-30cm.tif",            "value")
    silt         = _get(props, "SLTPPT_M_sl1_250m_ll_0-30cm.tif",            "value")
    bulk_density = _get(props, "BLDFIE_M_sl1_250m_ll_0-30cm.tif",            "value")

    # ── Chemical ─────────────────────────────────────────────
    ph             = _get(props, "PHIHOX_M_sl1_250m_ll_by10_0-30cm.tif",     "value")
    organic_carbon = _get(props, "ORCDRC_M_sl1_250m_ll_0-30cm.tif",          "value")
    cec            = _get(props, "CECSOL_M_sl1_250m_ll_0-30cm.tif",          "value")
    ec             = _get(props, "Electrical_conductivity_0-29cm_250m.tif",   "value")

    # ── Nutrients ────────────────────────────────────────────
    total_n  = _get(props, "Total_nitrogen_0-29cm_250m.tif",                  "value")
    total_p  = _get(props, "Total_phosphorus_0-29cm_250m.tif",                "value")
    total_k  = _get(props, "Total_potassium_0-29cm_250m.tif",                 "value")
    exch_k   = _get(props, "Exchangeable_potassium_0-29cm_250m.tif",          "value")
    p_olsen  = _get(props, "Phosphorus_Olsen_method_0-29cm_250m.tif",         "value")

    # ── Water ────────────────────────────────────────────────
    water_pf2   = _get(props, "AWCh1_M_sl1_250m_ll_pF2_0-30cm.tif",          "value")
    water_pf2_5 = _get(props, "AWCh1_M_sl1_250m_ll_pF2.5_0-30cm.tif",        "value")
    wilting     = _get(props, "AWCh1_M_sl1_250m_ll_pF4.2_0-30cm.tif",        "value")
    plant_water = _get(props, "Plant_available_water_storage_capacity_mm_in_depth_of_0-30_cm.tif", "value")

    # ── Classification ───────────────────────────────────────
    classification = geo.get("classification", {})
    soil_type      = _get(classification, "TAXNWRB_250m_ll.tif",              "value")

    # ── Climate ──────────────────────────────────────────────
    climate      = geo.get("climate", {})
    climate_type = _get(climate, "World_Koppen_250m.tif",                     "value")

    # ── Geomorphology ────────────────────────────────────────
    geomorph  = geo.get("geomorphology", {})
    elevation = _get(geomorph, "Altitude_asl_meter.tif",                      "value")
    slope     = _get(geomorph, "Slope_percentage_gdal.tif",                   "value")

    # ── Biological ───────────────────────────────────────────
    bio       = geo.get("biological_properties", {})
    microbial = _get(bio, "Global_estimates_of_soil_microbial_abundance.tif", "value")
    macrofauna= _get(bio, "Soil_macrofauna.tif",                              "value")

    # ── Threats ──────────────────────────────────────────────
    threats       = geo.get("threats", {})
    soil_loss     = _get(threats, "RUSLE_Soil_Loss_2012_250m_mosaic.tif",     "value")
    erosion_class = _get(threats, "RUSLE_Soil_Loss_2012_250m_mosaic_reclassified.tif", "value")
    desert_vuln   = _get(threats, "Global_desertification_vulnerability_reclassified.tif", "value")

    # ── Meteo ────────────────────────────────────────────────
    meteo          = geo.get("meteo", {})
    annual_temp    = _get(meteo, "Annual_mean_temperature_oC_250m.tif",       "value")
    annual_precip  = _get(meteo, "Annual_precipitation_mm.tif",               "value")

    # ph is stored ×10 in ISQAper — divide to get real pH
    ph_real = round(ph / 10, 2) if ph is not None else None

    return {
        # Physical
        "sand_pct":              sand,
        "clay_pct":              clay,
        "silt_pct":              silt,
        "bulk_density":          bulk_density,
        # Chemical
        "soil_ph":               ph_real,
        "soc_gkg":               organic_carbon,
        "cec":                   cec,
        "electrical_conductivity": ec,
        # Nutrients
        "nitrogen_gkg":          total_n,
        "total_phosphorus_mgkg": total_p,
        "total_potassium_mgkg":  total_k,
        "exchangeable_k":        exch_k,
        "phosphorus_olsen_mgkg": p_olsen,
        # Water
        "water_capacity_pf2":    water_pf2,
        "water_capacity_pf2_5":  water_pf2_5,
        "wilting_point":         wilting,
        "plant_available_water": plant_water,
        # Classification
        "soil_type":             soil_type,
        "climate_type":          climate_type,
        # Geomorphology
        "elevation_m":           elevation,
        "slope_pct":             slope,
        # Biological
        "microbial_abundance":   microbial,
        "macrofauna_groups":     macrofauna,
        # Threats
        "soil_loss":             soil_loss,
        "erosion_class":         erosion_class,
        "desertification_vuln":  desert_vuln,
        # Meteo
        "annual_temp_c":         annual_temp,
        "annual_precip_mm":      annual_precip,
    }


# ─────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────────
def fetch_and_store_soil(field_id: int) -> "FieldSoilData":
    """
    Fetch soil data from ISQAper REST API and cache in DB.
    Called once per field — refreshed after 180 days.
    """
    from .models import FieldSoilData
    from django.utils.timezone import now

    field    = Field.objects.get(pk=field_id)
    centroid = field.geometry.centroid
    lon, lat = centroid.x, centroid.y

    raw = _fetch_raw(lon, lat)

    if raw is None:
        # Return existing or empty record — pipeline continues with nulls
        soil, _ = FieldSoilData.objects.get_or_create(field=field)
        return soil

    parsed = _parse(raw)

    soil, _ = FieldSoilData.objects.update_or_create(
        field=field,
        defaults=parsed,
    )

    logger.info(
        "ISQAper soil stored — field=%s SOC=%.1f pH=%.1f N=%.2f clay=%.1f%%",
        field_id,
        parsed.get("soc_gkg")      or 0,
        parsed.get("soil_ph")      or 0,
        parsed.get("nitrogen_gkg") or 0,
        parsed.get("clay_pct")     or 0,
    )
    return soil