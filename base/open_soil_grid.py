import cdsapi
import xarray as xr
import requests
import pandas as pd
import json
import os
from datetime import datetime
import time
import numpy as np
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from shapely.geometry import Polygon, Point
from typing import List


class IntegratedSoilAnalyzer:
    """Class for integrated soil and climate data analysis using ERA5 and SoilGrids"""
    
    def __init__(self, huggingface_token: str = None):
        """Initialize with required configurations"""
        self.huggingface_token = huggingface_token or os.getenv("HUGGINGFACE_TOKEN")
        if not self.huggingface_token:
            raise ValueError("Hugging Face token is required")
            
        # Falcon-7B configuration
        self.model_url = "https://api-inference.huggingface.co/models/tiiuae/falcon-7b-instruct"
        self.headers = {"Authorization": f"Bearer {self.huggingface_token}"}
        
        # CDS client initialization
        self.cds_client = cdsapi.Client()
        
        # Request configuration
        self.max_retries = 3
        self.retry_delay = 5
        self.last_request_time = None
        self.min_request_interval = 2
    
    def get_era5_data(self, latitude: float, longitude: float, date: str) -> Dict[str, Any]:
        """Fetch ERA5 climate data"""
        temp_file = 'temp_era5_data.nc'
        year, month, day = date.split('-')
        
        # Calculate area bounds (0.5 degree buffer)
        area = [
            latitude + 0.5, longitude - 0.5,
            latitude - 0.5, longitude + 0.5
        ]
        
        request = {
            "variable": ["stl1", "swvl1", "e"],
            "year": year,
            "month": month,
            "day": [day],
            "time": ["00:00"],
            "format": "netcdf",
            "area": area
        }
        
        try:
            self.cds_client.retrieve("reanalysis-era5-land", request, temp_file)
            ds = xr.open_dataset(temp_file, engine='netcdf4')
            
            data = {
                "metadata": {
                    "timestamp": f"{date}T00:00:00",
                    "area": {
                        "north": area[0],
                        "east": area[3],
                        "south": area[2],
                        "west": area[1]
                    },
                    "source": "ERA5-Land"
                },
                "data": {}
            }
            
            variable_mapping = {
                'stl1': 'soil_temperature_level_1',
                'swvl1': 'volumetric_soil_water_layer_1',
                'e': 'total_evaporation'
            }
            
            for var_short_name in request["variable"]:
                if var_short_name in ds:
                    values = ds[var_short_name].values
                    readable_name = variable_mapping[var_short_name]
                    data["data"][readable_name] = {
                        "mean": float(np.nanmean(values)),
                        "min": float(np.nanmin(values)),
                        "max": float(np.nanmax(values)),
                        "unit": str(ds[var_short_name].units) if hasattr(ds[var_short_name], 'units') else "unknown"
                    }
            
            return data
            
        finally:
            if os.path.exists(temp_file):
                os.remove(temp_file)
            if 'ds' in locals():
                ds.close()

    def get_soilgrid_data(self, latitude: float, longitude: float) -> Optional[pd.DataFrame]:
        """Fetch soil data from SoilGrids"""
        base_url = "https://rest.isric.org"
        endpoint = f"soilgrids/v2.0/properties/query?lat={latitude}&lon={longitude}"
        
        try:
            response = requests.get(f"{base_url}/{endpoint}")
            response.raise_for_status()
            
            data = response.json()
            properties = data['properties']['layers']
            
            soil_data = {}
            for prop in properties:
                soil_data[prop['name']] = prop['depths'][0]['values']['mean']
                
            return pd.DataFrame([soil_data])
            
        except Exception as e:
            print(f"SoilGrids API Error: {e}")
            return None

        
    def analyze_combined_data(self, soil_data: pd.DataFrame, climate_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze combined soil and climate data using Falcon-7B"""
        combined_data = {
            "soil_properties": soil_data.to_dict(orient='records')[0],
            "climate_conditions": climate_data['data']
        }
        
        prompt = f"""You are an expert agricultural scientist and soil specialist. Analyze the following integrated soil and climate data to provide a detailed agricultural assessment and recommendations. Focus on practical, actionable insights.

Context:
The data provided combines soil properties from SoilGrids and climate conditions from ERA5-Land satellite data. All measurements are from ground level to 30cm depth.

Data for Analysis:
{json.dumps(combined_data, indent=2)}

PProvide a comprehensive analysis covering:

    Soil Health Assessment: Analyze texture, structure, nutrients, organic matter, deficiencies; rate health (1-10).
    Climate Impact: Assess temperature, moisture, evaporation; suggest climate-smart practices.
    Crop Recommendations: Suggest top 3 crops with yields, planting times, varieties, management.
    Soil Plan: Propose amendments, fertilizers, conservation, irrigation.
    Risk & Mitigation: Identify degradation risks, imbalances, pests; preventive measures.
    Economics: Cost analysis, ROI, low-cost options."""

        retries = 0
        current_delay = self.retry_delay
        
        while retries < self.max_retries:
            try:
                if self.last_request_time:
                    elapsed = (datetime.now() - self.last_request_time).total_seconds()
                    if elapsed < self.min_request_interval:
                        time.sleep(self.min_request_interval - elapsed)
                
                self.last_request_time = datetime.now()
                
                response = requests.post(
                    self.model_url,
                    headers=self.headers,
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": 1000,  # Increased token limit for more detailed response
                            "temperature": 0.7,
                            "top_p": 0.95,
                            "return_full_text": False
                        }
                    },
                    timeout=45  # Increased timeout for longer response
                )
                response.raise_for_status()
                
                result = response.json()
                analysis = result[0]['generated_text'] if isinstance(result, list) else result.get('generated_text', str(result))
                
                return {
                    "success": True,
                    "model": "falcon-7b-instruct",
                    "analysis": analysis,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                print(f"Analysis attempt {retries + 1} failed: {e}")
                retries += 1
                if retries < self.max_retries:
                    time.sleep(current_delay)
                    current_delay *= 2
        
        return {
            "success": False,
            "error": "Max retries exceeded",
            "model": "falcon-7b-instruct",
            "timestamp": datetime.now().isoformat()
        }
class FieldCoordinateProcessor:
    """Process and analyze field coordinates from map polygons"""
    
    def __init__(self, integrated_analyzer: IntegratedSoilAnalyzer):
        """Initialize with the soil analyzer instance"""
        self.analyzer = integrated_analyzer
        
    def process_field_polygon(self, coordinates: List[List[float]], sample_density: float = 0.01) -> Dict:
        """
        Process a field's polygon coordinates and run soil analysis on sample points
        
        Args:
            coordinates: List of [latitude, longitude] pairs defining the polygon
            sample_density: Distance between sample points in degrees (default: 0.01 ≈ 1km)
        
        Returns:
            Dictionary containing analysis results for the field
        """
        # Create polygon from coordinates
        poly = Polygon(coordinates)
        
        # Get bounding box
        minx, miny, maxx, maxy = poly.bounds
        
        # Create grid of points
        x = np.arange(minx, maxx, sample_density)
        y = np.arange(miny, maxy, sample_density)
        points = []
        
        # Filter points to only those within polygon
        for i in x:
            for j in y:
                if poly.contains(Point(i, j)):
                    points.append((j, i))  # Note: (latitude, longitude) format
        
        # Analyze each point
        results = []
        for lat, lon in points:
            try:
                soil_data = self.analyzer.get_soilgrid_data(lat, lon)
                climate_data = self.analyzer.get_era5_data(lat, lon, date="2024-01-15")  # Use current date
                
                if soil_data is not None and climate_data is not None:
                    analysis = self.analyzer.analyze_combined_data(soil_data, climate_data)
                    results.append({
                        "coordinates": {"latitude": lat, "longitude": lon},
                        "analysis": analysis
                    })
            except Exception as e:
                print(f"Error analyzing point ({lat}, {lon}): {e}")
        
        # Aggregate results
        return {
            "field_boundary": coordinates,
            "sample_points": len(results),
            "analyses": results,
            "summary": self._aggregate_analyses(results)
        }
    
        
    def _aggregate_analyses(self, results: List[Dict]) -> Dict:
        """Aggregate analyses from multiple points to create field summary"""
        if not results:
            return {"error": "No valid analyses to aggregate"}
            
        # Extract successful analyses
        successful_analyses = [r for r in results if r["analysis"].get("success", False)]
        
        if not successful_analyses:
            return {"error": "No successful analyses to aggregate"}
            
        # Combine all analyses into a summary
        return {
            "total_points": len(results),
            "successful_analyses": len(successful_analyses),
            "field_size_ha": self._calculate_field_size(results),
            "average_soil_health": self._extract_average_soil_health(successful_analyses),
            "recommended_crops": self._summarize_crop_recommendations(successful_analyses)
        }
        
    def _calculate_field_size(self, results: List[Dict]) -> float:
        """Calculate approximate field size in hectares"""
        if not results:
            return 0.0
        coordinates = [r["coordinates"] for r in results]
        poly = Polygon(coordinates)
        # Rough conversion from degree-square to hectares
        return poly.area * 111 * 111 * 100
        
    def _extract_average_soil_health(self, analyses: List[Dict]) -> float:
        """Extract and average soil health ratings from analyses"""
        health_scores = []
        for analysis in analyses:
            try:
                # Extract soil health rating from analysis text
                text = analysis["analysis"]["analysis"]
                if "rate health (" in text.lower():
                    score = float(text.split("rate health (")[1].split(")")[0].split("-")[0])
                    health_scores.append(score)
            except:
                continue
        return sum(health_scores) / len(health_scores) if health_scores else 0.0
    
        
    def _summarize_crop_recommendations(self, analyses: List[Dict]) -> List[str]:
        """Summarize crop recommendations across all points"""
        crop_mentions = {}
        for analysis in analyses:
            try:
                text = analysis["analysis"]["analysis"]
                if "crop recommendations" in text.lower():
                    crops_section = text.split("Crop Recommendations:")[1].split("\n")[0]
                    crops = [c.strip() for c in crops_section.split(",")]
                    for crop in crops:
                        crop_mentions[crop] = crop_mentions.get(crop, 0) + 1
            except:
                continue
        
        # Return top 3 most recommended crops
        return sorted(crop_mentions.items(), key=lambda x: x[1], reverse=True)[:3]

        
def main():
    """Main execution function"""
    try:
        analyzer = IntegratedSoilAnalyzer()
        field_processor = FieldCoordinateProcessor(analyzer)
        
        # Example polygon coordinates from map
        field_coordinates = [
            [20.5937, 78.9629],
            [20.5957, 78.9649],
            [20.5947, 78.9669],
            [20.5927, 78.9649],
            [20.5937, 78.9629]
        ]
        
        print("Processing field coordinates...")
        results = field_processor.process_field_polygon(field_coordinates)
        
        # Save results
        output_file = 'field_analysis_results.json'
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {output_file}")
        
    except Exception as e:
        print(f"Program execution failed: {e}")

if __name__ == "__main__":
    main()