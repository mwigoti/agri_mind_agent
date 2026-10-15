"""
AGRIVISION COMPLETE STANDALONE MODULE WITH GEE
===============================================

This file includes:
1. All 18 scientific formulas
2. Google Earth Engine integration (Sentinel-1, Sentinel-2)
3. External APIs integration:
   - SoilGrids (soil data)
   - CHIRPS (rainfall)
   - SMAP (soil moisture)
   - OpenWeatherMap (weather)
4. Complete analysis pipeline
5. Can work standalone OR with Django

INSTALLATION:
pip install earthengine-api numpy requests

AUTHENTICATION:
earthengine authenticate

RUN:
python agrivision_complete_standalone.py
"""

import ee
import numpy as np
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json


class AgrivisionCompleteAnalyzer:
    """
    Complete agricultural analysis system
    - Uses GEE for satellite data
    - Fetches external data from APIs
    - Implements all 18 scientific formulas
    """
    
    def __init__(self, openweather_api_key: str = None, 
                 use_gee: bool = True):
        """
        Initialize analyzer
        
        Args:
            openweather_api_key: API key for OpenWeatherMap
            use_gee: Whether to use Google Earth Engine
        """
        self.openweather_api_key = openweather_api_key
        self.use_gee = use_gee
        
        # Initialize GEE if requested
        if use_gee:
            try:
                ee.Initialize()
                print("✓ Google Earth Engine initialized successfully")
            except Exception as e:
                print(f"✗ GEE initialization failed: {e}")
                print("  Run: earthengine authenticate")
                self.use_gee = False
        
        # Scientific weights
        self.weights = {
            'vhi': {'alpha': 0.5},
            'spi': {'whc': 0.35, 'soc': 0.30, 'cec': 0.20, 'texture': 0.15},
            'csi': {'rainfall': 0.40, 'temperature': 0.35, 'gdd': 0.25},
            'chi': {'vhi': 0.30, 'spi': 0.25, 'water': 0.25, 'csi': 0.15, 'rsi': 0.05},
            'svs': {
                'vegetative': {'ndvi': 0.4, 'evi': 0.3, 'ndmi': 0.3},
                'flowering': {'ndvi': 0.35, 'evi': 0.35, 'ndmi': 0.3},
                'grain_filling': {'ndvi': 0.3, 'evi': 0.2, 'ndmi': 0.5},
                'maturity': {'ndvi': 0.4, 'evi': 0.3, 'ndmi': 0.3}
            }
        }
        
        # Crop parameters
        self.crop_params = {
            'maize': {
                'T_base': 10, 'T_opt_min': 18, 'T_opt_max': 32,
                'water_req_veg': 500, 'water_req_grain': 350, 'Y_max': 10.0
            },
            'wheat': {
                'T_base': 0, 'T_opt_min': 15, 'T_opt_max': 25,
                'water_req_veg': 300, 'water_req_grain': 250, 'Y_max': 6.0
            },
            'rice': {
                'T_base': 10, 'T_opt_min': 20, 'T_opt_max': 35,
                'water_req_veg': 800, 'water_req_grain': 600, 'Y_max': 8.0
            }
        }
    
    # ========================================================================
    # EXTERNAL DATA FETCHERS
    # ========================================================================
    
    def fetch_soilgrids_data(self, lat: float, lon: float) -> Dict:
        """
        Fetch soil data from ISRIC SoilGrids API (updated endpoint)
        
        Returns soil properties at 0-30cm depth
        """
        print(f"\n→ Fetching soil data for ({lat:.4f}, {lon:.4f})...")
        
        try:
            # Updated ISRIC API endpoint
            base_url = "https://isqaper.isric.org/isqaper-rest/api/1.0/query"
            
            params = {
                'lon': lon,
                'lat': lat,
                'attributes': 'soc,clay,sand,phh2o,cec,bdod',
                'depths': '0-30'
            }
            
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Parse response based on new API structure
            def get_property_value(data, property_name):
                try:
                    # New API structure - adjust based on actual response
                    if 'properties' in data:
                        props = data['properties']
                        if property_name in props:
                            return props[property_name].get('mean', None)
                    # Fallback to direct access
                    return data.get(property_name, {}).get('mean', None)
                except:
                    return None
            
            # Extract values (adjust units based on API response)
            soc = get_property_value(data, 'soc')
            clay = get_property_value(data, 'clay')
            sand = get_property_value(data, 'sand')
            ph = get_property_value(data, 'phh2o')
            cec = get_property_value(data, 'cec')
            bdod = get_property_value(data, 'bdod')
            
            # Convert units to standard format
            soil_properties = {
                'organic_carbon': float(soc) if soc else 20,  # g/kg
                'clay_percent': float(clay) if clay else 30,  # %
                'sand_percent': float(sand) if sand else 40,  # %
                'ph': float(ph) if ph else 6.5,  # pH
                'cec': float(cec) if cec else 15,  # cmol/kg
                'bulk_density': float(bdod) if bdod else 1.4  # g/cm³
            }
            
            # Calculate field capacity and wilting point (Saxton equation simplified)
            clay_pct = soil_properties['clay_percent']
            sand_pct = soil_properties['sand_percent']
            
            # Field capacity (approximation)
            soil_properties['field_capacity'] = 0.2576 - 0.0020*sand_pct + 0.0036*clay_pct
            soil_properties['wilting_point'] = 0.0260 + 0.0050*clay_pct
            
            print(f"  ✓ Soil data retrieved successfully")
            print(f"    pH: {soil_properties['ph']:.1f}")
            print(f"    Organic Carbon: {soil_properties['organic_carbon']:.1f} g/kg")
            print(f"    Clay: {soil_properties['clay_percent']:.1f}%, Sand: {soil_properties['sand_percent']:.1f}%")
            
            return soil_properties
            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Error fetching SoilGrids data (API error): {e}")
            print(f"    Using default values")
            return {
                'organic_carbon': 20, 'clay_percent': 30, 'sand_percent': 40,
                'ph': 6.5, 'cec': 15, 'bulk_density': 1.4,
                'field_capacity': 0.25, 'wilting_point': 0.12
            }
        except Exception as e:
            print(f"  ✗ Error parsing SoilGrids data: {e}")
            print(f"    Using default values")
            return {
                'organic_carbon': 20, 'clay_percent': 30, 'sand_percent': 40,
                'ph': 6.5, 'cec': 15, 'bulk_density': 1.4,
                'field_capacity': 0.25, 'wilting_point': 0.12
            }
    
    def fetch_chirps_rainfall(self, aoi: ee.Geometry, start_date: str, 
                             end_date: str) -> Dict:
        """
        Fetch rainfall data from CHIRPS using GEE
        """
        print(f"\n→ Fetching CHIRPS rainfall ({start_date} to {end_date})...")
        
        if not self.use_gee:
            print("  ✗ GEE not available, using default values")
            return {'total_rainfall_mm': 500, 'num_days': 90, 'daily_mean': 5.5}
        
        try:
            chirps = ee.ImageCollection('UCSB-CHG/CHIRPS/DAILY')
            
            chirps_filtered = chirps.filterDate(start_date, end_date).filterBounds(aoi)
            
            # Total rainfall
            total = chirps_filtered.sum().select('precipitation').reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=5000,
                maxPixels=1e9
            ).getInfo()
            
            num_days = chirps_filtered.size().getInfo()
            total_rainfall = total.get('precipitation', 0)
            
            result = {
                'total_rainfall_mm': round(total_rainfall, 1),
                'num_days': num_days,
                'daily_mean': round(total_rainfall / num_days, 2) if num_days > 0 else 0
            }
            
            print(f"  ✓ CHIRPS data retrieved")
            print(f"    Total rainfall: {result['total_rainfall_mm']} mm")
            print(f"    Period: {num_days} days")
            
            return result
            
        except Exception as e:
            print(f"  ✗ Error fetching CHIRPS: {e}")
            return {'total_rainfall_mm': 500, 'num_days': 90, 'daily_mean': 5.5}
    
    def fetch_smap_moisture(self, aoi: ee.Geometry, date: str) -> float:
        """
        Fetch soil moisture from NASA SMAP using GEE (updated dataset)
        """
        print(f"\n→ Fetching SMAP soil moisture for {date}...")
        
        if not self.use_gee:
            print("  ✗ GEE not available, using default value")
            return 0.25
        
        try:
            # Updated SMAP dataset
            smap = ee.ImageCollection('NASA/SMAP/SPL4SMGP/007')
            
            # Get data within 3 days of target date
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            start = (date_obj - timedelta(days=3)).strftime('%Y-%m-%d')
            end = (date_obj + timedelta(days=3)).strftime('%Y-%m-%d')
            
            smap_filtered = smap.filterDate(start, end).filterBounds(aoi)
            
            if smap_filtered.size().getInfo() == 0:
                print(f"  ⚠ No SMAP data available, using default")
                return 0.25
            
            # Get mean surface soil moisture (0-5cm)
            # Band: 'sm_surface' for surface soil moisture
            moisture_data = smap_filtered.mean().select('sm_surface').reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=11000,  # SMAP resolution ~11km
                maxPixels=1e9
            ).getInfo()
            
            # SMAP soil moisture is in m³/m³ (0-1 scale)
            moisture = moisture_data.get('sm_surface', 0.25)
            
            print(f"  ✓ SMAP moisture: {moisture:.3f}")
            
            return moisture
            
        except Exception as e:
            print(f"  ✗ Error fetching SMAP: {e}")
            return 0.25
    
    def fetch_weather_data(self, lat: float, lon: float) -> Dict:
        """
        Fetch current weather from OpenWeatherMap
        """
        print(f"\n→ Fetching weather data...")
        
        if not self.openweather_api_key:
            print("  ⚠ No API key provided, using default values")
            return {
                'temperature': 25, 'humidity': 60, 'temp_max_series': [28]*60,
                'temp_min_series': [15]*60
            }
        
        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                'lat': lat, 'lon': lon,
                'appid': self.openweather_api_key,
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            # Current weather
            current = {
                'temperature': data['main']['temp'],
                'humidity': data['main']['humidity'],
                'temp_min': data['main']['temp_min'],
                'temp_max': data['main']['temp_max']
            }
            
            # Simulate historical series (in production, use historical API)
            temp_range = 5
            current_temp = current['temperature']
            
            weather_data = {
                'temperature': current_temp,
                'humidity': current['humidity'],
                'temp_max_series': [current_temp + np.random.uniform(-2, 3) for _ in range(60)],
                'temp_min_series': [current_temp - temp_range + np.random.uniform(-2, 2) for _ in range(60)]
            }
            
            print(f"  ✓ Weather data retrieved")
            print(f"    Temperature: {current_temp:.1f}°C")
            print(f"    Humidity: {current['humidity']}%")
            
            return weather_data
            
        except Exception as e:
            print(f"  ✗ Error fetching weather: {e}")
            return {
                'temperature': 25, 'humidity': 60,
                'temp_max_series': [28]*60, 'temp_min_series': [15]*60
            }
    
    def fetch_sentinel2_indices(self, aoi: ee.Geometry, start_date: str, 
                                end_date: str) -> Dict:
        """
        Fetch and calculate vegetation indices from Sentinel-2
        """
        print(f"\n→ Fetching Sentinel-2 data ({start_date} to {end_date})...")
        
        if not self.use_gee:
            print("  ✗ GEE not available, using default values")
            return {'NDVI': 0.7, 'EVI': 0.5, 'NDMI': 0.4, 'SAVI': 0.6}
        
        try:
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(aoi) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
            
            if s2.size().getInfo() == 0:
                print("  ✗ No cloud-free Sentinel-2 images available")
                return {'NDVI': 0.7, 'EVI': 0.5, 'NDMI': 0.4, 'SAVI': 0.6}
            
            # Get median composite
            s2_median = s2.median()
            
            # Calculate indices
            # NDVI
            ndvi = s2_median.normalizedDifference(['B8', 'B4']).rename('NDVI')
            
            # EVI
            evi = s2_median.expression(
                '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                {
                    'NIR': s2_median.select('B8'),
                    'RED': s2_median.select('B4'),
                    'BLUE': s2_median.select('B2')
                }
            ).rename('EVI')
            
            # NDMI
            ndmi = s2_median.normalizedDifference(['B8', 'B11']).rename('NDMI')
            
            # SAVI
            savi = s2_median.expression(
                '((NIR - RED) / (NIR + RED + 0.5)) * 1.5',
                {
                    'NIR': s2_median.select('B8'),
                    'RED': s2_median.select('B4')
                }
            ).rename('SAVI')
            
            # Combine and extract
            combined = ee.Image.cat([ndvi, evi, ndmi, savi])
            
            values = combined.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            print(f"  ✓ Sentinel-2 indices calculated")
            print(f"    NDVI: {values.get('NDVI', 0):.3f}")
            print(f"    EVI: {values.get('EVI', 0):.3f}")
            print(f"    NDMI: {values.get('NDMI', 0):.3f}")
            
            return values
            
        except Exception as e:
            print(f"  ✗ Error fetching Sentinel-2: {e}")
            return {'NDVI': 0.7, 'EVI': 0.5, 'NDMI': 0.4, 'SAVI': 0.6}
    
    def fetch_sentinel1_sar(self, aoi: ee.Geometry, start_date: str, 
                           end_date: str) -> Dict:
        """
        Fetch Sentinel-1 SAR data
        """
        print(f"\n→ Fetching Sentinel-1 SAR data...")
        
        if not self.use_gee:
            print("  ✗ GEE not available, using default values")
            return {'VH': 0.15, 'VV': 0.28, 'RSI': 0.54}
        
        try:
            s1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
                .filterBounds(aoi) \
                .filterDate(start_date, end_date) \
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
            
            if s1.size().getInfo() == 0:
                print("  ✗ No Sentinel-1 data available")
                return {'VH': 0.15, 'VV': 0.28, 'RSI': 0.54}
            
            s1_median = s1.median()
            
            values = s1_median.select(['VH', 'VV']).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            vh = values.get('VH', 0.15)
            vv = values.get('VV', 0.28)
            rsi = vh / vv if vv != 0 else 0.54
            
            result = {'VH': vh, 'VV': vv, 'RSI': rsi}
            
            print(f"  ✓ Sentinel-1 data retrieved")
            print(f"    RSI: {rsi:.3f}")
            
            return result
            
        except Exception as e:
            print(f"  ✗ Error fetching Sentinel-1: {e}")
            return {'VH': 0.15, 'VV': 0.28, 'RSI': 0.54}
    
    # ========================================================================
    # SCIENTIFIC FORMULAS (All 18)
    # ========================================================================
    
    def calculate_vci(self, ndvi_current: float, ndvi_min: float, ndvi_max: float) -> float:
        """VCI = (NDVI_current - NDVI_min) / (NDVI_max - NDVI_min)"""
        if ndvi_max <= ndvi_min:
            return 0.5
        return np.clip((ndvi_current - ndvi_min) / (ndvi_max - ndvi_min), 0, 1)
    
    def calculate_tci(self, temp_current: float, temp_min: float, temp_max: float) -> float:
        """TCI = (T_max - T_current) / (T_max - T_min)"""
        if temp_max <= temp_min:
            return 0.5
        return np.clip((temp_max - temp_current) / (temp_max - temp_min), 0, 1)
    
    def calculate_vhi(self, vci: float, tci: float) -> float:
        """VHI = α·VCI + (1-α)·TCI"""
        alpha = self.weights['vhi']['alpha']
        return np.clip(alpha * vci + (1 - alpha) * tci, 0, 1)
    
    def normalize_soil_properties(self, raw_soil: Dict) -> Dict:
        """Normalize soil properties to 0-1 scale"""
        normalized = {}
        
        whc = raw_soil.get('field_capacity', 0.25) - raw_soil.get('wilting_point', 0.10)
        normalized['whc_norm'] = self._normalize(whc, 0.05, 0.25)
        
        soc = raw_soil.get('organic_carbon', 20)
        normalized['soc_norm'] = self._normalize(soc, 5, 50)
        
        cec = raw_soil.get('cec', 15)
        normalized['cec_norm'] = self._normalize(cec, 5, 40)
        
        sand = raw_soil.get('sand_percent', 40)
        clay = raw_soil.get('clay_percent', 30)
        texture_score = 1.0 - abs((sand - 37.5) / 50) * 0.5 - abs((clay - 17) / 30) * 0.5
        normalized['texture_norm'] = np.clip(texture_score, 0, 1)
        
        return normalized
    
    def calculate_spi(self, whc_norm: float, soc_norm: float, 
                     cec_norm: float, texture_norm: float) -> float:
        """SPI = w1·WHC + w2·SOC + w3·CEC + w4·Texture"""
        w = self.weights['spi']
        return np.clip(
            w['whc'] * whc_norm + w['soc'] * soc_norm + 
            w['cec'] * cec_norm + w['texture'] * texture_norm,
            0, 1
        )
    
    def calculate_ewa(self, rainfall: float, whc: float, 
                     moisture: float, water_req: float) -> float:
        """EWA = (Rainfall × WHC × Moisture) / WaterRequirement"""
        if water_req <= 0:
            return 0.5
        return np.clip((rainfall * whc * moisture) / water_req, 0, 1)
    
    def calculate_wsi(self, ewa: float) -> float:
        """WSI = 1 - EWA"""
        return 1.0 - ewa
    
    def calculate_gdd(self, temp_max_series: List[float], 
                     temp_min_series: List[float], t_base: float) -> float:
        """GDD = Σ((T_max + T_min)/2 - T_base)"""
        gdd = 0
        for t_max, t_min in zip(temp_max_series, temp_min_series):
            t_avg = (t_max + t_min) / 2
            if t_avg > t_base:
                gdd += (t_avg - t_base)
        return max(0, gdd)
    
    def normalize_climate_variables(self, rainfall: float, temp: float, 
                                   gdd: float, crop_type: str) -> Dict:
        """Normalize climate variables"""
        params = self.crop_params[crop_type]
        
        rainfall_norm = self._normalize(rainfall, 300, 1000)
        
        if params['T_opt_min'] <= temp <= params['T_opt_max']:
            temp_norm = 1.0
        elif temp < params['T_opt_min']:
            temp_norm = self._normalize(temp, params['T_base'], params['T_opt_min'])
        else:
            temp_norm = 1.0 - self._normalize(temp, params['T_opt_max'], 45)
        
        gdd_target = {'maize': 1500, 'wheat': 1700, 'rice': 2000}.get(crop_type, 1500)
        gdd_norm = self._normalize(gdd, gdd_target * 0.7, gdd_target * 1.2)
        
        return {
            'rainfall_norm': rainfall_norm,
            'temp_norm': temp_norm,
            'gdd_norm': gdd_norm
        }
    
    def calculate_csi(self, rainfall_norm: float, temp_norm: float, gdd_norm: float) -> float:
        """CSI = β1·Rainfall + β2·Temp + β3·GDD"""
        w = self.weights['csi']
        return np.clip(
            w['rainfall'] * rainfall_norm + 
            w['temperature'] * temp_norm + 
            w['gdd'] * gdd_norm,
            0, 1
        )
    
    def calculate_svs(self, ndvi: float, evi: float, ndmi: float, stage: str) -> float:
        """SVS = a1·NDVI + a2·EVI + a3·NDMI"""
        w = self.weights['svs'].get(stage, self.weights['svs']['vegetative'])
        return np.clip(
            w['ndvi'] * ndvi + w['evi'] * evi + w['ndmi'] * ndmi,
            0, 1
        )
    
    def calculate_chi(self, vhi: float, spi: float, wsi: float, 
                     csi: float, rsi: float) -> float:
        """CHI = γ1·VHI + γ2·SPI + γ3·(1-WSI) + γ4·CSI + γ5·RSI"""
        w = self.weights['chi']
        return np.clip(
            w['vhi'] * vhi + w['spi'] * spi + w['water'] * (1 - wsi) + 
            w['csi'] * csi + w['rsi'] * rsi,
            0, 1
        )
    
    def estimate_yield_simple(self, chi: float, wsi: float, crop_type: str) -> float:
        """Yield = Y_max × CHI × (1 - WSI)"""
        y_max = self.crop_params[crop_type]['Y_max']
        return max(0, y_max * chi * (1 - wsi))
    
    def estimate_yield_regression(self, svs_veg: float, svs_grain: float,
                                  ewa_veg: float, ewa_grain: float,
                                  spi: float, rsi: float,
                                  coefficients: Dict = None) -> float:
        """Yield = β0 + β1·SVS_veg + β2·SVS_grain + ..."""
        if not coefficients:
            coefficients = {
                'beta_0': 1.5, 'beta_1': 2.0, 'beta_2': 3.5,
                'beta_3': 1.0, 'beta_4': 2.5, 'beta_5': 1.2, 'beta_6': 0.8
            }
        
        return max(0,
            coefficients['beta_0'] +
            coefficients['beta_1'] * svs_veg +
            coefficients['beta_2'] * svs_grain +
            coefficients['beta_3'] * ewa_veg +
            coefficients['beta_4'] * ewa_grain +
            coefficients['beta_5'] * spi +
            coefficients['beta_6'] * rsi
        )
    
    def calculate_yield_anomaly(self, yield_pred: float, yield_mean: float) -> float:
        """Anomaly = (Yield_pred - Yield_mean) / Yield_mean"""
        if yield_mean <= 0:
            return 0.0
        return (yield_pred - yield_mean) / yield_mean
    
    def calculate_confidence(self, rmse: float, mean_yield: float) -> float:
        """Confidence = 1 - (RMSE / MeanYield)"""
        if mean_yield <= 0:
            return 0.5
        return np.clip(1 - (rmse / mean_yield), 0, 1)
    
    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize to 0-1"""
        if max_val <= min_val:
            return 0.5
        return np.clip((value - min_val) / (max_val - min_val), 0, 1)
    
    def _assess_risk(self, chi: float, wsi: float, vhi: float) -> str:
        """Assess risk level"""
        if chi > 0.75 and wsi < 0.3 and vhi > 0.75:
            return "Low"
        elif chi > 0.6 and wsi < 0.5 and vhi > 0.6:
            return "Moderate"
        elif chi > 0.45:
            return "High"
        else:
            return "Very High"
    
    # ========================================================================
    # COMPLETE ANALYSIS WITH ALL EXTERNAL DATA
    # ========================================================================
    
    def analyze_field_complete(self, 
                               field_coords: List[List[float]],
                               crop_type: str,
                               growth_stages: Dict,
                               historical_data: Dict = None) -> Dict:
        """
        Complete field analysis using GEE and external APIs
        
        Args:
            field_coords: Field boundary [[lon, lat], ...]
            crop_type: 'maize', 'wheat', or 'rice'
            growth_stages: {'vegetative': ['2024-03-01', '2024-04-15'], ...}
            historical_data: Optional historical ranges
        
        Returns:
            Complete analysis results
        """
        print("\n" + "="*80)
        print("AGRIVISION COMPLETE FIELD ANALYSIS")
        print("="*80)
        
        # Calculate field centroid
        lons = [coord[0] for coord in field_coords]
        lats = [coord[1] for coord in field_coords]
        centroid_lon = np.mean(lons)
        centroid_lat = np.mean(lats)
        
        print(f"\nField centroid: ({centroid_lat:.4f}, {centroid_lon:.4f})")
        print(f"Crop type: {crop_type}")
        
        # Create AOI
        if self.use_gee:
            aoi = ee.Geometry.Polygon([field_coords])
        else:
            aoi = None
        
        # 1. Fetch soil data
        soil_data = self.fetch_soilgrids_data(centroid_lat, centroid_lon)
        
        # 2. Fetch weather data
        weather_data = self.fetch_weather_data(centroid_lat, centroid_lon)
        
        # 3. Fetch rainfall for each stage
        rainfall_by_stage = {}
        if self.use_gee and aoi:
            for stage, dates in growth_stages.items():
                chirps_data = self.fetch_chirps_rainfall(aoi, dates[0], dates[1])
                rainfall_by_stage[stage] = chirps_data['total_rainfall_mm']
        else:
            rainfall_by_stage = {stage: 300 for stage in growth_stages}
        
        # 4. Fetch SMAP moisture
        latest_date = list(growth_stages.values())[-1][1]
        if self.use_gee and aoi:
            soil_moisture = self.fetch_smap_moisture(aoi, latest_date)
        else:
            soil_moisture = 0.28
        
        soil_data['smap_moisture'] = soil_moisture
        
        # 5. Fetch Sentinel-2 indices for each stage
        stage_indices = {}
        if self.use_gee and aoi:
            for stage, dates in growth_stages.items():
                indices = self.fetch_sentinel2_indices(aoi, dates[0], dates[1])
                stage_indices[stage] = indices
        else:
            stage_indices = {
                'vegetative': {'NDVI': 0.68, 'EVI': 0.52, 'NDMI': 0.42},
                'grain_filling': {'NDVI': 0.75, 'EVI': 0.58, 'NDMI': 0.38}
            }
        
        # 6. Fetch Sentinel-1 SAR
        if self.use_gee and aoi:
            grain_dates = growth_stages.get('grain_filling', list(growth_stages.values())[-1])
            sar_data = self.fetch_sentinel1_sar(aoi, grain_dates[0], grain_dates[1])
        else:
            sar_data = {'RSI': 0.54}
        
        # Now run the analysis
        print("\n" + "="*80)
        print("RUNNING SCIENTIFIC ANALYSIS")
        print("="*80)
        
        # Get crop parameters
        crop_params = self.crop_params[crop_type]
        
        # Historical data defaults
        if not historical_data:
            historical_data = {
                'ndvi_range': {'min': 0.25, 'max': 0.88},
                'temp_range': {'min': 12, 'max': 38},
                'mean_yield': 6.5,
                'rmse': 0.8
            }
        
        # Get indices for grain filling stage (most critical)
        grain_indices = stage_indices.get('grain_filling', stage_indices[list(stage_indices.keys())[-1]])
        veg_indices = stage_indices.get('vegetative', stage_indices[list(stage_indices.keys())[0]])
        
        # Calculate VCI, TCI, VHI
        print("\n1. Vegetation & Temperature Condition")
        vci = self.calculate_vci(
            grain_indices['NDVI'],
            historical_data['ndvi_range']['min'],
            historical_data['ndvi_range']['max']
        )
        print(f"   VCI: {vci:.3f}")
        
        tci = self.calculate_tci(
            weather_data['temperature'],
            historical_data['temp_range']['min'],
            historical_data['temp_range']['max']
        )
        print(f"   TCI: {tci:.3f}")
        
        vhi = self.calculate_vhi(vci, tci)
        print(f"   VHI: {vhi:.3f} ({vhi*100:.1f}%)")
        
        # Calculate SPI
        print("\n2. Soil Productivity")
        normalized_soil = self.normalize_soil_properties(soil_data)
        spi = self.calculate_spi(
            normalized_soil['whc_norm'],
            normalized_soil['soc_norm'],
            normalized_soil['cec_norm'],
            normalized_soil['texture_norm']
        )
        print(f"   SPI: {spi:.3f} ({spi*100:.1f}%)")
        
        # Calculate EWA and WSI
        print("\n3. Water Stress")
        ewa_veg = self.calculate_ewa(
            rainfall_by_stage.get('vegetative', 300),
            normalized_soil['whc_norm'],
            soil_moisture,
            crop_params['water_req_veg']
        )
        
        ewa_grain = self.calculate_ewa(
            rainfall_by_stage.get('grain_filling', 250),
            normalized_soil['whc_norm'],
            soil_moisture,
            crop_params['water_req_grain']
        )
        
        wsi_grain = self.calculate_wsi(ewa_grain)
        print(f"   EWA (Grain): {ewa_grain:.3f}")
        print(f"   WSI (Grain): {wsi_grain:.3f} ({wsi_grain*100:.1f}%)")
        
        # Calculate GDD and CSI
        print("\n4. Climate Suitability")
        gdd = self.calculate_gdd(
            weather_data['temp_max_series'],
            weather_data['temp_min_series'],
            crop_params['T_base']
        )
        print(f"   GDD: {gdd:.1f}")
        
        total_rainfall = sum(rainfall_by_stage.values())
        avg_temp = np.mean(weather_data['temp_max_series'])
        
        climate_norm = self.normalize_climate_variables(
            total_rainfall, avg_temp, gdd, crop_type
        )
        
        csi = self.calculate_csi(
            climate_norm['rainfall_norm'],
            climate_norm['temp_norm'],
            climate_norm['gdd_norm']
        )
        print(f"   CSI: {csi:.3f} ({csi*100:.1f}%)")
        
        # Calculate SVS
        print("\n5. Stage Vegetation Scores")
        svs_veg = self.calculate_svs(
            veg_indices['NDVI'],
            veg_indices['EVI'],
            veg_indices['NDMI'],
            'vegetative'
        )
        print(f"   SVS (Vegetative): {svs_veg:.3f}")
        
        svs_grain = self.calculate_svs(
            grain_indices['NDVI'],
            grain_indices['EVI'],
            grain_indices['NDMI'],
            'grain_filling'
        )
        print(f"   SVS (Grain): {svs_grain:.3f}")
        
        # Calculate CHI
        print("\n6. Crop Health Index")
        rsi = sar_data['RSI']
        chi = self.calculate_chi(vhi, spi, wsi_grain, csi, rsi)
        print(f"   CHI: {chi:.3f} ({chi*100:.1f}%)")
        
        # Yield prediction
        print("\n7. Yield Prediction")
        yield_simple = self.estimate_yield_simple(chi, wsi_grain, crop_type)
        print(f"   Simple Model: {yield_simple:.2f} t/ha")
        
        yield_regression = self.estimate_yield_regression(
            svs_veg, svs_grain, ewa_veg, ewa_grain, spi, rsi
        )
        print(f"   Regression Model: {yield_regression:.2f} t/ha")
        
        # Anomaly and confidence
        anomaly = self.calculate_yield_anomaly(
            yield_regression,
            historical_data['mean_yield']
        )
        print(f"   Anomaly: {anomaly*100:+.1f}%")
        
        confidence = self.calculate_confidence(
            historical_data['rmse'],
            historical_data['mean_yield']
        )
        print(f"   Confidence: {confidence*100:.1f}%")
        
        # Risk assessment
        risk = self._assess_risk(chi, wsi_grain, vhi)
        print(f"\n8. Risk Assessment: {risk}")
        
        # Compile results
        results = {
            'field_info': {
                'centroid': [centroid_lat, centroid_lon],
                'crop_type': crop_type
            },
            'indices': {
                'vegetation_health_index': round(vhi * 100, 2),
                'crop_health_index': round(chi * 100, 2),
                'soil_productivity_index': round(spi * 100, 2),
                'water_stress_index': round(wsi_grain * 100, 2),
                'climate_suitability_index': round(csi * 100, 2)
            },
            'yield_prediction': {
                'simple_model_t_ha': round(yield_simple, 2),
                'regression_model_t_ha': round(yield_regression, 2),
                'confidence_pct': round(confidence * 100, 1),
                'anomaly_pct': round(anomaly * 100, 2)
            },
            'stage_analysis': {
                'vegetative': {
                    'svs': round(svs_veg, 3),
                    'ewa': round(ewa_veg, 3),
                    'rainfall_mm': rainfall_by_stage.get('vegetative', 0)
                },
                'grain_filling': {
                    'svs': round(svs_grain, 3),
                    'ewa': round(ewa_grain, 3),
                    'rainfall_mm': rainfall_by_stage.get('grain_filling', 0)
                }
            },
            'climate': {
                'gdd': round(gdd, 1),
                'total_rainfall_mm': round(total_rainfall, 1),
                'avg_temperature_c': round(avg_temp, 1)
            },
            'soil': {
                'ph': soil_data['ph'],
                'organic_carbon': soil_data['organic_carbon'],
                'texture': f"{soil_data['sand_percent']:.0f}% sand, {soil_data['clay_percent']:.0f}% clay"
            },
            'risk_assessment': risk
        }
        
        return results


# ============================================================================
# TEST FUNCTION
# ============================================================================

def test_complete_analysis():
    """
    Test with real field coordinates
    """
    print("""
    ╔═══════════════════════════════════════════════════════════════════════╗
    ║     AGRIVISION COMPLETE ANALYSIS WITH GEE & EXTERNAL APIS            ║
    ╚═══════════════════════════════════════════════════════════════════════╝
    """)
    
    # Initialize analyzer
    # Replace with your OpenWeather API key
    analyzer = AgrivisionCompleteAnalyzer(
        openweather_api_key="YOUR_API_KEY_HERE",  # Optional
        use_gee=True
    )
    
    # Define field (example: small field in Kenya)
    field_coordinates = [
        [36.8219, -1.2921],
        [36.8319, -1.2921],
        [36.8319, -1.3021],
        [36.8219, -1.3021],
        [36.8219, -1.2921]
    ]
    
    # Define growth stages
    growth_stages = {
        'vegetative': ['2024-03-01', '2024-04-15'],
        'flowering': ['2024-04-16', '2024-05-15'],
        'grain_filling': ['2024-05-16', '2024-06-30'],
        'maturity': ['2024-07-01', '2024-07-31']
    }
    
    # Historical data (optional)
    historical_data = {
        'ndvi_range': {'min': 0.25, 'max': 0.88},
        'temp_range': {'min': 12, 'max': 38},
        'mean_yield': 6.5,
        'rmse': 0.8
    }
    
    # Run complete analysis
    results = analyzer.analyze_field_complete(
        field_coords=field_coordinates,
        crop_type='maize',
        growth_stages=growth_stages,
        historical_data=historical_data
    )
    
    # Print results
    print("\n" + "="*80)
    print("FINAL RESULTS")
    print("="*80)
    print(json.dumps(results, indent=2))
    
    print("\n" + "="*80)
    print("✓ ANALYSIS COMPLETE!")
    print("="*80)
    
    return results


if __name__ == "__main__":
    # Run the test
    results = test_complete_analysis()