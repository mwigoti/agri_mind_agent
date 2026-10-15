from __future__ import annotations
"""
agrivision_pipeline.py
=======================
Django Management Command — AgriVision Combined Analysis Pipeline

PROCESSING UNIT: FieldActivity (activity_type='planting')
    County   → activity.field.owner.location   (CustomUser.location)
    Crop     → activity.crop.name              (FK to Crop model)
    Planting → activity.date
    Stages   → CropGrowthStage rows if present, else derived from Crop.growing_season_days
    Soil     → FieldSoilData (OneToOneField on Field) if present, else SoilGrids API
    Weather  → WeatherData rows if present, else OpenWeatherMap API

WHAT IT DOES:
    1. Queries all planting FieldActivity records (optionally filtered).
    2. For each activity runs BOTH pipelines:
         • AgrivisionCompleteAnalyzer  – all 18 scientific indices (VHI, SPI,
           WSI, CSI, SVS, CHI, yield simple model, anomaly, confidence)
         • AgrivisionProductionPipeline – ML Voting Regressor prediction +
           Hugging Face agronomic narrative report
    3. Saves / updates the AnalysisResult row keyed on (field, activity).

PLACEMENT IN YOUR DJANGO PROJECT:
    yourapp/
    └── management/
        └── commands/
            └── agrivision_pipeline.py   ← this file

USAGE:
    python manage.py agrivision_pipeline
    python manage.py agrivision_pipeline --activity-id 7
    python manage.py agrivision_pipeline --field-id 42
    python manage.py agrivision_pipeline --county "Uasin Gishu"
    python manage.py agrivision_pipeline --dry-run
    python manage.py agrivision_pipeline --no-gee --dry-run   # fast local test

REQUIRED PACKAGES:
    pip install earthengine-api numpy requests joblib pandas

ENVIRONMENT VARIABLES:
    DJANGO_APP_LABEL          your app label (default: 'fields')
    OPENWEATHER_API_KEY       optional — used only when WeatherData rows absent
    HUGGINGFACE_API_TOKEN     for LLM agronomic report
    AGRIVISION_ML_MODEL_PATH  path to agrivision_ULTIMATE_voting_ensemble.pkl

AUTHENTICATION:
    earthengine authenticate
"""
import ee
import pandas as pd
import signal
import joblib
import json
import logging
import os
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import requests

# ── Django ────────────────────────────────────────────────────────────────────
import django
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: convert Django / GeoJSON polygon to coordinate list
# ─────────────────────────────────────────────────────────────────────────────

def polygon_to_coords(geometry) -> List[List[float]]:
    """
    Accepts any of:
      • A Django GeoDjango Polygon / MultiPolygon field value
      • A GeoJSON dict  {"type": "Polygon", "coordinates": [...]}
      • A raw string of the above JSON
    Returns [[lon, lat], [lon, lat], ...] closing ring for GEE.
    """
    # ── string → dict
    if isinstance(geometry, str):
        geometry = json.loads(geometry)

    # ── GeoDjango geometry object → dict
    if hasattr(geometry, 'geojson'):
        geometry = json.loads(geometry.geojson)
    elif hasattr(geometry, 'json'):
        geometry = json.loads(geometry.json)

    geo_type = geometry.get('type', '')

    if geo_type == 'Polygon':
        ring = geometry['coordinates'][0]           # outer ring
    elif geo_type == 'MultiPolygon':
        ring = geometry['coordinates'][0][0]        # first polygon outer ring
    elif geo_type == 'Point':
        lon, lat = geometry['coordinates']
        delta = 0.005                               # ~550 m bounding box
        ring = [
            [lon - delta, lat - delta],
            [lon + delta, lat - delta],
            [lon + delta, lat + delta],
            [lon - delta, lat + delta],
            [lon - delta, lat - delta],
        ]
    else:
        raise ValueError(f"Unsupported geometry type: {geo_type}")

    # GEE expects [[lon, lat], ...]
    coords = [[c[0], c[1]] for c in ring]

    # Close the ring if needed
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    return coords
    print(coords)

def derive_growth_stages(planting_date: str,
                         crop_type: str = 'maize',
                         total_days: int = None) -> Dict[str, List[str]]:
    """
    Derive approximate phenological windows from a planting date.

    If total_days is supplied (from Crop.growing_season_days) the four
    pipeline stages are distributed proportionally across it.
    Otherwise falls back to hard-coded defaults per crop type.

    Pipeline stage names     ←→    CropGrowthStage.stage choices
    ─────────────────────────────────────────────────────────────
    'vegetative'             ←→    'seedling' + 'vegetative'
    'flowering'              ←→    'flowering'
    'grain_filling'          ←→    'fruiting'
    'maturity'               ←→    'maturation' + 'harvest_ready'
    """
    # proportions of total season per pipeline stage
    proportions = {'vegetative': 0.30, 'flowering': 0.20,
                   'grain_filling': 0.30, 'maturity': 0.20}

    if total_days:
        durations = {s: max(7, int(p * total_days))
                     for s, p in proportions.items()}
    else:
        defaults = {
            'maize': {'vegetative': 45, 'flowering': 30, 'grain_filling': 45, 'maturity': 30},
            'wheat': {'vegetative': 60, 'flowering': 20, 'grain_filling': 40, 'maturity': 25},
            'rice':  {'vegetative': 50, 'flowering': 25, 'grain_filling': 35, 'maturity': 20},
        }
        durations = defaults.get(crop_type.lower(),
                                  defaults['maize'])

    fmt    = '%Y-%m-%d'
    t0     = datetime.strptime(planting_date, fmt)
    stages = {}
    cursor = t0
    for stage, days in durations.items():
        end = cursor + timedelta(days=days)
        stages[stage] = [cursor.strftime(fmt), end.strftime(fmt)]
        cursor = end
    return stages


def stages_from_growth_stage_qs(qs) -> Dict[str, List[str]]:
    """
    Build the four pipeline stage windows from a CropGrowthStage queryset.

    CropGrowthStage.stage choices → pipeline key mapping:
        seedling + vegetative  → 'vegetative'
        flowering              → 'flowering'
        fruiting               → 'grain_filling'
        maturation + harvest_ready → 'maturity'

    Returns an empty dict if the queryset has no rows (caller should fall
    back to derive_growth_stages).
    """
    # group DB stage rows by pipeline key
    STAGE_MAP = {
        'seedling':      'vegetative',
        'vegetative':    'vegetative',
        'flowering':     'flowering',
        'fruiting':      'grain_filling',
        'maturation':    'maturity',
        'harvest_ready': 'maturity',
    }
    buckets: Dict[str, List] = {k: [] for k in
                                 ['vegetative', 'flowering', 'grain_filling', 'maturity']}

    for row in qs:
        key = STAGE_MAP.get(row.stage)
        if key:
            buckets[key].append(row)

    result = {}
    fmt = '%Y-%m-%d'
    for key, rows in buckets.items():
        if not rows:
            continue
        start = min(r.start_date for r in rows).strftime(fmt)
        # prefer actual_end_date when recorded, else expected_end_date
        end   = max(
            (r.actual_end_date or r.expected_end_date) for r in rows
        ).strftime(fmt)
        result[key] = [start, end]

    return result


def soil_context_from_db(field) -> Optional[Dict]:
    """
    Read FieldSoilData (OneToOneField reverse accessor: field.soil_data).
    Returns a dict that matches what AgrivisionCompleteAnalyzer expects,
    or None if no soil record exists yet.

    FieldSoilData field        → pipeline key
    ──────────────────────────────────────────
    soc_gkg                    → organic_carbon   (g/kg — same unit)
    soil_ph                    → ph
    clay_pct                   → clay_percent
    sand_pct                   → sand_percent
    cec                        → cec
    bulk_density (kg/m³ ÷ 1000)→ bulk_density     (g/cm³)
    water_capacity_pf2         → field_capacity   (% → 0-1 fraction)
    wilting_point              → wilting_point    (% → 0-1 fraction)
    """
    try:
        sd = field.soil_data          # reverse OneToOneField accessor
    except Exception:
        return None

    def f(val, divisor=1.0):
        """Safe float conversion, returns None on null."""
        return float(val) / divisor if val is not None else None

    soil = {
        'organic_carbon': f(sd.soc_gkg),
        'ph':             f(sd.soil_ph),
        'clay_percent':   f(sd.clay_pct),
        'sand_percent':   f(sd.sand_pct),
        'cec':            f(sd.cec),
        'bulk_density':   f(sd.bulk_density, 1000.0),  # kg/m³ → g/cm³
        # water retention stored as % in DB → convert to 0-1 fraction
        'field_capacity': f(sd.water_capacity_pf2,  100.0) if sd.water_capacity_pf2  else None,
        'wilting_point':  f(sd.wilting_point,        100.0) if sd.wilting_point       else None,
    }
    # fill any None with SoilGrids-style defaults so downstream code never
    # receives None
    defaults = {'organic_carbon': 20, 'ph': 6.5, 'clay_percent': 30,
                'sand_percent': 40, 'cec': 15, 'bulk_density': 1.4,
                'field_capacity': 0.25, 'wilting_point': 0.12}
    return {k: (v if v is not None else defaults[k]) for k, v in soil.items()}


def weather_from_db(field, n_days: int = 60) -> Optional[Dict]:
    """
    Read the most recent n_days of WeatherData rows for the field.
    Returns a dict compatible with AgrivisionCompleteAnalyzer.fetch_weather_data,
    or None if fewer than 7 rows exist (not enough for GDD series).

    WeatherData fields used:
        temperature_avg  → current temperature scalar
        humidity         → humidity scalar
        temperature_max  → temp_max_series list
        temperature_min  → temp_min_series list
    """
    try:
        # WeatherData.objects manager via related_name='weather_data'
        qs = (field.weather_data
              .filter(is_forecast=False)
              .order_by('-date')[:n_days])
        rows = list(qs)
    except Exception:
        return None

    if len(rows) < 7:
        return None

    # reverse so series is chronological (oldest first = correct for GDD sum)
    rows.reverse()
    return {
        'temperature':       float(rows[-1].temperature_avg),
        'humidity':          float(rows[-1].humidity),
        'temp_max_series':   [float(r.temperature_max) for r in rows],
        'temp_min_series':   [float(r.temperature_min) for r in rows],
    }


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE 1 — AgrivisionCompleteAnalyzer  (all 18 scientific indices)
# ─────────────────────────────────────────────────────────────────────────────

class AgrivisionCompleteAnalyzer:
    """
    All 18 scientific formulas + GEE + external APIs.
    Condensed from agrivision_complete_standalone.py.
    """

    def __init__(self, openweather_api_key: str = None, use_gee: bool = True):
        self.openweather_api_key = openweather_api_key
        self.use_gee = use_gee

        self.weights = {
            'vhi':  {'alpha': 0.5},
            'spi':  {'whc': 0.35, 'soc': 0.30, 'cec': 0.20, 'texture': 0.15},
            'csi':  {'rainfall': 0.40, 'temperature': 0.35, 'gdd': 0.25},
            'chi':  {'vhi': 0.30, 'spi': 0.25, 'water': 0.25, 'csi': 0.15, 'rsi': 0.05},
            'svs':  {
                'vegetative':   {'ndvi': 0.4, 'evi': 0.3, 'ndmi': 0.3},
                'flowering':    {'ndvi': 0.35, 'evi': 0.35, 'ndmi': 0.3},
                'grain_filling':{'ndvi': 0.3, 'evi': 0.2, 'ndmi': 0.5},
                'maturity':     {'ndvi': 0.4, 'evi': 0.3, 'ndmi': 0.3},
            },
        }
        self.crop_params = {
            'maize': {'T_base': 10, 'T_opt_min': 18, 'T_opt_max': 32,
                      'water_req_veg': 500, 'water_req_grain': 350, 'Y_max': 10.0},
            'wheat': {'T_base': 0,  'T_opt_min': 15, 'T_opt_max': 25,
                      'water_req_veg': 300, 'water_req_grain': 250, 'Y_max': 6.0},
            'rice':  {'T_base': 10, 'T_opt_min': 20, 'T_opt_max': 35,
                      'water_req_veg': 800, 'water_req_grain': 600, 'Y_max': 8.0},
        }

        if use_gee:
            try:
                import ee
                # AGRIVISION_GEE_PROJECT must be set in your environment.
                # Find it at: console.cloud.google.com → project selector → copy Project ID
                gee_project = os.environ.get('AGRIVISION_GEE_PROJECT')
                if gee_project:
                    ee.Initialize(project=gee_project)
                else:
                    ee.Initialize()          # falls back to application default credentials
                self._ee = ee
                logger.info("GEE initialised (Analyzer) project=%s", gee_project or 'default')
            except Exception as exc:
                logger.warning("GEE init failed (Analyzer): %s", exc)
                self.use_gee = False
                self._ee = None
        else:
            self._ee = None

    # ── external data fetchers ─────────────────────────────────────────────

    def fetch_soilgrids_data(self, lat: float, lon: float) -> Dict:
        """
        Fetch soil properties from ISRIC SoilGrids v2 REST API.
        Endpoint: https://rest.isric.org/soilgrids/v2.0/properties/query
        Depth layer: 0-30 cm mean
        """
        DEFAULTS = {
            'organic_carbon': 20, 'clay_percent': 30, 'sand_percent': 40,
            'ph': 6.5, 'cec': 15, 'bulk_density': 1.4,
            'field_capacity': 0.25, 'wilting_point': 0.12,
        }
        try:
            # SoilGrids v2 — one request with all needed properties
            url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
            params = [
                ('lon',      lon),
                ('lat',      lat),
                ('property', 'phh2o'),   # pH ×10
                ('property', 'soc'),     # SOC g/kg ×10
                ('property', 'clay'),    # clay g/kg  (÷10 → %)
                ('property', 'sand'),    # sand g/kg  (÷10 → %)
                ('property', 'cec'),     # CEC mmolc/kg (÷10 → cmolc/kg)
                ('property', 'bdod'),    # bulk density cg/cm³ (÷100 → g/cm³)
                ('depth',    '0-30cm'),
                ('value',    'mean'),
            ]
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()

            # Response shape: data['properties']['layers'] is a list of dicts
            # Each layer: {'name': 'phh2o', 'depths': [{'label':'0-30cm',
            #               'values': {'mean': 65}}], ...}
            layers = {
                layer['name']: layer['depths'][0]['values'].get('mean')
                for layer in data.get('properties', {}).get('layers', [])
                if layer.get('depths')
            }

            def pick(key, divisor, fallback):
                raw = layers.get(key)
                return float(raw) / divisor if raw is not None else fallback

            soc  = pick('soc',   10.0,  DEFAULTS['organic_carbon'])   # dg/kg → g/kg
            clay = pick('clay',  10.0,  DEFAULTS['clay_percent'])      # g/kg  → %
            sand = pick('sand',  10.0,  DEFAULTS['sand_percent'])      # g/kg  → %
            ph   = pick('phh2o', 10.0,  DEFAULTS['ph'])                # pH×10 → pH
            cec  = pick('cec',   10.0,  DEFAULTS['cec'])               # mmol  → cmol
            bdod = pick('bdod',  100.0, DEFAULTS['bulk_density'])      # cg/cm³→ g/cm³

            props = {
                'organic_carbon': soc,
                'clay_percent':   clay,
                'sand_percent':   sand,
                'ph':             ph,
                'cec':            cec,
                'bulk_density':   bdod,
                'field_capacity': 0.2576 - 0.002 * sand + 0.0036 * clay,
                'wilting_point':  0.026  + 0.005 * clay,
            }
            logger.info(
                "SoilGrids v2 OK (%.4f, %.4f) pH=%.1f SOC=%.1f clay=%.1f%%",
                lat, lon, ph, soc, clay,
            )
            return props

        except Exception as exc:
            logger.warning("SoilGrids fallback: %s", exc)
            return DEFAULTS

    def fetch_imerg_rainfall(self, aoi, start_date: str, end_date: str) -> Dict:
        if not self.use_gee:
            return {'total_rainfall_mm': None, 'num_days':None, 'daily_mean': None}
        try:
            ee = self._ee
            aoi_buffered = aoi.buffer(10000)

            imerg = (ee.ImageCollection('NASA/GPM_L3/IMERG_V07')  # V07
                    .filterDate(start_date, end_date)
                    .filterBounds(aoi_buffered)
                    .select('precipitation'))  # V07 uses 'precipitation' not 'precipitationCal'

            count = imerg.size().getInfo()
            if count == 0:
                logger.warning("IMERG V07: no images for %s→%s, trying CHIRPS",
                            start_date, end_date)
                return self.fetch_chirps_rainfall(aoi, start_date, end_date)  # correct name

            total = (imerg.sum()
                    .multiply(0.5)  # mm/hr → mm per 30-min step
                    .reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=aoi_buffered,
                        scale=10000,
                        maxPixels=1e9,
                        bestEffort=True
                    ).getInfo())

            tot    = float(total.get('precipitation') or 0.0)
            n_days = max(1, (datetime.strptime(end_date, '%Y-%m-%d') -
                            datetime.strptime(start_date, '%Y-%m-%d')).days)

            logger.info("IMERG V07 OK [%s→%s]: %.1fmm", start_date, end_date, tot)
            return {
                'total_rainfall_mm': round(tot, 1),
                'num_days':          n_days,
                'daily_mean':        round(tot / n_days, 2),
            }

        except Exception as exc:
            logger.warning("ERA5 rainfall failed [%s→%s]: %s", start_date, end_date, exc)
            return {'total_rainfall_mm': None, 'num_days': 0, 'daily_mean': None}
    def fetch_weather_data(self, lat: float, lon: float) -> Dict:
        if not self.openweather_api_key:
            return {'temperature': 22, 'humidity': 65,
                    'temp_max_series': [26]*60, 'temp_min_series': [14]*60}
        try:
            r = requests.get("https://api.openweathermap.org/data/2.5/weather",
                             params={'lat': lat, 'lon': lon,
                                     'appid': self.openweather_api_key,
                                     'units': 'metric'}, timeout=10)
            r.raise_for_status()
            d   = r.json()
            tmp = d['main']['temp']
            return {'temperature': tmp, 'humidity': d['main']['humidity'],
                    'temp_max_series': [tmp + np.random.uniform(-2, 3)  for _ in range(60)],
                    'temp_min_series': [tmp - 5   + np.random.uniform(-2, 2)  for _ in range(60)]}
        except Exception as exc:
            logger.warning("OpenWeather fallback: %s", exc)
            return {'temperature': None, 'humidity': None,
                    'temp_max_series': None, 'temp_min_series': None}

    # ── date helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _clamp_dates(start_date: str, end_date: str) -> tuple:
        """
        Two adjustments applied to every satellite query:

        1. End-date clamping — GEE Sentinel-2 SR has a ~5-day processing lag.
           Any end_date beyond (today - 5) is moved back so the query doesn't
           sit waiting for imagery that isn't in the catalogue yet.

        2. Minimum window — if clamping collapses the window to < 15 days,
           push start_date back so there is always a reasonable search period.
           This handles crops planted very recently.
        """
        fmt   = '%Y-%m-%d'
        today = datetime.utcnow().date()
        lag   = timedelta(days=5)          # S2 SR processing lag
        min_w = timedelta(days=15)         # minimum window width

        start = datetime.strptime(start_date, fmt).date()
        end   = datetime.strptime(end_date,   fmt).date()

        # clamp end to today - lag
        end = min(end, today - lag)

        # ensure minimum window
        if (end - start) < min_w:
            start = end - min_w

        return start.strftime(fmt), end.strftime(fmt)

    @staticmethod
    def _push_back(start_date: str, days: int) -> str:
        """Extend start_date further into the past by `days`."""
        fmt  = '%Y-%m-%d'
        date = datetime.strptime(start_date, fmt).date() - timedelta(days=days)
        return date.strftime(fmt)

    # ── Sentinel-2 ────────────────────────────────────────────────────────

    def fetch_sentinel2_indices(self, aoi, start_date: str, end_date: str) -> Dict:
        """
        Fetch Sentinel-2 SR median composite for a date window.

        Progressive fallback strategy to maximise coverage:
        ┌──────┬────────────────────────────────┬───────────────┐
        │ Pass │ Window                         │ Max cloud %   │
        ├──────┼────────────────────────────────┼───────────────┤
        │  1   │ original (clamped)             │ 20 %          │
        │  2   │ start pushed back 30 days      │ 35 %          │
        │  3   │ start pushed back 60 more days │ 50 %          │
        └──────┴────────────────────────────────┴───────────────┘
        Each pass is tried only if the previous one returned 0 scenes.
        """
        if not self.use_gee:
            return {'total_rainfall_mm': None, 'num_days': 0, 'daily_mean': None}


        ee = self._ee

        def _query(s, e, cloud_pct):
            col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                     .filterBounds(aoi)
                     .filterDate(s, e)
                     .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_pct)))
            return col

        def _compute_indices(col):
            med  = col.median()
            ndvi = med.normalizedDifference(['B8', 'B4']).rename('NDVI')
            evi  = med.expression(
                '2.5*((NIR-RED)/(NIR+6*RED-7.5*BLUE+1))',
                {'NIR': med.select('B8'), 'RED': med.select('B4'),
                 'BLUE': med.select('B2')}).rename('EVI')
            ndmi = med.normalizedDifference(['B8', 'B11']).rename('NDMI')
            savi = med.expression('((NIR-RED)/(NIR+RED+0.5))*1.5',
                {'NIR': med.select('B8'), 'RED': med.select('B4')}).rename('SAVI')
            return (ee.Image.cat([ndvi, evi, ndmi, savi])
                    .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi,
                                  scale=10, maxPixels=1e9).getInfo())

        try:
            s, e = self._clamp_dates(start_date, end_date)

            # Pass 1 — tight window, strict cloud filter
            col = _query(s, e, cloud_pct=20)
            n   = col.size().getInfo()
            logger.info("S2 pass-1 [%s→%s] cloud<20%%: %d scenes", s, e, n)

            if n == 0:
                # Pass 2 — push start back 30 days, relax cloud to 35 %
                s2 = self._push_back(s, 30)
                col = _query(s2, e, cloud_pct=35)
                n   = col.size().getInfo()
                logger.info("S2 pass-2 [%s→%s] cloud<35%%: %d scenes", s2, e, n)

            if n == 0:
                # Pass 3 — push start back another 60 days, relax cloud to 50 %
                s3 = self._push_back(s, 90)
                col = _query(s3, e, cloud_pct=50)
                n   = col.size().getInfo()
                logger.info("S2 pass-3 [%s→%s] cloud<50%%: %d scenes", s3, e, n)

            if n == 0:
                logger.warning("S2: no scenes found after 3 passes — using fallback")
                return {'NDVI': 0.68, 'EVI': 0.52, 'NDMI': 0.40, 'SAVI': 0.58}

            vals = _compute_indices(col)
            logger.info("S2 OK — NDVI=%.3f EVI=%.3f (%d scenes)",
                        vals.get('NDVI', 0), vals.get('EVI', 0), n)
            return vals

        except Exception as exc:
            logger.warning("S2 fallback: %s", exc)
            return {'NDVI': None, 'EVI': None, 'NDMI': None, 'SAVI': None}
    def fetch_smap_moisture(self, aoi, date: str) -> float:
        if not self.use_gee:
            return None
        try:
            ee = self._ee
            dt = datetime.strptime(date, '%Y-%m-%d')
            s  = (dt - timedelta(days=3)).strftime('%Y-%m-%d')
            e  = (dt + timedelta(days=3)).strftime('%Y-%m-%d')
            smap = (ee.ImageCollection('NASA/SMAP/SPL4SMGP/008')
                    .filterDate(s, e).filterBounds(aoi))
            if smap.size().getInfo() == 0:
                return 0.25
            val = (smap.mean().select('sm_surface')
                .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi,
                                scale=11000, maxPixels=1e9).getInfo())
            return float(val.get('sm_surface') or 0.25)
        except Exception as exc:
            logger.warning("SMAP fallback: %s", exc)
            return None
    # ── Sentinel-1 SAR ────────────────────────────────────────────────────

    def fetch_sentinel1_sar(self, aoi, start_date: str, end_date: str) -> Dict:
        """
        Fetch Sentinel-1 GRD median for a date window.

        Progressive fallback strategy (S1 is cloud-independent but has a
        12-day revisit; push back further than S2):
        ┌──────┬──────────────────────────────────┐
        │ Pass │ Window                           │
        ├──────┼──────────────────────────────────┤
        │  1   │ original (clamped, 2-day lag)    │
        │  2   │ start pushed back 30 days        │
        │  3   │ start pushed back 60 more days   │
        └──────┴──────────────────────────────────┘
        """
        if not self.use_gee:
            return {'VH': None, 'VV': None, 'RSI': None}

        ee = self._ee

        def _query_s1(s, e):
            return (ee.ImageCollection('COPERNICUS/S1_GRD')
                      .filterBounds(aoi).filterDate(s, e)
                      .filter(ee.Filter.listContains(
                          'transmitterReceiverPolarisation', 'VV'))
                      .filter(ee.Filter.listContains(
                          'transmitterReceiverPolarisation', 'VH')))

        try:
            # S1 lag is shorter (~2 days); reuse _clamp_dates then loosen
            s, e = self._clamp_dates(start_date, end_date)

            col = _query_s1(s, e)
            n   = col.size().getInfo()
            logger.info("S1 pass-1 [%s→%s]: %d scenes", s, e, n)

            if n == 0:
                s2 = self._push_back(s, 30)
                col = _query_s1(s2, e)
                n   = col.size().getInfo()
                logger.info("S1 pass-2 [%s→%s]: %d scenes", s2, e, n)

            if n == 0:
                s3 = self._push_back(s, 90)
                col = _query_s1(s3, e)
                n   = col.size().getInfo()
                logger.info("S1 pass-3 [%s→%s]: %d scenes", s3, e, n)

            if n == 0:
                logger.warning("S1: no scenes found after 3 passes — using fallback")
                return {'VH': 0.15, 'VV': 0.28, 'RSI': 0.54}

            vals = (col.median().select(['VH', 'VV'])
                    .reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi,
                                  scale=10, maxPixels=1e9).getInfo())
            vh  = vals.get('VH', 0.15)
            vv  = vals.get('VV', 0.28)
            rsi = vh / vv if vv else 0.54
            logger.info("S1 OK — VH=%.3f VV=%.3f RSI=%.3f (%d scenes)", vh, vv, rsi, n)
            return {'VH': vh, 'VV': vv, 'RSI': rsi}

        except Exception as exc:
            logger.warning("S1 fallback: %s", exc)
            return {'VH': None, 'VV': None, 'RSI': None}

    # ── scientific formulas ────────────────────────────────────────────────

    def _norm(self, v, lo, hi):
        return float(np.clip((v - lo) / (hi - lo), 0, 1)) if hi > lo else 0.5

    def calculate_vci(self, ndvi, ndvi_min, ndvi_max):
        return self._norm(ndvi, ndvi_min, ndvi_max)

    def calculate_tci(self, temp, t_min, t_max):
        return self._norm(t_max - temp, 0, t_max - t_min)

    def calculate_vhi(self, vci, tci):
        a = self.weights['vhi']['alpha']
        return float(np.clip(a * vci + (1 - a) * tci, 0, 1))

    def normalize_soil_properties(self, soil: Dict) -> Dict:
        whc = max(0.08, soil.get('field_capacity', 0.25) - soil.get('wilting_point', 0.10))
        clay, sand = soil.get('clay_percent', 30), soil.get('sand_percent', 40)
        texture    = float(np.clip(1 - abs((sand - 37.5)/50)*0.5 - abs((clay - 17)/30)*0.5, 0, 1))
        return {
            'whc_norm':     self._norm(whc, 0.05, 0.25),
            'soc_norm':     self._norm(soil.get('organic_carbon', 20), 5, 50),
            'cec_norm':     self._norm(soil.get('cec', 15), 5, 40),
            'texture_norm': texture,
        }

    def calculate_spi(self, whc, soc, cec, texture):
        w = self.weights['spi']
        return float(np.clip(w['whc']*whc + w['soc']*soc + w['cec']*cec + w['texture']*texture, 0, 1))

    def calculate_ewa(self, rainfall, whc_norm, moisture, water_req):
        if not water_req:
            return 0.5
        # moisture near zero shouldn't zero out a well-watered field
        moisture_factor = max(0.3, float(moisture))
        return float(np.clip(
            (rainfall * max(0.3, whc_norm) * moisture_factor) / water_req, 
            0, 1
        ))

    def calculate_gdd(self, tmax_series, tmin_series, t_base):
        return max(0, sum(max(0, (mx + mn)/2 - t_base) for mx, mn in zip(tmax_series, tmin_series)))

    def calculate_csi(self, rain_norm, temp_norm, gdd_norm):
        w = self.weights['csi']
        return float(np.clip(w['rainfall']*rain_norm + w['temperature']*temp_norm + w['gdd']*gdd_norm, 0, 1))

    def calculate_svs(self, ndvi, evi, ndmi, stage):
        w = self.weights['svs'].get(stage, self.weights['svs']['vegetative'])
        return float(np.clip(w['ndvi']*ndvi + w['evi']*evi + w['ndmi']*ndmi, 0, 1))

    def calculate_chi(self, vhi, spi, wsi, csi, rsi):
        w = self.weights['chi']
        return float(np.clip(w['vhi']*vhi + w['spi']*spi + w['water']*(1-wsi) + w['csi']*csi + w['rsi']*rsi, 0, 1))

    def estimate_yield_simple(self, chi, wsi, crop_type):
        return max(0.0, self.crop_params[crop_type]['Y_max'] * chi * (1 - wsi))

    def estimate_yield_regression(self, svs_veg, svs_grain, ewa_veg, ewa_grain, spi, rsi):
        b = {'beta_0':1.5,'beta_1':2.0,'beta_2':3.5,'beta_3':1.0,
             'beta_4':2.5,'beta_5':1.2,'beta_6':0.8}
        return max(0.0, b['beta_0'] + b['beta_1']*svs_veg + b['beta_2']*svs_grain +
                   b['beta_3']*ewa_veg + b['beta_4']*ewa_grain + b['beta_5']*spi + b['beta_6']*rsi)

    def calculate_yield_anomaly(self, pred, mean):
        return (pred - mean) / mean if mean > 0 else 0.0

    def calculate_confidence(self, rmse, mean_yield):
        return float(np.clip(1 - rmse/mean_yield, 0, 1)) if mean_yield > 0 else 0.5

    def _risk(self, chi, wsi, vhi):
        if chi > 0.75 and wsi < 0.30 and vhi > 0.75: return "Low"
        if chi > 0.60 and wsi < 0.50 and vhi > 0.60: return "Moderate"
        if chi > 0.45: return "High"
        return "Very High"

    # ── master run ────────────────────────────────────────────────────────

    def analyze_field(self, coords: List[List[float]], crop_type: str,
                      growth_stages: Dict, lat: float, lon: float,
                      historical_data: Dict = None,
                      preloaded_soil: Dict = None,
                      preloaded_weather: Dict = None) -> Dict:
        """
        Run all 18 scientific formulas and return a result dict.

        preloaded_soil    — pass soil_context_from_db() result to skip SoilGrids API
        preloaded_weather — pass weather_from_db() result to skip OpenWeather API
        """
        crop_type = crop_type.lower()
        if crop_type not in self.crop_params:
            crop_type = 'maize'

        hist = historical_data or {
            'ndvi_range': {'min': 0.25, 'max': 0.88},
            'temp_range':  {'min': 12,  'max': 38},
            'mean_yield':  6.5,
            'rmse':        0.8,
        }

        aoi = self._ee.Geometry.Polygon([coords]) if self.use_gee else None

        # ── fetch data — prefer pre-loaded DB values, fall back to APIs ──
        soil    = preloaded_soil    or self.fetch_soilgrids_data(lat, lon)
        weather = preloaded_weather or self.fetch_weather_data(lat, lon)

        from datetime import date as _date
        today = datetime.utcnow().date()
        RAINFALL_STAGES = {'vegetative', 'grain_filling'}
        rainfall_by_stage = {}
        for stage, dates in growth_stages.items():
            stage_start = datetime.strptime(dates[0], '%Y-%m-%d').date()
            if stage in RAINFALL_STAGES and stage_start < today:
                rd = self.fetch_imerg_rainfall(aoi, dates[0], dates[1])
                rainfall_by_stage[stage] = rd['total_rainfall_mm']
            else:
                rainfall_by_stage[stage] = 0.0
        # RIGHT AFTER the CHIRPS loop — around line 776
        print(f"DEBUG growth_stages: {growth_stages}")
        print(f"DEBUG today: {today}")
        print(f"DEBUG rainfall_by_stage: {rainfall_by_stage}")
        moisture = self.fetch_smap_moisture(aoi, list(growth_stages.values())[-1][1])
        soil['smap_moisture'] = moisture

        stage_indices = {}
        for stage, dates in growth_stages.items():
            stage_indices[stage] = self.fetch_sentinel2_indices(aoi, dates[0], dates[1])

        grain_dates = growth_stages.get('grain_filling', list(growth_stages.values())[-1])
        sar = self.fetch_sentinel1_sar(aoi, grain_dates[0], grain_dates[1])

        # ── compute indices ──
        cp        = self.crop_params[crop_type]
        grain_idx = stage_indices.get('grain_filling', stage_indices[list(stage_indices)[-1]])
        veg_idx   = stage_indices.get('vegetative',    stage_indices[list(stage_indices)[0]])
        # ── soil normalization ────────────────────────────────────────────
        if any(v is None for v in [soil.get('field_capacity'), soil.get('wilting_point')]):
            norm_soil = {'whc_norm': None, 'soc_norm': None,
                        'cec_norm': None, 'texture_norm': None}
        else:
            norm_soil = self.normalize_soil_properties(soil)

        # ── rainfall ──────────────────────────────────────────────────────
        rain_veg   = rainfall_by_stage.get('vegetative')
        rain_grain = rainfall_by_stage.get('grain_filling')

        # ── EWA ──────────────────────────────────────────────────────────
        ewa_veg = self.calculate_ewa(
            rain_veg, norm_soil.get('whc_norm'), moisture, cp['water_req_veg']
        ) if rain_veg is not None and norm_soil.get('whc_norm') is not None else None

        ewa_grain = self.calculate_ewa(
            rain_grain, norm_soil.get('whc_norm'), moisture, cp['water_req_grain']
        ) if rain_grain is not None and norm_soil.get('whc_norm') is not None else None

        wsi_grain = (1.0 - ewa_grain) if ewa_grain is not None else None

        # ── GDD ───────────────────────────────────────────────────────────
        gdd = self.calculate_gdd(
            weather['temp_max_series'], weather['temp_min_series'], cp['T_base']
        ) if weather.get('temp_max_series') else None

        # ── VCI / TCI / VHI ──────────────────────────────────────────────
        ndvi_grain = grain_idx.get('NDVI')
        vci = self.calculate_vci(
            ndvi_grain, hist['ndvi_range']['min'], hist['ndvi_range']['max']
        ) if ndvi_grain is not None else None

        tci = self.calculate_tci(
            weather['temperature'], hist['temp_range']['min'], hist['temp_range']['max']
        ) if weather.get('temperature') is not None else None

        vhi = self.calculate_vhi(vci, tci) if vci is not None and tci is not None else None

        # ── SPI ───────────────────────────────────────────────────────────
        spi = self.calculate_spi(
            norm_soil['whc_norm'], norm_soil['soc_norm'],
            norm_soil['cec_norm'], norm_soil['texture_norm']
        ) if all(v is not None for v in norm_soil.values()) else None

        # ── CSI ───────────────────────────────────────────────────────────
        total_rain = sum(v for v in rainfall_by_stage.values() if v is not None)
        avg_temp   = float(np.mean(weather['temp_max_series'])) \
                    if weather.get('temp_max_series') else None
        csi = None
        if total_rain > 0 and avg_temp is not None and gdd is not None:
            rain_norm  = self._norm(total_rain, 300, 1000)
            t_opt_lo, t_opt_hi = cp['T_opt_min'], cp['T_opt_max']
            if t_opt_lo <= avg_temp <= t_opt_hi:
                temp_norm = 1.0
            elif avg_temp < t_opt_lo:
                temp_norm = self._norm(avg_temp, cp['T_base'], t_opt_lo)
            else:
                temp_norm = 1.0 - self._norm(avg_temp, t_opt_hi, 45)
            gdd_target = {'maize': 1500, 'wheat': 1700, 'rice': 2000}.get(crop_type, 1500)
            gdd_norm   = self._norm(gdd, gdd_target * 0.7, gdd_target * 1.2)
            csi        = self.calculate_csi(rain_norm, temp_norm, gdd_norm)

        # ── SVS ───────────────────────────────────────────────────────────
        svs_veg = self.calculate_svs(
            veg_idx.get('NDVI'), veg_idx.get('EVI'), veg_idx.get('NDMI'), 'vegetative'
        ) if veg_idx.get('NDVI') is not None else None

        svs_grain = self.calculate_svs(
            grain_idx.get('NDVI'), grain_idx.get('EVI'), grain_idx.get('NDMI'), 'grain_filling'
        ) if grain_idx.get('NDVI') is not None else None

        # ── CHI ───────────────────────────────────────────────────────────
        rsi = sar.get('RSI')
        chi = self.calculate_chi(
            vhi       if vhi       is not None else 0.5,
            spi       if spi       is not None else 0.5,
            wsi_grain if wsi_grain is not None else 0.5,
            csi       if csi       is not None else 0.5,
            rsi       if rsi       is not None else 0.5,
        ) if any(v is not None for v in [vhi, spi, csi]) else None

        # ── yield estimates ───────────────────────────────────────────────
        y_simple = self.estimate_yield_simple(
            chi, wsi_grain if wsi_grain is not None else 0.5, crop_type
        ) if chi is not None else None

        y_regression = self.estimate_yield_regression(
            svs_veg   if svs_veg   is not None else 0.5,
            svs_grain if svs_grain is not None else 0.5,
            ewa_veg   if ewa_veg   is not None else 0.5,
            ewa_grain if ewa_grain is not None else 0.5,
            spi       if spi       is not None else 0.5,
            rsi       if rsi       is not None else 0.5,
        ) if any(v is not None for v in [svs_veg, svs_grain, spi]) else None

        anomaly    = self.calculate_yield_anomaly(y_regression, hist['mean_yield']) \
                    if y_regression is not None else None
        confidence = self.calculate_confidence(hist['rmse'], hist['mean_yield'])
        risk       = self._risk(
            chi,
            wsi_grain if wsi_grain is not None else 0.5,
            vhi       if vhi       is not None else 0.5,
        ) if chi is not None else None

        return {
        'scientific_indices': {
            'vci':              round(vci, 3)           if vci   is not None else None,
            'tci':              round(tci, 3)           if tci   is not None else None,
            'vhi':              round(vhi * 100, 2)     if vhi   is not None else None,
            'spi':              round(spi * 100, 2)     if spi   is not None else None,
            'ewa_vegetative':   round(ewa_veg, 3)       if ewa_veg   is not None else None,
            'ewa_grain_filling':round(ewa_grain, 3)     if ewa_grain is not None else None,
            'gdd':              round(gdd, 1)           if gdd   is not None else None,
            'csi':              round(csi * 100, 2)     if csi   is not None else None,
            'svs_vegetative':   round(svs_veg, 3)       if veg_idx.get('NDVI') is not None else None,
            'svs_grain_filling':round(svs_grain, 3)     if grain_idx.get('NDVI') is not None else None,
            'chi':              round(chi * 100, 2)     if chi   is not None else None,
            'rsi':              round(rsi, 3)           if rsi   is not None else None,
        },
        'scientific_yield': {
            'simple_model_t_ha':         round(y_simple, 2)      if chi is not None else None,
            'regression_model_t_ha':     round(y_regression, 2)  if spi is not None else None,
            'yield_anomaly_pct':         round(anomaly * 100, 2) if chi is not None else None,
            'prediction_confidence_pct': round(confidence * 100, 1),
        },
        'climate': {
            'total_season_rainfall_mm': round(total_rain, 1) if total_rain > 0 else None,
            'avg_temperature_c':        round(avg_temp, 1)   if avg_temp is not None else None,
            'gdd':                      round(gdd, 1)        if gdd is not None else None,
        },
        'soil': {
            'ph':             soil.get('ph'),
            'organic_carbon': soil.get('organic_carbon'),
            'clay_pct':       soil.get('clay_percent'),
            'sand_pct':       soil.get('sand_percent'),
            'field_capacity': round(soil['field_capacity'], 3) if soil.get('field_capacity') else None,
            'smap_moisture':  round(moisture, 3) if moisture is not None else None,
        },
        'satellite': {
            'ndvi_vegetative':    veg_idx.get('NDVI'),
            'evi_vegetative':     veg_idx.get('EVI'),
            'ndvi_grain_filling': grain_idx.get('NDVI'),
            'evi_grain_filling':  grain_idx.get('EVI'),
            'vh':  None,
            'vv':  None,
            'rsi': None,
            'scene_count':       0,
            'latest_scene_date': None,
        },
        'rainfall_by_stage': {
            k: round(float(v), 1)
            for k, v in rainfall_by_stage.items()
            if v is not None
        },
        'risk_level': risk,
    }


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE 2 — AgrivisionProductionPipeline  (ML + HuggingFace report)
# ─────────────────────────────────────────────────────────────────────────────

class AgrivisionProductionPipeline:
    def __init__(self, ml_model_path: str, hf_token: str, **kwargs):
        self.hf_token = hf_token
        self.use_gee = kwargs.get('use_gee', True)
        
        try:
            # Ensure 'pip install scikit-learn' was run in your terminal
            self.model = joblib.load(ml_model_path)
            print("✓ Optical ML Model loaded successfully")
        except Exception as e:
            print(f"✗ Model Load Error: {e}")
            self.model = None

        self.ml_features_order = [
            'evi_s2_mean', 'ndvi_auc_full', 'ewa_s4_mm', 'mean_daily_gdd', 
            'Rainfall_anomaly_tassel', 'Altitude_m',
            'county_Bungoma', 'county_Elgeyo-Marakwet', 'county_Kericho', 
            'county_Nakuru', 'county_Nandi', 'county_Trans Nzoia', 'county_Uasin Gishu'
        ]

    def calculate_gdd_stages(self, aoi, planting_date):
        T_BASE = 10
        plant_dt = datetime.strptime(planting_date, '%Y-%m-%d')
        default_stages = {
            'mean_daily_gdd': 9.2,
            's2_end': (plant_dt + timedelta(days=70)).strftime('%Y-%m-%d'),
            's3_end': (plant_dt + timedelta(days=110)).strftime('%Y-%m-%d'),
            's4_end': (plant_dt + timedelta(days=160)).strftime('%Y-%m-%d')
        }
        try:
            season_end = (plant_dt + timedelta(days=240)).strftime('%Y-%m-%d')
            era5 = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').filterBounds(aoi).filterDate(planting_date, season_end)
            if era5.size().getInfo() > 0:
                def compute_gdd(img):
                    tmean = img.select('temperature_2m_max').add(img.select('temperature_2m_min')).divide(2).subtract(273.15)
                    return img.addBands(tmean.subtract(T_BASE).max(0).rename('gdd'))
                stats = era5.map(compute_gdd).select('gdd').mean().reduceRegion(ee.Reducer.mean(), aoi, 1000).getInfo()
                mean_gdd = stats.get('gdd') if stats and stats.get('gdd') else 9.2
                return {
                    'mean_daily_gdd': mean_gdd,
                    's2_end': (plant_dt + timedelta(days=int(700/mean_gdd))).strftime('%Y-%m-%d'),
                    's3_end': (plant_dt + timedelta(days=int(1100/mean_gdd))).strftime('%Y-%m-%d'),
                    's4_end': (plant_dt + timedelta(days=int(1600/mean_gdd))).strftime('%Y-%m-%d')
                }
            return default_stages
        except: return default_stages

    def extract_features(self, field_coords, year):
        aoi = ee.Geometry.Polygon([field_coords])
        planting_date = f"{year}-03-15"
        stages = self.calculate_gdd_stages(aoi, planting_date)
        ml_feat = {c: (1.0 if c == 'county_Uasin Gishu' else 0.0) for c in self.ml_features_order[6:]}
        
        try:
            alt = ee.Image('USGS/SRTMGL1_003').reduceRegion(ee.Reducer.mean(), aoi, 30).getInfo().get('elevation', 2100)
            ml_feat['Altitude_m'] = alt if alt else 2100
        except: ml_feat['Altitude_m'] = 2100

        is_extrapolated = False
        try:
            s2_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi)
            def add_evi(img):
                mask = img.select('SCL').eq(4)or(img.select('SCL').eq(5))
                evi = img.expression('2.5 * ((B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1))', 
                                    {'B8': img.select('B8'), 'B4': img.select('B4'), 'B2': img.select('B2')}).rename('EVI')
                return img.addBands(evi).updateMask(mask)
            s2 = s2_col.map(add_evi)
            s3_res = s2.filterDate(stages['s2_end'], stages['s3_end']).select('EVI').mean().reduceRegion(ee.Reducer.mean(), aoi, 10).getInfo()
            s3_evi = s3_res.get('EVI') if s3_res else None
            if s3_evi:
                ml_feat['evi_s2_mean'] = s3_evi
            else:
                is_extrapolated = True
                s2_res = s2.filterDate(planting_date, stages['s2_end']).select('EVI').mean().reduceRegion(ee.Reducer.mean(), aoi, 10).getInfo()
                s2_evi = s2_res.get('EVI') if s2_res and s2_res.get('EVI') else 0.3
                ml_feat['evi_s2_mean'] = s2_evi * 1.50
            auc_res = s2.filterDate(planting_date, stages['s4_end']).select('EVI').mean().reduceRegion(ee.Reducer.mean(), aoi, 10).getInfo()
            ml_feat['ndvi_auc_full'] = (auc_res.get('EVI') if auc_res and auc_res.get('EVI') else 0.4) * 12
        except:
            ml_feat['evi_s2_mean'], ml_feat['ndvi_auc_full'] = 0.45, 4.8

        try:
            chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY').filterBounds(aoi).select('precipitation')
            def get_rain(start, end, default):
                coll = chirps.filterDate(start, end)
                if coll.size().getInfo() == 0: return default
                res = coll.sum().reduceRegion(ee.Reducer.mean(), aoi, 5000).getInfo()
                return res.get('precipitation') if res and res.get('precipitation') is not None else default
            ml_feat['ewa_s4_mm'] = get_rain(stages['s3_end'], stages['s4_end'], 140.0)
            t_rain = get_rain(stages['s2_end'], stages['s3_end'], 120.0)
            ml_feat['Rainfall_anomaly_tassel'] = (t_rain - 125.0) / 30.0
        except:
            ml_feat['ewa_s4_mm'], ml_feat['Rainfall_anomaly_tassel'] = 140.0, 0.0

        ml_feat['mean_daily_gdd'] = stages['mean_daily_gdd']
        return ml_feat, is_extrapolated

    def run(self, year=None, scientific=None, **kwargs):
        if year is None:
            year = datetime.utcnow().year

        field_coords = kwargs.get('coords') or kwargs.get('field_coords')
        ml_feats, extrapolated = self.extract_features(field_coords, year)

        if self.model:
            input_data = pd.DataFrame(
                [[ml_feats[f] for f in self.ml_features_order]],
                columns=self.ml_features_order
            )
            yield_val = float(self.model.predict(input_data)[0])
        else:
            yield_val = 0.0

        # Pass scientific indices into the report generator
        report = self.generate_llm_report(yield_val, ml_feats, extrapolated, scientific=scientific)

        return {
            "predicted_yield_t_ha": round(yield_val, 2),
            "ai_agronomic_report":  report,
            "is_extrapolated":      extrapolated,
            "full_bundle":          ml_feats,
        }
    def generate_llm_report(self, yield_val, feats, extrapolated, scientific=None):
        if not self.hf_token:
            return f"Predicted yield: {yield_val:.2f} t/ha based on ML ensemble model."

        API_URL = "https://router.huggingface.co/v1/chat/completions"
        headers = {"Authorization": f"Bearer {self.hf_token}"}

        # Build context only from real available data
        lines = []
        if scientific:
            idx  = scientific.get('scientific_indices', {})
            soil = scientific.get('soil', {})
            clim = scientific.get('climate', {})

            if idx.get('chi')  is not None: lines.append(f"Crop Health Index: {idx['chi']}%")
            if idx.get('vhi')  is not None: lines.append(f"Vegetation Health: {idx['vhi']}%")
            if idx.get('spi')  is not None: lines.append(f"Soil Productivity: {idx['spi']}%")
            if idx.get('csi')  is not None: lines.append(f"Climate Suitability: {idx['csi']}%")
            if idx.get('gdd')  is not None: lines.append(f"Growing Degree Days: {idx['gdd']}")
            if clim.get('total_season_rainfall_mm') is not None:
                lines.append(f"Season Rainfall: {clim['total_season_rainfall_mm']}mm")
            if clim.get('avg_temperature_c') is not None:
                lines.append(f"Avg Temperature: {clim['avg_temperature_c']}°C")
            if soil.get('ph') is not None:
                lines.append(f"Soil pH: {soil['ph']}")
            if soil.get('organic_carbon') is not None:
                lines.append(f"Organic Carbon: {soil['organic_carbon']}g/kg")
            if feats.get('Altitude_m') is not None:
                lines.append(f"Altitude: {feats['Altitude_m']}m")
            if scientific.get('risk_level'):
                lines.append(f"Risk Level: {scientific['risk_level']}")

        status = "early-season estimate" if extrapolated else "observed data"
        data_block = "\n".join(f"- {l}" for l in lines) if lines else "- Limited data available"

        prompt = (
            f"<|im_start|>system\n"
            f"You are an experienced agronomist advising a smallholder maize farmer "
            f"in western Kenya. Write a clear, practical, encouraging 4-sentence report. "
            f"Sentence 1: yield outlook based on the ML prediction. "
            f"Sentence 2: crop and climate health based on available indices. "
            f"Sentence 3: soil condition and what it means for the crop. "
            f"Sentence 4: one specific actionable recommendation the farmer can act on now. "
            f"Do not mention WSI, water stress index, or SAR. Be concise.\n"
            f"<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Field data ({status}):\n"
            f"- ML Predicted Yield: {yield_val:.2f} t/ha\n"
            f"{data_block}\n"
            f"<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        try:
            # NEW — OpenAI-compatible format for Qwen
            res = requests.post(
            API_URL,
            headers=headers,
            json={
                "model": "Qwen/Qwen2.5-7B-Instruct:together",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a senior agronomist and crop scientist with 20 years of experience "
                            "advising smallholder farmers across western Kenya. "
                            "You write detailed, professional agronomic field reports that are both "
                            "scientifically grounded and accessible to farmers with no formal education. "
                            "Your reports are warm, encouraging, and always end with clear next steps. "
                            "Never mention WSI, water stress index, RSI, or SAR radar indices."
                        )
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Write a detailed professional agronomic report for a smallholder maize farmer "
                            f"in western Kenya based on the following field data. "
                            f"The report must have exactly 6 paragraphs:\n\n"
                            f"Paragraph 1 — YIELD OUTLOOK: Interpret the ML predicted yield of "
                            f"{yield_val:.2f} t/ha. Compare to Kenya national average (1.5 t/ha) "
                            f"and Uasin Gishu average (3.0 t/ha). State whether this is a good, "
                            f"average, or below-average season.\n\n"
                            f"Paragraph 2 — CROP HEALTH: Interpret the crop health and vegetation "
                            f"indices. Explain what they mean for the current crop condition in "
                            f"simple terms.\n\n"
                            f"Paragraph 3 — CLIMATE AND RAINFALL: Interpret the season rainfall and "
                            f"temperature data. Explain how the rainfall compares to typical short "
                            f"rains (400-600mm) and what this means for the crop.\n\n"
                            f"Paragraph 4 — SOIL CONDITION: Interpret the soil pH and organic carbon. "
                            f"Explain what these values mean for nutrient availability and crop growth.\n\n"
                            f"Paragraph 5 — RISK ASSESSMENT: Based on the risk level and available "
                            f"data, explain the main risks facing this crop for the remainder of "
                            f"the season.\n\n"
                            f"Paragraph 6 — RECOMMENDATIONS: Give 3 specific, practical, actionable "
                            f"recommendations the farmer can implement immediately or before the next "
                            f"season. Number them 1, 2, 3.\n\n"
                            f"Field Data ({status}):\n"
                            f"{data_block}\n\n"
                            f"Write the report now. Use clear headings for each paragraph in bold. Then present the report in swahili"
                        )
                    }
                ],
                "max_tokens": 800,
                "temperature": 0.5,
            },
            timeout=60
        )
            res.raise_for_status()
            result = res.json()
            text = result['choices'][0]['message']['content'].strip()
            if text:
                return text

            # Empty response — use structured fallback
            raise ValueError("Empty response from model")

        except Exception as e:
            logger.warning("LLM report failed: %s", e)

            # Honest fallback using only real data
            if scientific:
                idx  = scientific.get('scientific_indices', {})
                clim = scientific.get('climate', {})
                parts = [f"Predicted yield: {yield_val:.2f} t/ha ({status})."]
                if idx.get('chi')  is not None:
                    parts.append(f"Crop Health Index: {idx['chi']}%.")
                if clim.get('total_season_rainfall_mm') is not None:
                    parts.append(f"Season rainfall: {clim['total_season_rainfall_mm']}mm.")
                if scientific.get('risk_level'):
                    parts.append(f"Risk level: {scientific['risk_level']}.")
                return " ".join(parts)

            return f"Predicted yield: {yield_val:.2f} t/ha ({status})."
# ─────────────────────────────────────────────────────────────────────────────
# DJANGO MANAGEMENT COMMAND
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        "Run the combined AgriVision analysis pipeline for planting "
        "FieldActivity records. Processing unit = FieldActivity."
    )

    # ── CLI arguments ─────────────────────────────────────────────────────

    def add_arguments(self, parser):
        parser.add_argument(
            '--activity-id', type=int, default=None,
            # FieldActivity primary key — most precise filter
            help='Analyse a single FieldActivity record by its primary key.'
        )
        parser.add_argument(
            '--field-id', type=int, default=None,
            # Field.id — processes all planting activities for that field
            help='Analyse all planting activities for a given Field pk.'
        )
        parser.add_argument(
            '--county', type=str, default=None,
            # Resolved via FieldActivity → Field → CustomUser.location
            help='Filter by county (matches Field.owner.location, case-insensitive).'
        )
        parser.add_argument(
            '--crop-type', type=str, default=None,
            # Overrides activity.crop.name — useful for bulk re-runs
            help='Override crop type for all activities (maize / wheat / rice).'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Compute results but do NOT write to AnalysisResult.'
        )
        parser.add_argument(
            '--no-gee', action='store_true',
            help='Disable Google Earth Engine and use fallback values.'
        )

    # ── DB helpers ────────────────────────────────────────────────────────

    def _app_label(self) -> str:
        """
        Prefer the configured environment label when it matches an installed app,
        but fall back to the real app label used by this project.
        """
        configured = os.environ.get('DJANGO_APP_LABEL')
        candidates = []
        if configured:
            candidates.append(configured)
        candidates.extend(['base', 'fields'])

        from django.apps import apps
        for label in candidates:
            if label and label in apps.app_configs:
                return label

        return 'base'

    def _get_activities(self, options):
        """
        Return a queryset of FieldActivity rows to process.

        Rules:
        • activity_type = 'planting'          (only planting events drive analysis)
        • completion_status in planned/completed  (skip cancelled)
        • crop FK must not be null             (we need crop parameters)
        • Field must have a geometry           (polygon required for GEE)
        """
        from django.apps import apps
        FieldActivity = apps.get_model(self._app_label(), 'FieldActivity')

        qs = (FieldActivity.objects
              .filter(
                  activity_type='planting',                        # ← FieldActivity.ACTIVITY_TYPES
                  completion_status__in=('planned', 'completed'),  # ← skip 'cancelled'/'in_progress'
                  crop__isnull=False,                              # ← Crop FK must exist
              )
              .select_related(
                  'field',              # Field model
                  'field__owner',       # CustomUser — for .location (county)
                  'crop',               # Crop model — for name, growing_season_days, temps
              )
              .prefetch_related(
                  'field__growth_stages',   # CropGrowthStage reverse relation
                  'field__weather_data',    # WeatherData reverse relation
              ))

        # ── optional CLI filters ──
        if options.get('activity_id'):
            qs = qs.filter(pk=options['activity_id'])

        if options.get('field_id'):
            qs = qs.filter(field__id=options['field_id'])  # ← Field.id (AutoField)

        if options.get('county'):
            # County stored on CustomUser.location, not directly on Field
            qs = qs.filter(field__owner__location__iexact=options['county'])

        return qs

    def _resolve_stages(self, activity) -> Dict[str, List[str]]:
        """
        Build growth-stage windows for this activity.

        Priority order:
        1. CropGrowthStage rows in DB  (field.growth_stages reverse relation)
        2. Derived from activity.date + activity.crop.growing_season_days
        3. Hard-coded defaults for the crop type
        """
        # 1 — try CropGrowthStage rows
        db_stages_qs = (activity.field.growth_stages
                        .filter(crop=activity.crop)
                        .order_by('start_date'))
        stages = stages_from_growth_stage_qs(db_stages_qs)
        if len(stages) >= 3:   # need at least vegetative + flowering + grain_filling
            return stages

        # 2 / 3 — derive from planting date
        planting_str = activity.date.strftime('%Y-%m-%d')  # FieldActivity.date (DateTimeField)
        crop_name    = (activity.crop.name or 'maize').lower()
        total_days   = activity.crop.growing_season_days or None  # Crop.growing_season_days

        return derive_growth_stages(planting_str, crop_name, total_days)

    def _resolve_county(self, activity) -> str:
        """
        County is stored as CustomUser.location (free-text CharField).
        Falls back to 'Unknown' if blank.
        """
        return (activity.field.owner.location or 'Unknown').strip()

    def _save_result(self, activity, combined: Dict, options):
        """
        Persist merged pipeline output to AnalysisResult.

        AnalysisResult is keyed on (field, activity) — unique_together constraint.
        All structured scalars are written to their own columns; the full merged
        dict is also stored in full_bundle for ML / LLM downstream pipelines.

        combined dict key                    → AnalysisResult field
        ─────────────────────────────────────────────────────────────
        scientific_indices.chi               → (in full_bundle)
        scientific_indices.rsi               → (in full_bundle)
        scientific_yield.regression_model_t_ha → (in full_bundle)
        ml_predicted_yield_t_ha              → (in full_bundle)
        climate.total_season_rainfall_mm     → total_rainfall_mm
        climate.gdd                          → cumulative_gdd
        soil.ph                              → soil_ph
        soil.organic_carbon                  → soc_gkg
        sar.VH                               → vh_latest
        sar.VV                               → vv_latest
        sar.RSI                              → (in full_bundle)
        risk_level                           → stress_flags (list)
        """
        if options.get('dry_run'):
            return

        from django.apps import apps
        AnalysisResult = apps.get_model(self._app_label(), 'AnalysisResult')

        climate = combined.get('climate', {})
        soil    = combined.get('soil', {})
        sci_idx = combined.get('scientific_indices', {})
        sar     = combined.get('_sar_raw', {})      # stored internally by analyze_field

        # ── stress_flags: derive from risk level and WSI ──────────────────
        flags = []
        risk  = combined.get('risk_level', '')
        if risk in ('High', 'Very High'):
            flags.append(f'crop_health_{risk.lower().replace(" ", "_")}')
        wsi = sci_idx.get('wsi', 0)
        if wsi > 50:
            flags.append('water_stress')
        if sci_idx.get('vhi', 100) < 40:
            flags.append('vegetation_stress')

        AnalysisResult.objects.update_or_create(
            field=activity.field,       # ← Field FK  (unique_together field 1)
            activity=activity,          # ← FieldActivity FK  (unique_together field 2)
            defaults={
                # ── status ──────────────────────────────────────────────
                'pipeline_status': 'done',
                'error_message':   None,

                # ── Sentinel-2 ──────────────────────────────────────────
                # ndvi_latest / ndre_latest come from grain-filling stage
                # (the most diagnostically significant window)
                'ndvi_latest':      combined.get('_grain_ndvi'),    # set by analyze_field
                'ndre_latest':      None,                           # S2 NDRE not yet in pipeline
                'ndvi_auc':         combined.get('ml_features_used', {}).get('ndvi_auc_full'),
                'ndre_peak':        None,
                'scene_count':      combined.get('_s2_scene_count', 0),
                'latest_scene_date': combined.get('_latest_scene_date'),

                # ── SAR (Sentinel-1) ─────────────────────────────────────
                'vh_latest':        sar.get('VH'),
                'vv_latest':        sar.get('VV'),
                'vh_auc':           None,   # multi-temporal VH AUC not yet computed
                'fused_ndvi_auc':   None,
                'sar_scene_count':  combined.get('_s1_scene_count', 0),
                'gap_fill_count':   0,

                # ── Climate ──────────────────────────────────────────────
                'total_rainfall_mm': climate.get('total_season_rainfall_mm'),
                'cumulative_gdd':    climate.get('gdd'),
                'heat_stress_frac':  None,   # not yet computed

                # ── Soil ─────────────────────────────────────────────────
                # FieldSoilData uses soc_gkg; pipeline returns organic_carbon (same unit g/kg)
                'soc_gkg':   soil.get('organic_carbon'),
                'soil_ph':   soil.get('ph'),

                # ── Advisory ─────────────────────────────────────────────
                'stress_flags': flags,

                # ── Full bundle (all data for ML + LLM pipelines) ────────
                'full_bundle': combined,
            },
        )
    

    def _gee_getinfo(ee_object, timeout_seconds=30):
        """
        Call .getInfo() with a timeout. Raises TimeoutError if GEE doesn't
        respond within timeout_seconds. Prevents background thread from hanging.
        """
        result = [None]
        error  = [None]

        def _target():
            try:
                result[0] = ee_object.getInfo()
            except Exception as e:
                error[0] = e

        t = threading.Thread(target=_target, daemon=True)
        t.start()
        t.join(timeout=timeout_seconds)

        if t.is_alive():
            raise TimeoutError(f"GEE .getInfo() timed out after {timeout_seconds}s")
        if error[0]:
            raise error[0]
        return result[0]
    # ── main entry point ─────────────────────────────────────────────────

    def handle(self, *args, **options):
        use_gee = not options['no_gee']

        # ── config from environment ──────────────────────────────────────
        openweather_key = os.environ.get('OPENWEATHER_API_KEY')
        hf_token        = os.environ.get('HUGGINGFACE_API_TOKEN', '')
        ml_model_path   = os.environ.get(
            'AGRIVISION_ML_MODEL_PATH',
            'agrivision_ULTIMATE_voting_ensemble.pkl',
        )

        # ── initialise both pipelines once (shared across all activities) ─
        self.stdout.write(self.style.MIGRATE_HEADING("Initialising AgriVision pipelines…"))

        analyzer = AgrivisionCompleteAnalyzer(
            openweather_api_key=openweather_key,
            use_gee=use_gee,
        )
        ml_pipeline = AgrivisionProductionPipeline(
            ml_model_path=ml_model_path,
            hf_token=hf_token,
            use_gee=use_gee,
        )

        # ── query FieldActivity (not Field directly) ──────────────────────
        activities = self._get_activities(options)
        total      = activities.count()
        if total == 0:
            self.stdout.write(self.style.WARNING(
                "No qualifying planting activities found. "
                "Check activity_type='planting', crop FK set, and status."
            ))
            return

        self.stdout.write(f"Processing {total} planting activity/activities…\n")

        success_count = 0
        fail_count    = 0

        for activity in activities:
            field = activity.field                  # Field model instance
            # ── county from CustomUser.location ──────────────────────────
            county    = self._resolve_county(activity)
            # ── crop name from Crop FK ────────────────────────────────────
            crop_name = (options.get('crop_type') or activity.crop.name or 'maize').lower()

            self.stdout.write(f"\n{'─'*60}")
            self.stdout.write(
                f"Activity #{activity.pk}  |  Field: {field.name}  |  "
                f"County: {county}  |  Crop: {crop_name}"
            )

            # ── mark as running so the UI can show progress ───────────────
            if not options.get('dry_run'):
                try:
                    from django.apps import apps
                    AR = apps.get_model(self._app_label(), 'AnalysisResult')
                    AR.objects.update_or_create(
                        field=field, activity=activity,
                        defaults={'pipeline_status': 'running', 'error_message': None}
                    )
                except Exception:
                    pass

            try:
                # ── 1. polygon → coordinate ring ─────────────────────────
                coords = polygon_to_coords(field.geometry)   # Field.geometry = PolygonField(srid=4326)
                lons   = [c[0] for c in coords]
                lats   = [c[1] for c in coords]
                lat    = float(np.mean(lats))
                lon    = float(np.mean(lons))

                # ── 2. growth stages ──────────────────────────────────────
                # Uses CropGrowthStage rows if present, else derives from
                # FieldActivity.date + Crop.growing_season_days
                stages = self._resolve_stages(activity)
                self.stdout.write(f"  Stages: { {k: v for k, v in stages.items()} }")

                # ── 3. soil — prefer FieldSoilData, fall back to SoilGrids API ──
                # FieldSoilData is accessed via field.soil_data (OneToOneField
                # reverse accessor defined in FieldSoilData model)
                preloaded_soil = soil_context_from_db(field)
                if preloaded_soil:
                    self.stdout.write("  Soil: loaded from FieldSoilData (DB)")
                else:
                    self.stdout.write("  Soil: FieldSoilData absent — will call SoilGrids API")

                # ── 4. weather — prefer WeatherData rows, fall back to OpenWeather ──
                # WeatherData is accessed via field.weather_data (related_name)
                preloaded_weather = weather_from_db(field)
                if preloaded_weather:
                    self.stdout.write("  Weather: loaded from WeatherData (DB)")
                else:
                    self.stdout.write("  Weather: WeatherData absent — will call OpenWeather API")

                # ── 5. Pipeline 1: 18 scientific indices ──────────────────
                self.stdout.write("  → Running scientific analysis (18 formulas)…")
                scientific = analyzer.analyze_field(
                    coords=coords,
                    crop_type=crop_name,
                    growth_stages=stages,
                    lat=lat,
                    lon=lon,
                    preloaded_soil=preloaded_soil,       # skips SoilGrids if not None
                    preloaded_weather=preloaded_weather, # skips OpenWeather if not None
                )

                # ── 6. Pipeline 2: ML ensemble + HuggingFace report ───────
                self.stdout.write("  → Running ML ensemble + LLM report…")
                ml_result = ml_pipeline.run(
                    coords=coords,
                    county=county,                       # from CustomUser.location
                    growth_stages=stages,
                    soil_context=scientific.get('soil'), # pass computed soil dict
                )

                # ── 7. merge ──────────────────────────────────────────────
                combined = {**scientific, **ml_result}

                # ── 8. print summary ──────────────────────────────────────
                chi  = combined['scientific_indices']['chi']
                risk = combined.get('risk_level', 'N/A')
                y_sc = combined['scientific_yield']['regression_model_t_ha']
                y_ml = combined.get('ml_predicted_yield_t_ha', 'N/A')

                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ CHI={chi}%  |  Risk={risk}  |  "
                    f"Yield(sci)={y_sc} t/ha  |  Yield(ML)={y_ml} t/ha"
                ))

                # ── 9. persist to AnalysisResult ─────────────────────────
                if options.get('dry_run'):
                    self.stdout.write(self.style.WARNING("  [DRY-RUN] not saved."))
                    self.stdout.write(json.dumps(combined, indent=2, default=str)[:800] + " …")
                else:
                    self._save_result(activity, combined, options)
                    self.stdout.write("  ✓ AnalysisResult saved (field={}, activity={}).".format(
                        field.pk, activity.pk))

                success_count += 1

            except Exception as exc:
                fail_count += 1
                self.stderr.write(self.style.ERROR(
                    f"  ✗ Activity #{activity.pk} (Field #{field.pk}) failed: {exc}"
                ))
                logger.debug(traceback.format_exc())

                # ── mark error in DB ──────────────────────────────────────
                if not options.get('dry_run'):
                    try:
                        from django.apps import apps
                        AR = apps.get_model(self._app_label(), 'AnalysisResult')
                        AR.objects.update_or_create(
                            field=field, activity=activity,
                            defaults={
                                'pipeline_status': 'error',
                                'error_message':   str(exc)[:500],
                            }
                        )
                    except Exception:
                        pass

        # ── final summary ─────────────────────────────────────────────────
        self.stdout.write(f"\n{'═'*60}")
        self.stdout.write(self.style.SUCCESS(
            f"Done — {success_count} succeeded, {fail_count} failed."
        ))


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-REFERENCE: pipeline variable  ←→  your models.py field
# ─────────────────────────────────────────────────────────────────────────────
#
# SOURCE DATA
# ───────────────────────────────────────────────────────────────────────────
# Pipeline needs          From model / field
# ─────────────────────── ──────────────────────────────────────────────────
# Field polygon           Field.geometry          (PolygonField srid=4326)
# County / location       CustomUser.location     (via Field.owner FK)
# Crop name               Crop.name               (via FieldActivity.crop FK)
# T_base, T_opt_*         Crop.min_temp / optimal_temp_min / optimal_temp_max
# growing_season_days     Crop.growing_season_days
# Planting date           FieldActivity.date      (activity_type='planting')
# Growth stage windows    CropGrowthStage rows    (field.growth_stages reverse)
# Weather series          WeatherData rows        (field.weather_data reverse)
# Soil properties         FieldSoilData           (field.soil_data OneToOne)
#
# FieldSoilData → pipeline key mapping
# ───────────────────────────────────────────────────────────────────────────
# soc_gkg                 → organic_carbon   (g/kg — identical unit)
# soil_ph                 → ph
# clay_pct                → clay_percent
# sand_pct                → sand_percent
# cec                     → cec
# bulk_density / 1000     → bulk_density     (kg/m³ → g/cm³)
# water_capacity_pf2 / 100→ field_capacity   (% → fraction)
# wilting_point / 100     → wilting_point    (% → fraction)
#
# CropGrowthStage.stage → pipeline stage mapping
# ───────────────────────────────────────────────────────────────────────────
# 'seedling' + 'vegetative'          → 'vegetative'
# 'flowering'                        → 'flowering'
# 'fruiting'                         → 'grain_filling'
# 'maturation' + 'harvest_ready'     → 'maturity'
#
# OUTPUT STORAGE (AnalysisResult)
# ───────────────────────────────────────────────────────────────────────────
# combined key                        AnalysisResult field
# ─────────────────────────────────── ───────────────────────────────────────
# climate.total_season_rainfall_mm  → total_rainfall_mm  (DecimalField)
# climate.gdd                       → cumulative_gdd     (DecimalField)
# soil.ph                           → soil_ph            (DecimalField)
# soil.organic_carbon               → soc_gkg            (DecimalField, g/kg)
# _sar_raw.VH                       → vh_latest          (DecimalField)
# _sar_raw.VV                       → vv_latest          (DecimalField)
# ml_features_used.ndvi_auc_full    → ndvi_auc           (DecimalField)
# _grain_ndvi                       → ndvi_latest        (DecimalField)
# (risk + wsi + vhi thresholds)     → stress_flags       (JSONField list)
# everything                        → full_bundle        (JSONField)
# pipeline_status='done'/'error'    → pipeline_status    (CharField)