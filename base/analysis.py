import requests
import pandas as pd
import json
import os
from datetime import datetime
import time

from typing import Optional, Dict, Any, Union

from pyproj import Transformer
from .models import Field  # Assuming this is a Django/ORM model


class IntegratedSoilAnalyzer:
    def __init__(self, huggingface_token: Optional[str] = None):
        self.huggingface_token = huggingface_token or os.getenv("HUGGINGFACE_TOKEN")
        if not self.huggingface_token:
            raise ValueError("Hugging Face token is required")
            
        self.model_url = "https://api-inference.huggingface.co/models/tiiuae/falcon-7b-instruct"
        self.headers = {
            "Authorization": f"Bearer {self.huggingface_token}",
            "Content-Type": "application/json"
        }
        
        self.max_retries = 3
        self.retry_delay = 5
        self.last_request_time = None
        self.min_request_interval = 2
        
    def get_field_center(self, field_id: int) -> Dict[str, Any]:
        try:
            field = Field.objects.get(pk=field_id)
            transformer = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
            center = field.geometry.centroid
            lon, lat = transformer.transform(center.x, center.y)
            
            return {
                "lat": lat,
                "lon": lon,
                "name": field.name
            }
        except Field.DoesNotExist:
            raise ValueError(f"Field with ID {field_id} not found")
        except Exception as e:
            raise RuntimeError(f"Error retrieving field center: {e}")

    @staticmethod
    def get_soilgrid_data(lat: float, lon: float) -> Optional[pd.DataFrame]:
        url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
        params = {
            "lon": lon,
            "lat": lat,
            "property": [
                "bdod", "cec", "cfvo", "clay", "nitrogen", "ocd", 
                "ocs", "phh2o", "sand", "silt", "soc", 
                "wv0010", "wv0033", "wv1500"
            ],
            "depth": ["0-5cm", "0-30cm", "5-15cm", "15-30cm", "30-60cm"],
            "value": "mean"
        }
        
        try:
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            soil_data = {}
            for layer in data['properties']['layers']:
                soil_data[layer['name']] = layer['depths'][0]['values']['mean']
                
            return pd.DataFrame([soil_data])
            
        except requests.RequestException as e:
            print(f"SoilGrids API Error: {e}")
            return None

    def get_climate_data(self, lat: float, lon: float, days: int = 7) -> Optional[Dict[str, Any]]:
        base_url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": [
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation_probability",
                "wind_speed_10m",
                "wind_direction_10m",
                "weathercode"
            ],
            "daily": [
                "weathercode",
                "temperature_2m_max",
                "temperature_2m_min",
                "sunrise",
                "sunset",
                "precipitation_probability_max",
                "uv_index_max"
            ],
            "forecast_days": days,
            "timezone": "auto"
        }

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Climate API Error: {e}")
            return None

    @staticmethod
    def interpret_weather_code(code: int) -> str:
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with light hail",
            99: "Thunderstorm with heavy hail"
        }
        return weather_codes.get(code, "Unknown weather condition")

    @staticmethod
    def format_weather_predictions(predictions: Dict[str, Any]) -> None:
        """
        Format and print weather predictions in a readable format
        
        Args:
            predictions (dict): Weather predictions from Open-Meteo
        """
        if not predictions:
         
            return
        
        
        
        # Daily predictions
        for i in range(len(predictions['daily']['time'])):
            date = predictions['daily']['time'][i]
            max_temp = predictions['daily']['temperature_2m_max'][i]
            min_temp = predictions['daily']['temperature_2m_min'][i]
            weather_code = predictions['daily']['weathercode'][i]
            precip_prob = predictions['daily']['precipitation_probability_max'][i]
            uv_index = predictions['daily']['uv_index_max'][i]
            
            return {
                "date": date,
                "max_temp": max_temp,
                "min_temp": min_temp,
                "weather_code": weather_code,
                "precip_prob": precip_prob,
                "uv_index": uv_index
            }

    def analyze_combined_data(self, soil_data: Union[pd.DataFrame, Dict[str, Any], int], climate_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        # Handle field ID input
        if isinstance(soil_data, int):
            field_center = self.get_field_center(soil_data)
            soil_data = self.get_soilgrid_data(field_center['lat'], field_center['lon'])
            
            if soil_data is None:
                raise ValueError(f"Could not retrieve soil data for field ID {soil_data}")
        
        # Convert soil_data to DataFrame if it's a dictionary
        elif isinstance(soil_data, dict):
            soil_data = pd.DataFrame([soil_data])
        
        # Validate soil_data
        if not isinstance(soil_data, pd.DataFrame):
            raise ValueError(f"Invalid soil_data type: {type(soil_data)}. Expected pandas DataFrame, dictionary, or field ID.")
        
        if soil_data.empty:
            raise ValueError("Empty soil data provided")
        
        # Handle climate_data parsing
        if isinstance(climate_data, str):
            try:
                climate_data = json.loads(climate_data)
            except json.JSONDecodeError:
                climate_data = {"data": {"note": "No climate data available"}}
        
        if not isinstance(climate_data, dict):
            climate_data = {"data": {"note": "Invalid climate data format"}}
        
        # Ensure climate_data has the expected structure
        if "data" not in climate_data:
            climate_data = {"data": climate_data}
            
        combined_data = {
            "soil_properties": soil_data.to_dict(orient='records')[0],
            "climate_conditions": climate_data['data']
        }
        
        prompt = self._generate_analysis_prompt(combined_data)
        
        for retry in range(self.max_retries):
            try:
                self._handle_rate_limit()
                
                response = requests.post(
                    self.model_url,
                    headers=self.headers,
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": 1000,
                            "temperature": 0.7,
                            "top_p": 0.95,
                            "return_full_text": True
                        }
                    },
                    timeout=45
                )
                
                response.raise_for_status()
                analysis = self._extract_analysis(response.json())
                
                if not analysis.strip():
                    raise ValueError("Empty analysis received")
                
                return {
                    "success": True,
                    "model": "falcon-7b-instruct",
                    "analysis": analysis,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {"retries": retry}
                }
                
            except Exception as e:
                if retry == self.max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e),
                        "model": "falcon-7b-instruct",
                        "timestamp": datetime.now().isoformat(),
                        "metadata": {"retries": retry + 1}
                    }
                time.sleep(self.retry_delay * (2 ** retry))

    def _handle_rate_limit(self):
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = datetime.now()

    @staticmethod
    def _generate_analysis_prompt(combined_data: Dict[str, Any]) -> str:
        return f"""Based on the following soil data, provide specific crop recommendations:

Soil Properties:
{json.dumps(combined_data['soil_properties'], indent=2)}

Climate Conditions:
{json.dumps(combined_data['climate_conditions'], indent=2)}

Key soil parameters interpretation:
- Clay content ({combined_data['soil_properties'].get('clay', 'N/A')})
- Sand content ({combined_data['soil_properties'].get('sand', 'N/A')})
- pH (phh2o) ({combined_data['soil_properties'].get('phh2o', 'N/A')})
- CEC ({combined_data['soil_properties'].get('cec', 'N/A')})
- Nitrogen ({combined_data['soil_properties'].get('nitrogen', 'N/A')})
- Water retention (wv0033) ({combined_data['soil_properties'].get('wv0033', 'N/A')})

Based on these soil characteristics:
1. List the top 5 most suitable crops for this soil type
2. For each recommended crop, explain in depth why it's well-suited based on the specific soil values
3. Include any special management recommendations for the suggested crops

Focus on practical, actionable recommendations that consider both the soil's strengths and limitations."""

    @staticmethod
    def _extract_analysis(result: Any) -> str:
        if isinstance(result, list) and result:
            return result[0].get('generated_text', '')
        elif isinstance(result, dict):
            return result.get('generated_text', '')
        return str(result)