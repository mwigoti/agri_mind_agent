import cdsapi
import xarray as xr
import requests
import pandas as pd
import json
import os
import sys
from datetime import datetime, date
import time
import numpy as np
from typing import Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import django
from django.conf import settings


# Ensure Django is configured
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AgriVision.settings')
django.setup()

from .models import Field  # Replace with your actual app name
from pyproj import Transformer

class IntegratedSoilAnalyzer:
    def __init__(self, huggingface_token: Optional[str] = None):
        """Initialize with required configurations"""
        self.huggingface_token = huggingface_token or os.getenv("HUGGINGFACE_TOKEN")
        if not self.huggingface_token:
            raise ValueError("Hugging Face token is required. Set HUGGINGFACE_TOKEN environment variable.")
            
        # Falcon-7B configuration
        self.model_url = "https://api-inference.huggingface.co/models/tiiuae/falcon-7b-instruct"
        self.headers = {
            "Authorization": f"Bearer {self.huggingface_token}",
            "Content-Type": "application/json"
        }
        
        # CDS client initialization
        self.cds_client = cdsapi.Client(
            url=os.environ.get('CDS_URL'),
            key=os.environ.get('CDS_KEY')
        )
        
        # Request configuration
        self.max_retries = 3
        self.retry_delay = 5
        self.last_request_time = None
        self.min_request_interval = 2
        
    
    def get_field_center(self, id: int) -> Dict[str, float]:
        """
        Retrieve the center coordinates of a field using Django ORM
        
        Args:
            field_id (int): ID of the field in the database
        
        Returns:
            Dict with latitude and longitude
        """
        try:
            # Fetch the field by ID
            field = Field.objects.get(pk=id)
            
            # Create a transformer from Web Mercator (EPSG:3857) to WGS84 (EPSG:4326)
            transformer = Transformer.from_crs(
                "EPSG:3857",  # Web Mercator
                "EPSG:4326",  # WGS84 lat/lon
                always_xy=True  # Ensure x, y order
            )
            
            # Get the centroid of the geometry
            center = field.geometry.centroid
            
            # Transform the coordinates
            lon, lat = transformer.transform(center.x, center.y)
            
            return {
                "latitude": lat,
                "longitude": lon,
                "name": field.name
            }
        
        except Field.DoesNotExist:
            raise ValueError(f"Field with ID {id} not found")
        except Exception as e:
            raise RuntimeError(f"Error retrieving field center: {e}")
    def get_soilgrid_data(self, lat: float, lon: float) -> Optional[pd.DataFrame]:
    
        base_url = "https://rest.isric.org"
        endpoint = f"soilgrids/v2.0/properties/query?lat={lat}&lon={lon}"
        
        try:
            # Timeout set to 30 seconds to prevent long-running requests
            response = requests.get(f"{base_url}/{endpoint}", timeout=30)
            response.raise_for_status()
            
            # Parse the JSON response
            data = response.json()
            properties = data.get('properties', {}).get('layers', [])
            
            # Extract soil properties
            soil_data = {}
            for prop in properties:
                # Safely extract mean value, defaulting to None if not available
                soil_data[prop['name']] = prop['depths'][0]['values'].get('mean')
            
            # Convert to DataFrame, handling potential empty data
            df = pd.DataFrame([soil_data])
            
            return df
        
        except requests.RequestException as e:
            print(f"SoilGrids API Request Error: {e}")
            return None
        except (KeyError, IndexError, ValueError) as e:
            print(f"SoilGrids Data Parsing Error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error fetching SoilGrids data: {e}")
            return None
    def get_era5_data(self, latitude: float, longitude: float, analysis_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetch ERA5 climate data"""
        # Use current date if no specific date provided
        if analysis_date is None:
            analysis_date = "2024-11-23"
        
        temp_file = f'temp_era5_data_{int(time.time())}.nc'
        try:
            year, month, day = analysis_date.split('-')
            
            # Calculate area bounds (0.5 degree buffer)
            area = [
                min(90, latitude + 0.5), 
                max(-180, longitude - 0.5),
                max(-90, latitude - 0.5), 
                min(180, longitude + 0.5)
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
            
            self.cds_client.retrieve("reanalysis-era5-land", request, temp_file)
            
            # Open dataset with error handling
            ds = xr.open_dataset(temp_file, engine='netcdf4')
            
            data = {
                "metadata": {
                    "timestamp": f"{analysis_date}T00:00:00",
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
            
        except Exception as e:
            print(f"Error fetching ERA5 data: {e}")
            raise
        finally:
            # Ensure file is closed and deleted
            if 'ds' in locals():
                ds.close()
            if os.path.exists(temp_file):
                os.remove(temp_file)

    # Rest of the methods remain the same as in the previous implementation
    # (get_soilgrid_data, analyze_combined_data, etc.)

def analyze_field(id: int, huggingface_token: Optional[str] = None) -> Dict[str, Any]:
    """
    Comprehensive field analysis workflow
    
    Args:
        field_id (int): ID of the field to analyze
        huggingface_token (Optional[str]): Hugging Face API token
    
    Returns:
        Dict with analysis results
    """
    try:
        # Initialize analyzer
        analyzer = IntegratedSoilAnalyzer(huggingface_token)
        
        # Get field center coordinates
        field_center = analyzer.get_field_center(id)
        
        print(f"\nAnalyzing field: {field_center['name']}")
        print(f"Coordinates: Lat {field_center['latitude']}, Lon {field_center['longitude']}")
        
        # Concurrent data fetching
        with ThreadPoolExecutor(max_workers=2) as executor:
            # Submit tasks
            soil_future = executor.submit(analyzer.get_soilgrid_data, 
                                          field_center['latitude'], 
                                          field_center['longitude'])
            climate_future = executor.submit(analyzer.get_era5_data, 
                                             field_center['latitude'], 
                                             field_center['longitude'])
            
            # Wait for results
            soil_data = soil_future.result()
            climate_data = climate_future.result()
        
        # Validate retrieved data
        if soil_data is None or climate_data is None:
            raise ValueError("Failed to retrieve complete data")
        
        # Perform analysis
        result = analyzer.analyze_combined_data(soil_data, climate_data)
        
        # Attach field metadata to result
        result['field_metadata'] = field_center
        
        return result
    
    except Exception as e:
        print(f"\nCritical error during field analysis: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "field_id": id
        }

