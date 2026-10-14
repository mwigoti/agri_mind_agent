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
    @staticmethod
    def get_climate_data(lat: float, lon: float, days: int = 7) -> Optional[Dict[str, Any]]:
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

    
    def format_weather_predictions(self, predictions: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw climate API response into structured format."""
        if not predictions or 'daily' not in predictions:
            return {}

        processed = {
            "summary": {
                "temp_range": [],
                "precipitation_days": 0,
                "weather_types": {},
                "avg_max_temp": None,
                "avg_min_temp": None,
                "dominant_weather": None
            },
            "daily_details": []
        }

        try:
            # Process daily data with proper type checking
            daily_data = predictions.get('daily', {})
            for i in range(len(daily_data.get('time', []))):
                daily_entry = {
                    "date": daily_data['time'][i],
                    "max_temp": float(daily_data['temperature_2m_max'][i]),
                    "min_temp": float(daily_data['temperature_2m_min'][i]),
                    "weather_condition": self.interpret_weather_code(
                        int(daily_data['weathercode'][i])
                    ),
                    "precip_prob": int(daily_data['precipitation_probability_max'][i]),
                    "uv_index": float(daily_data['uv_index_max'][i])
                }
                
                # Update summary
                processed['summary']['temp_range'].extend([daily_entry['max_temp'], daily_entry['min_temp']])
                if daily_entry['precip_prob'] > 40:
                    processed['summary']['precipitation_days'] += 1
                processed['summary']['weather_types'][daily_entry['weather_condition']] = processed['summary']['weather_types'].get(daily_entry['weather_condition'], 0) + 1
                
                processed['daily_details'].append(daily_entry)

            # Calculate averages only if data exists
            if processed['daily_details']:
                processed['summary']['avg_max_temp'] = round(
                    sum(d['max_temp'] for d in processed['daily_details']) / len(processed['daily_details']), 1
                )
                processed['summary']['avg_min_temp'] = round(
                    sum(d['min_temp'] for d in processed['daily_details']) / len(processed['daily_details']), 1
                )
                processed['summary']['dominant_weather'] = max(
                    processed['summary']['weather_types'].items(),
                    key=lambda x: x[1],
                    default=("Unknown", 0)
                )[0]

        except (KeyError, IndexError, TypeError) as e:
            print(f"Error processing climate data: {e}")
        
            return processed



    def analyze_combined_data(self, soil_data: Union[pd.DataFrame, Dict[str, Any], int], climate_data: Union[Dict[str, Any], str]) -> Dict[str, Any]:
        # Process input data (keeping this part the same)
        if isinstance(soil_data, int):
            field_center = self.get_field_center(soil_data)
            soil_data = self.get_soilgrid_data(field_center['lat'], field_center['lon'])
            climate_data = {"data": self.format_weather_predictions(climate_data)}
            if soil_data is None:
                raise ValueError(f"Could not retrieve soil data for field ID {soil_data}")
        
        elif isinstance(soil_data, dict):
            soil_data = pd.DataFrame([soil_data])
        
        if not isinstance(soil_data, pd.DataFrame):
            raise ValueError(f"Invalid soil_data type: {type(soil_data)}. Expected pandas DataFrame, dictionary, or field ID.")
        
        if soil_data.empty:
            raise ValueError("Empty soil data provided")
        
        if isinstance(climate_data, str):
            try:
                climate_data = json.loads(climate_data)
            except json.JSONDecodeError:
                climate_data = {"data": {"note": "No climate data available"}}
        
        if not isinstance(climate_data, dict):
            climate_data = {"data": {"note": "Invalid climate data format"}}
        
        if "data" not in climate_data:
            climate_data = {"data": climate_data}
            
        combined_data = {
            "soil_properties": soil_data.to_dict(orient='records')[0],
            "climate_conditions": climate_data['data']
        }
        
        # Create a more concise prompt to reduce token count
        prompt = self._generate_concise_prompt(combined_data)
        
        for retry in range(self.max_retries):
            try:
                self._handle_rate_limit()
                
                # First check if the model is ready to process
                check_response = requests.get(
                    self.model_url,
                    headers=self.headers
                )
                
                # If model is loading, wait before sending the actual request
                if check_response.status_code == 503:
                    estimated_time = check_response.json().get('estimated_time', 20)
                    print(f"Model loading. Waiting {estimated_time} seconds...")
                    time.sleep(estimated_time)
                
                # Send the actual inference request
                response = requests.post(
                    self.model_url,
                    headers=self.headers,
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": 1000,
                            "temperature": 0.7,
                            "top_p": 0.95,
                            "return_full_text": False,
                            "use_cache": True  # Enable caching to speed up repeated requests
                        },
                        "options": {
                            "wait_for_model": True  # Wait if model is loading
                        }
                    },
                    timeout=90  # Increased timeout
                )
                
                # Handle potential errors
                if response.status_code != 200:
                    error_msg = f"API Error: {response.status_code} - {response.text}"
                    print(error_msg)
                    if retry == self.max_retries - 1:
                        return {
                            "success": False,
                            "error": error_msg,
                            "model": "falcon-7b-instruct",
                            "timestamp": datetime.now().isoformat(),
                            "metadata": {"retries": retry + 1}
                        }
                    time.sleep(self.retry_delay * (2 ** retry))
                    continue
                    
                # Process the response
                response_data = response.json()
                
                # Debug the raw response if needed
                print(f"Raw API response: {json.dumps(response_data)[:200]}...")
                
                analysis = self._extract_analysis(response_data)
                
                if not analysis.strip():
                    print("Empty analysis received. Retrying...")
                    if retry == self.max_retries - 1:
                        return {
                            "success": False,
                            "error": "Empty analysis received from API",
                            "model": "falcon-7b-instruct",
                            "timestamp": datetime.now().isoformat(),
                            "metadata": {"retries": retry + 1}
                        }
                    time.sleep(self.retry_delay * (2 ** retry))
                    continue
                
                return {
                    "success": True,
                    "model": "falcon-7b-instruct",
                    "analysis": analysis,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {"retries": retry}
                }
                
            except Exception as e:
                print(f"Exception during API request: {str(e)}")
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
        """
        Handles rate limiting for API requests.
        Ensures that consecutive requests are separated by at least self.min_request_interval seconds.
        """
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.min_request_interval:
                time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = datetime.now()

    def _generate_concise_prompt(self, combined_data: Dict[str, Any]) -> str:
        """Generate a more concise prompt to reduce token usage"""
        soil = combined_data['soil_properties']
        climate = combined_data['climate_conditions'].get('summary', {})
        
        # Create a simpler representation of soil data
        soil_str = f"SOIL: sand:{soil.get('sand')}, clay:{soil.get('clay')}, pH:{soil.get('phh2o')}, "
        soil_str += f"CEC:{soil.get('cec')}, nitrogen:{soil.get('nitrogen')}, organic carbon:{soil.get('soc')}, "
        soil_str += f"water retention (3 levels): {soil.get('wv0010')}, {soil.get('wv0033')}, {soil.get('wv1500')}"
        
        # Get climate summary
        temp_max = climate.get('avg_max_temp')
        temp_min = climate.get('avg_min_temp')
        temp_str = f"Temp:{temp_max}°C max, {temp_min}°C min" if temp_max and temp_min else "Temp: Unknown"
        precip = climate.get('precipitation_days', 0)
        weather = climate.get('dominant_weather', 'Unknown')
        
        # Create prompt
        return f"""As an agricultural expert, analyze these field conditions and provide recommendations:

    {soil_str}

    CLIMATE: {temp_str}, Precipitation days: {precip}, Pattern: {weather}

    Provide:
    1. Top 5 suitable crops with soil-climate synergies for each
    2. Climate risks and mitigations
    3. Planting timing recommendations
    4. Irrigation strategy based on water retention and precipitation

    Keep analysis concise and practical for sustainable farming."""
            
    @staticmethod
    def _extract_analysis(result: Any) -> str:
        if isinstance(result, list) and result:
            return result[0].get('generated_text', '')
        elif isinstance(result, dict):
            return result.get('generated_text', '')
        return str(result)