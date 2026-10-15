"""
Agrivision - Crop Health and Yield Optimization Analysis
Integrates GEE Sentinel-1/2 data with soil and weather data
"""

import ee
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import json
import pandas as pd
from django.conf import settings
import requests


class AgrivisionGEEAnalyzer:
    """
    Main class for analyzing agricultural data using Google Earth Engine
    """
    
    def __init__(self, service_account_path: str = None):
        """
        Initialize GEE with service account credentials
        
        Args:
            service_account_path: Path to GEE service account JSON file
        """
        try:
            if service_account_path:
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
    
    def define_aoi(self, coordinates: List[List[float]]) -> ee.Geometry:
        """
        Define Area of Interest from coordinates
        
        Args:
            coordinates: List of [lon, lat] coordinate pairs
            
        Returns:
            ee.Geometry.Polygon object
        """
        return ee.Geometry.Polygon(coordinates)
    
    def get_sentinel2_data(self, aoi: ee.Geometry, start_date: str, 
                          end_date: str, cloud_threshold: int = 20) -> ee.ImageCollection:
        """
        Retrieve Sentinel-2 imagery
        
        Args:
            aoi: Area of Interest geometry
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            cloud_threshold: Maximum cloud cover percentage
            
        Returns:
            Filtered Sentinel-2 ImageCollection
        """
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', cloud_threshold))
        
        return s2
    
    def get_sentinel1_data(self, aoi: ee.Geometry, start_date: str, 
                          end_date: str) -> ee.ImageCollection:
        """
        Retrieve Sentinel-1 SAR imagery
        
        Args:
            aoi: Area of Interest geometry
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            Filtered Sentinel-1 ImageCollection
        """
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(aoi) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
        
        return s1
    
    def calculate_vegetation_indices(self, image: ee.Image) -> ee.Image:
        """
        Calculate all major vegetation indices
        
        Args:
            image: Sentinel-2 image
            
        Returns:
            Image with added vegetation index bands
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
        
        # SAVI - Soil Adjusted Vegetation Index (L=0.5)
        savi = image.expression(
            '((NIR - RED) / (NIR + RED + 0.5)) * 1.5',
            {
                'NIR': image.select('B8'),
                'RED': image.select('B4')
            }
        ).rename('SAVI')
        
        # NDWI - Normalized Difference Water Index
        ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
        
        # NDMI - Normalized Difference Moisture Index
        ndmi = image.normalizedDifference(['B8', 'B11']).rename('NDMI')
        
        # GNDVI - Green Normalized Difference Vegetation Index
        gndvi = image.normalizedDifference(['B8', 'B3']).rename('GNDVI')
        
        # MSAVI2 - Modified Soil Adjusted Vegetation Index
        msavi2 = image.expression(
            '(2 * NIR + 1 - sqrt(pow((2 * NIR + 1), 2) - 8 * (NIR - RED))) / 2',
            {
                'NIR': image.select('B8'),
                'RED': image.select('B4')
            }
        ).rename('MSAVI2')
        
        # NBR - Normalized Burn Ratio
        nbr = image.normalizedDifference(['B8', 'B12']).rename('NBR')
        
        # NDRE - Normalized Difference Red Edge
        ndre = image.normalizedDifference(['B8', 'B5']).rename('NDRE')
        
        # CIG - Chlorophyll Index Green
        cig = image.expression(
            '(NIR / GREEN) - 1',
            {
                'NIR': image.select('B8'),
                'GREEN': image.select('B3')
            }
        ).rename('CIG')
        
        # ARVI - Atmospherically Resistant Vegetation Index
        arvi = image.expression(
            '(NIR - (2 * RED - BLUE)) / (NIR + (2 * RED - BLUE))',
            {
                'NIR': image.select('B8'),
                'RED': image.select('B4'),
                'BLUE': image.select('B2')
            }
        ).rename('ARVI')
        
        return image.addBands([ndvi, evi, savi, ndwi, ndmi, gndvi, 
                               msavi2, nbr, ndre, cig, arvi])
    
    def calculate_sar_indices(self, image: ee.Image) -> ee.Image:
        """
        Calculate SAR-based indices from Sentinel-1
        
        Args:
            image: Sentinel-1 image
            
        Returns:
            Image with added SAR index bands
        """
        vv = image.select('VV')
        vh = image.select('VH')
        
        # VV/VH ratio
        ratio = vv.divide(vh).rename('VV_VH_RATIO')
        
        # RVI - Radar Vegetation Index
        rvi = vh.multiply(4).divide(vv.add(vh)).rename('RVI')
        
        # Dual Pol SAR Vegetation Index
        dpsvi = vh.divide(vv.add(vh)).rename('DPSVI')
        
        return image.addBands([ratio, rvi, dpsvi])
    
    def calculate_crop_health_score(self, indices: Dict[str, float], 
                                   soil_data: Dict, weather_data: Dict) -> Dict:
        """
        Calculate comprehensive crop health score
        
        Args:
            indices: Dictionary of calculated vegetation indices
            soil_data: Soil properties (pH, moisture, nutrients, etc.)
            weather_data: Weather conditions (temp, rainfall, humidity, etc.)
            
        Returns:
            Dictionary with health scores and recommendations
        """
        scores = {}
        
        # Vegetation health (40% weight)
        ndvi_score = self._normalize_score(indices.get('NDVI', 0), 0.2, 0.9)
        evi_score = self._normalize_score(indices.get('EVI', 0), 0.2, 0.8)
        savi_score = self._normalize_score(indices.get('SAVI', 0), 0.2, 0.7)
        vegetation_health = (ndvi_score * 0.5 + evi_score * 0.3 + savi_score * 0.2) * 100
        
        # Water stress (25% weight)
        ndwi_score = self._normalize_score(indices.get('NDWI', 0), -0.3, 0.3)
        ndmi_score = self._normalize_score(indices.get('NDMI', 0), 0.0, 0.6)
        water_stress = (ndwi_score * 0.6 + ndmi_score * 0.4) * 100
        
        # Soil health (20% weight)
        soil_ph_score = self._soil_ph_score(soil_data.get('ph', 7.0))
        soil_moisture_score = self._normalize_score(
            soil_data.get('moisture', 0), 
            soil_data.get('field_capacity', 0.2) * 0.5,
            soil_data.get('field_capacity', 0.35)
        )
        soil_health = (soil_ph_score * 0.5 + soil_moisture_score * 0.5) * 100
        
        # Weather conditions (15% weight)
        temp_score = self._temperature_score(weather_data.get('temperature', 25))
        rainfall_score = self._normalize_score(
            weather_data.get('rainfall_7day', 0), 10, 50
        )
        weather_score = (temp_score * 0.6 + rainfall_score * 0.4) * 100
        
        # Overall health score
        overall_health = (
            vegetation_health * 0.40 +
            water_stress * 0.25 +
            soil_health * 0.20 +
            weather_score * 0.15
        )
        
        return {
            'overall_health': round(overall_health, 2),
            'vegetation_health': round(vegetation_health, 2),
            'water_stress_index': round(100 - water_stress, 2),  # Inverted for stress
            'soil_health': round(soil_health, 2),
            'weather_favorability': round(weather_score, 2),
            'health_category': self._categorize_health(overall_health),
            'recommendations': self._generate_recommendations(
                overall_health, vegetation_health, water_stress, 
                soil_health, indices, soil_data, weather_data
            )
        }
    
    def predict_yield(self, indices: Dict[str, float], soil_data: Dict, 
                     weather_data: Dict, crop_type: str, 
                     growth_stage: str) -> Dict:
        """
        Predict crop yield based on multiple factors
        
        Args:
            indices: Vegetation indices
            soil_data: Soil properties
            weather_data: Weather data
            crop_type: Type of crop (wheat, rice, maize, etc.)
            growth_stage: Current growth stage
            
        Returns:
            Yield prediction dictionary
        """
        # Base yield factors
        ndvi = indices.get('NDVI', 0.5)
        evi = indices.get('EVI', 0.3)
        lai_estimate = self._estimate_lai(ndvi, evi)
        
        # Growth stage multipliers
        stage_multipliers = {
            'germination': 0.3,
            'vegetative': 0.6,
            'flowering': 0.85,
            'grain_filling': 0.95,
            'maturity': 1.0
        }
        stage_multiplier = stage_multipliers.get(growth_stage.lower(), 0.7)
        
        # Crop-specific baseline yields (tonnes per hectare)
        baseline_yields = {
            'wheat': 3.5,
            'rice': 4.5,
            'maize': 5.5,
            'soybean': 2.8,
            'barley': 3.2,
            'cotton': 2.5
        }
        baseline_yield = baseline_yields.get(crop_type.lower(), 3.0)
        
        # Vegetation factor (0.5 to 1.5 multiplier)
        veg_factor = 0.5 + (ndvi * 1.0) + (evi * 0.5)
        veg_factor = min(1.5, max(0.5, veg_factor))
        
        # Soil factor
        soil_factor = self._calculate_soil_factor(soil_data)
        
        # Weather factor
        weather_factor = self._calculate_weather_factor(weather_data, crop_type)
        
        # Water availability factor
        water_factor = 0.7 + (indices.get('NDMI', 0.3) * 0.6)
        
        # Predicted yield
        predicted_yield = (
            baseline_yield * 
            veg_factor * 
            soil_factor * 
            weather_factor * 
            water_factor * 
            stage_multiplier
        )
        
        # Confidence calculation
        data_quality = self._assess_data_quality(indices, soil_data, weather_data)
        confidence = data_quality * stage_multiplier
        
        return {
            'predicted_yield_tonnes_per_ha': round(predicted_yield, 2),
            'confidence_percentage': round(confidence * 100, 1),
            'lai_estimate': round(lai_estimate, 2),
            'yield_category': self._categorize_yield(predicted_yield, baseline_yield),
            'limiting_factors': self._identify_limiting_factors(
                veg_factor, soil_factor, weather_factor, water_factor
            ),
            'optimization_potential': self._calculate_optimization_potential(
                predicted_yield, baseline_yield, veg_factor, soil_factor, 
                weather_factor, water_factor
            )
        }
    
    def generate_field_zones(self, aoi: ee.Geometry, image: ee.Image, 
                            num_zones: int = 5) -> Dict:
        """
        Generate management zones based on NDVI and other indices
        
        Args:
            aoi: Area of interest
            image: Image with calculated indices
            num_zones: Number of management zones to create
            
        Returns:
            Dictionary with zone information
        """
        # Use NDVI and NDMI for zone classification
        ndvi = image.select('NDVI')
        ndmi = image.select('NDMI')
        
        # Stack bands for clustering
        stack = ee.Image.cat([ndvi, ndmi])
        
        # K-means clustering
        training = stack.sample(
            region=aoi,
            scale=10,
            numPixels=5000
        )
        
        clusterer = ee.Clusterer.wekaKMeans(num_zones).train(training)
        zones = stack.cluster(clusterer).select('cluster')
        
        # Calculate statistics for each zone
        zone_stats = []
        for i in range(num_zones):
            zone_mask = zones.eq(i)
            zone_image = image.updateMask(zone_mask)
            
            stats = zone_image.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=10,
                maxPixels=1e9
            )
            
            zone_stats.append({
                'zone_id': i + 1,
                'statistics': stats.getInfo()
            })
        
        return {
            'num_zones': num_zones,
            'zone_statistics': zone_stats,
            'zone_image': zones
        }
    
    def analyze_temporal_trend(self, collection: ee.ImageCollection, 
                              aoi: ee.Geometry, index: str = 'NDVI') -> Dict:
        """
        Analyze temporal trends in vegetation indices
        
        Args:
            collection: Image collection with calculated indices
            aoi: Area of interest
            index: Index to analyze
            
        Returns:
            Dictionary with trend analysis
        """
        # Extract time series
        def extract_value(image):
            value = image.select(index).reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=10,
                maxPixels=1e9
            ).get(index)
            
            return ee.Feature(None, {
                'value': value,
                'date': image.date().format('YYYY-MM-dd')
            })
        
        time_series = collection.map(extract_value)
        
        # Calculate trend statistics
        values = collection.select(index).toBands()
        trend = values.reduce(ee.Reducer.linearFit())
        
        trend_stats = trend.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=10,
            maxPixels=1e9
        )
        
        return {
            'index': index,
            'trend_slope': trend_stats.getInfo().get('scale', 0),
            'trend_offset': trend_stats.getInfo().get('offset', 0),
            'time_series': time_series.getInfo()
        }
    
    # Helper methods
    
    def _normalize_score(self, value: float, min_val: float, max_val: float) -> float:
        """Normalize value to 0-1 range"""
        return max(0, min(1, (value - min_val) / (max_val - min_val)))
    
    def _soil_ph_score(self, ph: float) -> float:
        """Calculate soil pH score (optimal range 6.0-7.5)"""
        if 6.0 <= ph <= 7.5:
            return 1.0
        elif 5.5 <= ph < 6.0 or 7.5 < ph <= 8.0:
            return 0.7
        elif 5.0 <= ph < 5.5 or 8.0 < ph <= 8.5:
            return 0.4
        else:
            return 0.2
    
    def _temperature_score(self, temp: float) -> float:
        """Calculate temperature score (optimal 15-30°C)"""
        if 15 <= temp <= 30:
            return 1.0
        elif 10 <= temp < 15 or 30 < temp <= 35:
            return 0.7
        elif 5 <= temp < 10 or 35 < temp <= 40:
            return 0.4
        else:
            return 0.2
    
    def _categorize_health(self, score: float) -> str:
        """Categorize health score"""
        if score >= 80:
            return "Excellent"
        elif score >= 65:
            return "Good"
        elif score >= 50:
            return "Fair"
        elif score >= 35:
            return "Poor"
        else:
            return "Critical"
    
    def _estimate_lai(self, ndvi: float, evi: float) -> float:
        """Estimate Leaf Area Index"""
        # Simplified LAI estimation
        lai = 3.618 * evi - 0.118
        return max(0, min(8, lai))
    
    def _calculate_soil_factor(self, soil_data: Dict) -> float:
        """Calculate soil contribution to yield"""
        ph_score = self._soil_ph_score(soil_data.get('ph', 7.0))
        
        # Nutrient availability scores
        n_score = self._normalize_score(soil_data.get('nitrogen', 0), 20, 100)
        p_score = self._normalize_score(soil_data.get('phosphorus', 0), 10, 50)
        k_score = self._normalize_score(soil_data.get('potassium', 0), 100, 300)
        
        # Organic matter score
        om_score = self._normalize_score(soil_data.get('organic_matter', 0), 1.5, 5.0)
        
        soil_factor = (
            ph_score * 0.25 +
            n_score * 0.25 +
            p_score * 0.15 +
            k_score * 0.15 +
            om_score * 0.20
        )
        
        return 0.5 + (soil_factor * 0.5)  # Range: 0.5 to 1.0
    
    def _calculate_weather_factor(self, weather_data: Dict, crop_type: str) -> float:
        """Calculate weather contribution to yield"""
        temp = weather_data.get('temperature', 25)
        rainfall = weather_data.get('rainfall_7day', 20)
        humidity = weather_data.get('humidity', 60)
        
        temp_score = self._temperature_score(temp)
        rainfall_score = self._normalize_score(rainfall, 10, 50)
        humidity_score = self._normalize_score(humidity, 40, 80)
        
        weather_factor = (
            temp_score * 0.4 +
            rainfall_score * 0.4 +
            humidity_score * 0.2
        )
        
        return 0.6 + (weather_factor * 0.4)  # Range: 0.6 to 1.0
    
    def _assess_data_quality(self, indices: Dict, soil_data: Dict, 
                            weather_data: Dict) -> float:
        """Assess overall data quality for confidence calculation"""
        indices_available = len([v for v in indices.values() if v is not None])
        soil_available = len([v for v in soil_data.values() if v is not None])
        weather_available = len([v for v in weather_data.values() if v is not None])
        
        total_expected = 15  # Expected number of data points
        total_available = indices_available + soil_available + weather_available
        
        return min(1.0, total_available / total_expected)
    
    def _categorize_yield(self, predicted: float, baseline: float) -> str:
        """Categorize yield prediction"""
        ratio = predicted / baseline
        if ratio >= 1.2:
            return "Excellent"
        elif ratio >= 1.0:
            return "Above Average"
        elif ratio >= 0.8:
            return "Average"
        elif ratio >= 0.6:
            return "Below Average"
        else:
            return "Poor"
    
    def _identify_limiting_factors(self, veg_factor: float, soil_factor: float,
                                   weather_factor: float, water_factor: float) -> List[str]:
        """Identify factors limiting yield"""
        factors = {
            'Vegetation vigor': veg_factor,
            'Soil health': soil_factor,
            'Weather conditions': weather_factor,
            'Water availability': water_factor
        }
        
        # Find factors below 0.8 (80%)
        limiting = [name for name, value in factors.items() if value < 0.8]
        
        # Sort by severity
        limiting.sort(key=lambda x: factors[x])
        
        return limiting if limiting else ['None - optimal conditions']
    
    def _calculate_optimization_potential(self, predicted: float, baseline: float,
                                         veg_factor: float, soil_factor: float,
                                         weather_factor: float, water_factor: float) -> Dict:
        """Calculate yield optimization potential"""
        # Calculate what yield could be with optimal conditions
        optimal_yield = baseline * 1.5  # 150% of baseline
        
        # Calculate gaps
        current_gap = optimal_yield - predicted
        
        # Potential improvements
        improvements = {}
        if soil_factor < 0.9:
            improvements['soil_management'] = baseline * (0.9 - soil_factor) * 0.5
        if water_factor < 0.9:
            improvements['irrigation'] = baseline * (0.9 - water_factor) * 0.7
        if veg_factor < 1.2:
            improvements['crop_nutrition'] = baseline * (1.2 - veg_factor) * 0.3
        
        total_potential = sum(improvements.values())
        
        return {
            'current_yield': round(predicted, 2),
            'optimal_yield': round(optimal_yield, 2),
            'gap_tonnes_per_ha': round(current_gap, 2),
            'improvements': {k: round(v, 2) for k, v in improvements.items()},
            'total_potential_gain': round(total_potential, 2),
            'achievable_yield': round(predicted + total_potential * 0.7, 2)
        }
    
    def _generate_recommendations(self, overall_health: float, veg_health: float,
                                 water_stress: float, soil_health: float,
                                 indices: Dict, soil_data: Dict, 
                                 weather_data: Dict) -> List[Dict]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Vegetation health recommendations
        if veg_health < 60:
            recommendations.append({
                'priority': 'High',
                'category': 'Crop Nutrition',
                'issue': 'Low vegetation vigor detected',
                'action': 'Apply balanced NPK fertilizer. Consider foliar application for quick uptake.',
                'expected_improvement': '15-25% increase in vegetation health'
            })
        
        # Water stress recommendations
        if water_stress < 60:
            ndmi = indices.get('NDMI', 0)
            if ndmi < 0.3:
                recommendations.append({
                    'priority': 'Critical',
                    'category': 'Irrigation',
                    'issue': 'Severe water stress detected',
                    'action': 'Immediate irrigation required. Apply 25-30mm of water.',
                    'expected_improvement': 'Reduce water stress by 40-50%'
                })
        
        # Soil health recommendations
        if soil_health < 65:
            ph = soil_data.get('ph', 7.0)
            if ph < 6.0:
                recommendations.append({
                    'priority': 'Medium',
                    'category': 'Soil Management',
                    'issue': f'Soil pH too acidic ({ph})',
                    'action': 'Apply lime at 2-3 tonnes per hectare',
                    'expected_improvement': 'Improve nutrient availability'
                })
            elif ph > 8.0:
                recommendations.append({
                    'priority': 'Medium',
                    'category': 'Soil Management',
                    'issue': f'Soil pH too alkaline ({ph})',
                    'action': 'Apply elemental sulfur or acidifying fertilizers',
                    'expected_improvement': 'Improve nutrient availability'
                })
            
            if soil_data.get('organic_matter', 0) < 2.0:
                recommendations.append({
                    'priority': 'Low',
                    'category': 'Soil Management',
                    'issue': 'Low organic matter content',
                    'action': 'Incorporate compost or green manure',
                    'expected_improvement': 'Long-term soil health improvement'
                })
        
        # Weather-based recommendations
        temp = weather_data.get('temperature', 25)
        if temp > 35:
            recommendations.append({
                'priority': 'High',
                'category': 'Heat Stress Management',
                'issue': 'High temperature stress',
                'action': 'Increase irrigation frequency, consider shade nets for high-value crops',
                'expected_improvement': 'Reduce heat stress damage'
            })
        
        # Nitrogen recommendations based on NDRE
        ndre = indices.get('NDRE', 0)
        if ndre < 0.2:
            recommendations.append({
                'priority': 'High',
                'category': 'Crop Nutrition',
                'issue': 'Low nitrogen levels detected',
                'action': 'Apply nitrogen fertilizer at 40-60 kg/ha',
                'expected_improvement': 'Boost vegetative growth'
            })
        
        # Sort by priority
        priority_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3}
        recommendations.sort(key=lambda x: priority_order.get(x['priority'], 4))
        
        return recommendations
    
    def export_results_to_dict(self, analysis_results: Dict, 
                              field_info: Dict) -> Dict:
        """
        Export all results in a structured format for report generation
        
        Args:
            analysis_results: All analysis results
            field_info: Field information
            
        Returns:
            Structured dictionary ready for report generation
        """
        return {
            'field_information': field_info,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'satellite_data': {
                'sentinel_2': analysis_results.get('sentinel2_stats', {}),
                'sentinel_1': analysis_results.get('sentinel1_stats', {})
            },
            'vegetation_indices': analysis_results.get('indices', {}),
            'health_assessment': analysis_results.get('health_score', {}),
            'yield_prediction': analysis_results.get('yield_prediction', {}),
            'management_zones': analysis_results.get('zones', {}),
            'temporal_trends': analysis_results.get('trends', {}),
            'soil_analysis': analysis_results.get('soil_data', {}),
            'weather_data': analysis_results.get('weather_data', {}),
            'recommendations': analysis_results.get('recommendations', [])
        }


# Example usage function for Django views
def run_complete_analysis(field_coordinates: List[List[float]], 
                         field_name: str,
                         crop_type: str,
                         growth_stage: str,
                         soil_data: Dict,
                         weather_data: Dict,
                         start_date: str = None,
                         end_date: str = None) -> Dict:
    """
    Run complete Agrivision analysis
    
    Args:
        field_coordinates: Field boundary coordinates
        field_name: Name of the field
        crop_type: Type of crop
        growth_stage: Current growth stage
        soil_data: Soil properties dictionary
        weather_data: Weather data dictionary
        start_date: Analysis start date
        end_date: Analysis end date
        
    Returns:
        Complete analysis results
    """
    # Initialize analyzer
    analyzer = AgrivisionGEEAnalyzer()
    
    # Set date range if not provided
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # Define AOI
    aoi = analyzer.define_aoi(field_coordinates)
    
    # Get satellite data
    s2_collection = analyzer.get_sentinel2_data(aoi, start_date, end_date)
    s1_collection = analyzer.get_sentinel1_data(aoi, start_date, end_date)
    
    # Calculate indices for most recent image
    s2_latest = s2_collection.sort('system:time_start', False).first()
    s2_with_indices = analyzer.calculate_vegetation_indices(s2_latest)
    
    s1_latest = s1_collection.sort('system:time_start', False).first()
    s1_with_indices = analyzer.calculate_sar_indices(s1_latest)
    
    # Extract index values
    indices_stats = s2_with_indices.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=aoi,
        scale=10,
        maxPixels=1e9
    ).getInfo()
    
    # Calculate health score
    health_score = analyzer.calculate_crop_health_score(
        indices_stats, soil_data, weather_data
    )
    
    # Predict yield
    yield_prediction = analyzer.predict_yield(
        indices_stats, soil_data, weather_data, crop_type, growth_stage
    )
    
    # Generate management zones
    zones = analyzer.generate_field_zones(aoi, s2_with_indices, num_zones=5)
    
    # Analyze temporal trends
    s2_with_indices_collection = s2_collection.map(
        lambda img: analyzer.calculate_vegetation_indices(img)
    )
    trends = analyzer.analyze_temporal_trend(s2_with_indices_collection, aoi, 'NDVI')
    
    # Compile results
    results = {
        'indices': indices_stats,
        'health_score': health_score,
        'yield_prediction': yield_prediction,
        'zones': zones,
        'trends': trends,
        'soil_data': soil_data,
        'weather_data': weather_data,
        'recommendations': health_score['recommendations']
    }
    
    # Export for report
    field_info = {
        'name': field_name,
        'coordinates': field_coordinates,
        'crop_type': crop_type,
        'growth_stage': growth_stage,
        'area_hectares': aoi.area().divide(10000).getInfo()
    }
    
    final_results = analyzer.export_results_to_dict(results, field_info)
    
    return final_results