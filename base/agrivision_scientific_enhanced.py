"""
Agrivision - Enhanced Scientific Module
Implements BSc-level formulas for agricultural analysis
Integrates with Google Earth Engine for satellite data
"""

import ee
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json


class ScientificAgrivisionAnalyzer:
    """
    Enhanced agricultural analysis with scientific formulas
    Based on peer-reviewed indices and validated models
    """
    
    def __init__(self, service_account_path: str = None):
        """Initialize GEE and set up scientific parameters"""
        try:
            if service_account_path:
                from django.conf import settings
                credentials = ee.ServiceAccountCredentials(
                    email=settings.GEE_SERVICE_ACCOUNT,
                    key_file=service_account_path
                )
                ee.Initialize(credentials)
            else:
                ee.Initialize()
        except Exception as e:
            print(f"Error initializing Earth Engine: {e}")
            raise
        
        # Scientific calibration weights (adjust based on validation data)
        self.weights = {
            'vhi': {'alpha': 0.5},  # VHI = α*VCI + (1-α)*TCI
            'spi': {  # Soil Productivity Index
                'whc': 0.35,      # Water holding capacity
                'soc': 0.30,      # Soil organic carbon
                'cec': 0.20,      # Cation exchange capacity
                'texture': 0.15   # Texture index
            },
            'csi': {  # Climate Suitability Index
                'rainfall': 0.40,
                'temperature': 0.35,
                'gdd': 0.25
            },
            'chi': {  # Crop Health Index
                'vhi': 0.30,      # Vegetation Health
                'spi': 0.25,      # Soil Productivity
                'water': 0.25,    # Water availability (1-WSI)
                'csi': 0.15,      # Climate Suitability
                'rsi': 0.05       # Radar Structural Index
            },
            'svs': {  # Stage-based Vegetation Score
                'vegetative': {'ndvi': 0.4, 'evi': 0.3, 'ndmi': 0.3},
                'flowering': {'ndvi': 0.35, 'evi': 0.35, 'ndmi': 0.3},
                'grain_filling': {'ndvi': 0.3, 'evi': 0.2, 'ndmi': 0.5},
                'maturity': {'ndvi': 0.4, 'evi': 0.3, 'ndmi': 0.3}
            }
        }
        
        # Crop-specific parameters
        self.crop_params = {
            'maize': {
                'T_base': 10,      # Base temperature for GDD (°C)
                'T_opt_min': 18,   # Optimal temp range min
                'T_opt_max': 32,   # Optimal temp range max
                'water_req_veg': 500,    # mm per season
                'water_req_grain': 350,  # mm per season
                'Y_max': 10.0      # Maximum potential yield (t/ha)
            },
            'wheat': {
                'T_base': 0,
                'T_opt_min': 15,
                'T_opt_max': 25,
                'water_req_veg': 300,
                'water_req_grain': 250,
                'Y_max': 6.0
            },
            'rice': {
                'T_base': 10,
                'T_opt_min': 20,
                'T_opt_max': 35,
                'water_req_veg': 800,
                'water_req_grain': 600,
                'Y_max': 8.0
            }
        }
    
    # ==============================================
    # 1. BASIC VEGETATION INDICES (Satellite Level)
    # ==============================================
    
    def calculate_basic_indices(self, image: ee.Image) -> ee.Image:
        """
        Calculate fundamental vegetation indices
        Formula: NDVI = (NIR - Red) / (NIR + Red)
        Formula: EVI = 2.5 * (NIR - Red) / (NIR + 6*Red - 7.5*Blue + 1)
        Formula: NDMI = (NIR - SWIR) / (NIR + SWIR)
        """
        # NDVI - Normalized Difference Vegetation Index
        ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
        
        # EVI - Enhanced Vegetation Index
        evi = image.expression(
            '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
            {
                'NIR': image.select('B8'),
                'RED': image.select('B4'),
                'BLUE': image.select('B2')
            }
        ).rename('EVI')
        
        # NDMI - Normalized Difference Moisture Index
        ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
        
        # SAVI - Soil Adjusted Vegetation Index (L=0.5)
        savi = image.expression(
            '((NIR - RED) / (NIR + RED + 0.5)) * 1.5',
            {
                'NIR': image.select('B8'),
                'RED': image.select('B4')
            }
        ).rename('SAVI')
        
        # GNDVI - Green NDVI
        gndvi = image.normalizedDifference(['B8', 'B3']).rename('GNDVI')
        
        # NDRE - Normalized Difference Red Edge (for nitrogen)
        ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
        
        return image.addBands([ndvi, evi, ndmi, savi, gndvi, ndre])
    
    # ==============================================
    # 2. VEGETATION CONDITION INDEX (VCI)
    # ==============================================
    
    def calculate_vci(self, current_ndvi: float, ndvi_min: float, 
                     ndvi_max: float) -> float:
        """
        Formula: VCI = (NDVI_current - NDVI_min) / (NDVI_max - NDVI_min)
        Range: 0-1
        """
        if ndvi_max <= ndvi_min:
            return 0.5  # Default if no historical range
        
        vci = (current_ndvi - ndvi_min) / (ndvi_max - ndvi_min)
        return np.clip(vci, 0, 1)
    
    # ==============================================
    # 3. TEMPERATURE CONDITION INDEX (TCI)
    # ==============================================
    
    def calculate_tci(self, current_temp: float, temp_min: float, 
                     temp_max: float) -> float:
        """
        Formula: TCI = (T_max - T_current) / (T_max - T_min)
        Range: 0-1 (inverted so higher is better)
        """
        if temp_max <= temp_min:
            return 0.5
        
        tci = (temp_max - current_temp) / (temp_max - temp_min)
        return np.clip(tci, 0, 1)
    
    # ==============================================
    # 4. VEGETATION HEALTH INDEX (VHI)
    # ==============================================
    
    def calculate_vhi(self, vci: float, tci: float) -> float:
        """
        Formula: VHI = α·VCI + (1-α)·TCI
        Typically α = 0.5
        """
        alpha = self.weights['vhi']['alpha']
        vhi = alpha * vci + (1 - alpha) * tci
        return np.clip(vhi, 0, 1)
    
    # ==============================================
    # 5. SOIL PRODUCTIVITY INDEX (SPI)
    # ==============================================
    
    def calculate_spi(self, soil_data: Dict) -> float:
        """
        Formula: SPI = w1·WHC + w2·SOC + w3·CEC + w4·TextureIndex
        Where: w1 + w2 + w3 + w4 = 1
        
        Requires soil_data with normalized values (0-1):
        - whc: Water holding capacity
        - soc: Soil organic carbon
        - cec: Cation exchange capacity
        - texture: Texture index
        """
        weights = self.weights['spi']
        
        # Get normalized soil properties (0-1 scale)
        whc = soil_data.get('whc_norm', 0.5)
        soc = soil_data.get('soc_norm', 0.5)
        cec = soil_data.get('cec_norm', 0.5)
        texture = soil_data.get('texture_norm', 0.5)
        
        spi = (
            weights['whc'] * whc +
            weights['soc'] * soc +
            weights['cec'] * cec +
            weights['texture'] * texture
        )
        
        return np.clip(spi, 0, 1)
    
    def normalize_soil_properties(self, raw_soil_data: Dict) -> Dict:
        """
        Convert raw soil data to normalized 0-1 scale
        Based on typical ranges for agricultural soils
        """
        normalized = {}
        
        # Water holding capacity (field capacity - wilting point)
        # Typical range: 0.05 - 0.35 (cm³/cm³)
        whc = raw_soil_data.get('field_capacity', 0.25) - raw_soil_data.get('wilting_point', 0.10)
        normalized['whc_norm'] = self._normalize(whc, 0.05, 0.25)
        
        # Soil organic carbon (g/kg)
        # Typical range: 5 - 50 g/kg
        soc = raw_soil_data.get('organic_carbon', 20)
        normalized['soc_norm'] = self._normalize(soc, 5, 50)
        
        # Cation exchange capacity (cmol/kg)
        # Typical range: 5 - 40 cmol/kg
        cec = raw_soil_data.get('cec', 15)
        normalized['cec_norm'] = self._normalize(cec, 5, 40)
        
        # Texture index (0=heavy clay, 1=light sand, 0.5=loam optimal)
        # Convert to favorability (loam = 1.0)
        sand = raw_soil_data.get('sand_percent', 40)
        clay = raw_soil_data.get('clay_percent', 30)
        # Loam range: 23-52% sand, 7-27% clay
        texture_score = 1.0 - abs((sand - 37.5) / 50) * 0.5 - abs((clay - 17) / 30) * 0.5
        normalized['texture_norm'] = np.clip(texture_score, 0, 1)
        
        return normalized
    
    # ==============================================
    # 6. EFFECTIVE WATER AVAILABILITY (EWA)
    # ==============================================
    
    def calculate_ewa(self, rainfall_stage: float, whc: float, 
                     smap_moisture: float, crop_water_req: float) -> float:
        """
        Formula: EWA = (Rainfall_stage × WHC × SMAP_moisture) / CropWaterRequirement
        Normalized to 0-1
        """
        ewa = (rainfall_stage * whc * smap_moisture) / max(crop_water_req, 1)
        return np.clip(ewa, 0, 1)
    
    # ==============================================
    # 7. WATER STRESS INDEX (WSI)
    # ==============================================
    
    def calculate_wsi(self, ewa: float) -> float:
        """
        Formula: WSI = 1 - EWA
        Higher WSI = more water stress
        """
        return 1.0 - ewa
    
    # ==============================================
    # 8. GROWING DEGREE DAYS (GDD)
    # ==============================================
    
    def calculate_gdd(self, temp_max_series: List[float], 
                     temp_min_series: List[float], 
                     t_base: float) -> float:
        """
        Formula: GDD = Σ((T_max + T_min)/2 - T_base)
        Only count days where average temp > T_base
        """
        gdd_total = 0
        for t_max, t_min in zip(temp_max_series, temp_min_series):
            t_avg = (t_max + t_min) / 2
            if t_avg > t_base:
                gdd_total += (t_avg - t_base)
        
        return max(0, gdd_total)
    
    # ==============================================
    # 9. CLIMATE SUITABILITY INDEX (CSI)
    # ==============================================
    
    def calculate_csi(self, rainfall_norm: float, temp_norm: float, 
                     gdd_norm: float) -> float:
        """
        Formula: CSI = β1·Rainfall_norm + β2·Temp_norm + β3·GDD_norm
        Where: β1 + β2 + β3 = 1
        """
        weights = self.weights['csi']
        
        csi = (
            weights['rainfall'] * rainfall_norm +
            weights['temperature'] * temp_norm +
            weights['gdd'] * gdd_norm
        )
        
        return np.clip(csi, 0, 1)
    
    def normalize_climate_variables(self, rainfall_mm: float, 
                                   avg_temp: float, gdd: float, 
                                   crop_type: str = 'maize') -> Dict:
        """
        Normalize climate variables to 0-1 scale based on crop requirements
        """
        params = self.crop_params.get(crop_type, self.crop_params['maize'])
        
        # Rainfall normalization (500-1000mm optimal for most crops)
        rainfall_norm = self._normalize(rainfall_mm, 300, 1000)
        
        # Temperature normalization (optimal range)
        if params['T_opt_min'] <= avg_temp <= params['T_opt_max']:
            temp_norm = 1.0
        else:
            # Decreases outside optimal range
            if avg_temp < params['T_opt_min']:
                temp_norm = self._normalize(avg_temp, params['T_base'], params['T_opt_min'])
            else:
                temp_norm = 1.0 - self._normalize(avg_temp, params['T_opt_max'], 45)
        
        # GDD normalization (crop-specific requirements)
        # Maize: ~1200-1800 GDD, Wheat: ~1400-2000 GDD
        gdd_optimal = {'maize': 1500, 'wheat': 1700, 'rice': 2000}
        gdd_target = gdd_optimal.get(crop_type, 1500)
        gdd_norm = self._normalize(gdd, gdd_target * 0.7, gdd_target * 1.2)
        
        return {
            'rainfall_norm': rainfall_norm,
            'temp_norm': temp_norm,
            'gdd_norm': gdd_norm
        }
    
    # ==============================================
    # 10. RADAR STRUCTURAL INDEX (RSI)
    # ==============================================
    
    def calculate_rsi(self, image: ee.Image) -> ee.Image:
        """
        Formula: RSI = VH / VV
        Represents canopy structure and biomass density
        """
        vv = image.select('VV')
        vh = image.select('VH')
        
        rsi = vh.divide(vv).rename('RSI')
        return image.addBands(rsi)
    
    def get_stage_rsi(self, rsi_values: List[float]) -> float:
        """
        Formula: RSI_stage = mean(VH/VV) for the growth stage
        """
        if not rsi_values:
            return 0.5
        return np.mean(rsi_values)
    
    # ==============================================
    # 11. STAGE-BASED VEGETATION SCORE (SVS)
    # ==============================================
    
    def calculate_svs(self, ndvi_mean: float, evi_mean: float, 
                     ndmi_mean: float, growth_stage: str) -> float:
        """
        Formula: SVS_stage = a1·NDVI_mean + a2·EVI_mean + a3·NDMI_mean
        Weights depend on growth stage
        """
        stage_key = growth_stage.lower().replace(' ', '_')
        weights = self.weights['svs'].get(stage_key, self.weights['svs']['vegetative'])
        
        svs = (
            weights['ndvi'] * ndvi_mean +
            weights['evi'] * evi_mean +
            weights['ndmi'] * ndmi_mean
        )
        
        return np.clip(svs, 0, 1)
    
    # ==============================================
    # 12. FINAL CROP HEALTH INDEX (CHI)
    # ==============================================
    
    def calculate_chi(self, vhi: float, spi: float, wsi: float, 
                     csi: float, rsi: float) -> float:
        """
        Formula: CHI = γ1·VHI + γ2·SPI + γ3·(1-WSI) + γ4·CSI + γ5·RSI
        Where: γ1 + γ2 + γ3 + γ4 + γ5 = 1
        """
        weights = self.weights['chi']
        
        chi = (
            weights['vhi'] * vhi +
            weights['spi'] * spi +
            weights['water'] * (1 - wsi) +
            weights['csi'] * csi +
            weights['rsi'] * rsi
        )
        
        return np.clip(chi, 0, 1)
    
    # ==============================================
    # 13. YIELD ESTIMATION - METHOD 1 (Simple)
    # ==============================================
    
    def estimate_yield_simple(self, chi: float, wsi_grain: float, 
                             crop_type: str = 'maize') -> float:
        """
        Formula: Yield = Y_max × CHI × AdjustmentFactor
        Where: AdjustmentFactor = 1 - WSI_grain
        """
        y_max = self.crop_params.get(crop_type, {}).get('Y_max', 5.0)
        adjustment_factor = 1 - wsi_grain
        
        yield_predicted = y_max * chi * adjustment_factor
        return max(0, yield_predicted)
    
    # ==============================================
    # 14. YIELD ESTIMATION - METHOD 2 (Regression)
    # ==============================================
    
    def estimate_yield_regression(self, svs_veg: float, svs_grain: float,
                                  ewa_veg: float, ewa_grain: float,
                                  spi: float, rsi_grain: float,
                                  coefficients: Dict = None) -> float:
        """
        Formula: Yield = β0 + β1·SVS_veg + β2·SVS_grain + β3·EWA_veg + 
                        β4·EWA_grain + β5·SPI + β6·RSI_grain + ε
        
        This is scientifically stronger and should be calibrated with field data
        """
        # Default coefficients (MUST BE CALIBRATED with real yield data)
        if coefficients is None:
            coefficients = {
                'beta_0': 1.5,      # Intercept
                'beta_1': 2.0,      # SVS vegetative stage
                'beta_2': 3.5,      # SVS grain filling stage (more critical)
                'beta_3': 1.0,      # EWA vegetative
                'beta_4': 2.5,      # EWA grain filling (critical period)
                'beta_5': 1.2,      # Soil productivity
                'beta_6': 0.8       # Radar structural index
            }
        
        yield_predicted = (
            coefficients['beta_0'] +
            coefficients['beta_1'] * svs_veg +
            coefficients['beta_2'] * svs_grain +
            coefficients['beta_3'] * ewa_veg +
            coefficients['beta_4'] * ewa_grain +
            coefficients['beta_5'] * spi +
            coefficients['beta_6'] * rsi_grain
        )
        
        return max(0, yield_predicted)
    
    # ==============================================
    # 15. YIELD ANOMALY
    # ==============================================
    
    def calculate_yield_anomaly(self, yield_predicted: float, 
                               yield_historical_mean: float) -> float:
        """
        Formula: Yield_anomaly = (Yield_predicted - Yield_historical_mean) / Yield_historical_mean
        """
        if yield_historical_mean <= 0:
            return 0.0
        
        anomaly = (yield_predicted - yield_historical_mean) / yield_historical_mean
        return anomaly
    
    # ==============================================
    # 16. CONFIDENCE SCORE
    # ==============================================
    
    def calculate_confidence(self, rmse: float, mean_yield: float) -> float:
        """
        Formula: Confidence = 1 - (RMSE / MeanYield)
        Range: 0-1
        
        RMSE should be from model validation on historical data
        """
        if mean_yield <= 0:
            return 0.5
        
        confidence = 1 - (rmse / mean_yield)
        return np.clip(confidence, 0, 1)
    
    # ==============================================
    # HELPER FUNCTIONS
    # ==============================================
    
    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize value to 0-1 range"""
        if max_val <= min_val:
            return 0.5
        normalized = (value - min_val) / (max_val - min_val)
        return np.clip(normalized, 0, 1)
    
    # ==============================================
    # COMPLETE ANALYSIS PIPELINE
    # ==============================================
    
    def run_complete_scientific_analysis(
        self,
        aoi: ee.Geometry,
        start_date: str,
        end_date: str,
        crop_type: str,
        growth_stages: Dict,  # {'vegetative': (start, end), 'grain_filling': (start, end)}
        soil_data: Dict,
        weather_data: Dict,
        historical_data: Dict = None
    ) -> Dict:
        """
        Complete scientific analysis pipeline
        Returns all indices and yield prediction
        """
        
        # 1. Get satellite data
        s2_collection = self._get_sentinel2(aoi, start_date, end_date)
        s1_collection = self._get_sentinel1(aoi, start_date, end_date)
        
        # 2. Calculate basic indices
        s2_with_indices = s2_collection.map(lambda img: self.calculate_basic_indices(img))
        s1_with_rsi = s1_collection.map(lambda img: self.calculate_rsi(img))
        
        # 3. Extract values for each growth stage
        stage_data = {}
        for stage, (stage_start, stage_end) in growth_stages.items():
            stage_collection = s2_with_indices.filterDate(stage_start, stage_end)
            
            # Mean values for stage
            stage_mean = stage_collection.mean().reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=10,
                maxPixels=1e9
            ).getInfo()
            
            stage_data[stage] = stage_mean
        
        # 4. Calculate VCI and TCI
        ndvi_current = stage_data.get('grain_filling', {}).get('NDVI', 0.5)
        ndvi_history = historical_data.get('ndvi_range', {'min': 0.2, 'max': 0.9}) if historical_data else {'min': 0.2, 'max': 0.9}
        
        vci = self.calculate_vci(
            ndvi_current,
            ndvi_history['min'],
            ndvi_history['max']
        )
        
        temp_current = weather_data.get('temperature', 25)
        temp_history = historical_data.get('temp_range', {'min': 15, 'max': 35}) if historical_data else {'min': 15, 'max': 35}
        
        tci = self.calculate_tci(
            temp_current,
            temp_history['min'],
            temp_history['max']
        )
        
        # 5. Calculate VHI
        vhi = self.calculate_vhi(vci, tci)
        
        # 6. Calculate SPI
        normalized_soil = self.normalize_soil_properties(soil_data)
        spi = self.calculate_spi(normalized_soil)
        
        # 7. Calculate EWA and WSI for each stage
        crop_params = self.crop_params.get(crop_type, self.crop_params['maize'])
        
        ewa_veg = self.calculate_ewa(
            weather_data.get('rainfall_vegetative', 250),
            normalized_soil.get('whc_norm', 0.5),
            soil_data.get('smap_moisture', 0.3),
            crop_params['water_req_veg']
        )
        
        ewa_grain = self.calculate_ewa(
            weather_data.get('rainfall_grain', 200),
            normalized_soil.get('whc_norm', 0.5),
            soil_data.get('smap_moisture', 0.25),
            crop_params['water_req_grain']
        )
        
        wsi_veg = self.calculate_wsi(ewa_veg)
        wsi_grain = self.calculate_wsi(ewa_grain)
        
        # 8. Calculate GDD and CSI
        temp_series = weather_data.get('temp_max_series', [25]*60)
        temp_min_series = weather_data.get('temp_min_series', [15]*60)
        
        gdd = self.calculate_gdd(
            temp_series,
            temp_min_series,
            crop_params['T_base']
        )
        
        climate_norm = self.normalize_climate_variables(
            weather_data.get('total_rainfall', 600),
            np.mean(temp_series),
            gdd,
            crop_type
        )
        
        csi = self.calculate_csi(
            climate_norm['rainfall_norm'],
            climate_norm['temp_norm'],
            climate_norm['gdd_norm']
        )
        
        # 9. Calculate RSI
        rsi_grain_values = []  # Extract from S1 data
        rsi_grain = self.get_stage_rsi(rsi_grain_values) if rsi_grain_values else 0.5
        
        # 10. Calculate SVS for each stage
        svs_veg = self.calculate_svs(
            stage_data.get('vegetative', {}).get('NDVI', 0.5),
            stage_data.get('vegetative', {}).get('EVI', 0.3),
            stage_data.get('vegetative', {}).get('NDMI', 0.3),
            'vegetative'
        )
        
        svs_grain = self.calculate_svs(
            stage_data.get('grain_filling', {}).get('NDVI', 0.5),
            stage_data.get('grain_filling', {}).get('EVI', 0.3),
            stage_data.get('grain_filling', {}).get('NDMI', 0.3),
            'grain_filling'
        )
        
        # 11. Calculate CHI
        chi = self.calculate_chi(vhi, spi, wsi_grain, csi, rsi_grain)
        
        # 12. Yield estimation (both methods)
        yield_simple = self.estimate_yield_simple(chi, wsi_grain, crop_type)
        
        yield_regression = self.estimate_yield_regression(
            svs_veg, svs_grain,
            ewa_veg, ewa_grain,
            spi, rsi_grain
        )
        
        # 13. Yield anomaly (if historical data available)
        yield_anomaly = None
        if historical_data and 'mean_yield' in historical_data:
            yield_anomaly = self.calculate_yield_anomaly(
                yield_regression,
                historical_data['mean_yield']
            )
        
        # 14. Confidence score (if validation RMSE available)
        confidence = 0.75  # Default
        if historical_data and 'rmse' in historical_data:
            confidence = self.calculate_confidence(
                historical_data['rmse'],
                historical_data['mean_yield']
            )
        
        # 15. Compile results
        results = {
            'vegetation_health_index': round(vhi * 100, 2),
            'crop_health_index': round(chi * 100, 2),
            'soil_productivity_index': round(spi * 100, 2),
            'water_stress_index': round(wsi_grain * 100, 2),
            'climate_suitability_index': round(csi * 100, 2),
            'yield_prediction': {
                'simple_model_t_ha': round(yield_simple, 2),
                'regression_model_t_ha': round(yield_regression, 2),
                'confidence_pct': round(confidence * 100, 1),
                'anomaly_pct': round(yield_anomaly * 100, 2) if yield_anomaly else None
            },
            'stage_scores': {
                'vegetative': {
                    'svs': round(svs_veg, 3),
                    'ewa': round(ewa_veg, 3),
                    'wsi': round(wsi_veg, 3)
                },
                'grain_filling': {
                    'svs': round(svs_grain, 3),
                    'ewa': round(ewa_grain, 3),
                    'wsi': round(wsi_grain, 3)
                }
            },
            'climate_metrics': {
                'gdd': round(gdd, 1),
                'rainfall_mm': weather_data.get('total_rainfall', 0),
                'avg_temp_c': round(np.mean(temp_series), 1)
            },
            'indices': stage_data,
            'risk_assessment': self._assess_risk(chi, wsi_grain, vhi)
        }
        
        return results
    
    def _assess_risk(self, chi: float, wsi: float, vhi: float) -> str:
        """Assess overall production risk"""
        if chi > 0.75 and wsi < 0.3 and vhi > 0.75:
            return "Low"
        elif chi > 0.6 and wsi < 0.5 and vhi > 0.6:
            return "Moderate"
        elif chi > 0.45:
            return "High"
        else:
            return "Very High"
    
    def _get_sentinel2(self, aoi: ee.Geometry, start_date: str, 
                      end_date: str) -> ee.ImageCollection:
        """Get Sentinel-2 data"""
        return ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))
    
    def _get_sentinel1(self, aoi: ee.Geometry, start_date: str, 
                      end_date: str) -> ee.ImageCollection:
        """Get Sentinel-1 data"""
        return ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))