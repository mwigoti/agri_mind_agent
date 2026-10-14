import requests
import pandas as pd
import json
import os
from datetime import datetime
import time
import re
from typing import Any, Optional, Dict, Union
from dataclasses import dataclass, asdict

from pyproj import Transformer
from .models import Field  # Assuming this is a Django/ORM model


# ==================== SOIL DATA MODELS & PARSER ====================

@dataclass
class SoilDataSummary:
    """Compact summary of essential soil data for AI analysis"""

    # Physical Properties (%)
    sand: Optional[float] = None
    clay: Optional[float] = None
    silt: Optional[float] = None
    bulk_density: Optional[float] = None  # kg/m³

    # Chemical Properties
    ph: Optional[float] = None
    organic_carbon: Optional[float] = None  # %
    cec: Optional[float] = None  # cmolc/kg
    electrical_conductivity: Optional[float] = None  # dS/m

    # Nutrients (g/kg or mg/kg)
    total_nitrogen: Optional[float] = None
    total_phosphorus: Optional[float] = None
    total_potassium: Optional[float] = None
    exchangeable_potassium: Optional[float] = None
    phosphorus_olsen: Optional[float] = None

    # Water Properties
    water_capacity_pf2: Optional[float] = None
    water_capacity_pf2_5: Optional[float] = None
    wilting_point: Optional[float] = None
    plant_available_water: Optional[float] = None

    # Classification & Environment
    soil_type: Optional[str] = None
    climate_type: Optional[str] = None
    elevation: Optional[float] = None
    slope: Optional[float] = None

    # Biological
    microbial_abundance: Optional[float] = None
    macrofauna_groups: Optional[int] = None

    # Threats
    erosion_risk: Optional[str] = None
    soil_loss: Optional[float] = None
    desertification_vulnerability: Optional[str] = None

    # Climate Data
    annual_temperature: Optional[float] = None
    annual_precipitation: Optional[float] = None

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class SoilDataParser:
    """Parser for ISRIC soil data API"""

    ISRIC_API_URL = "https://isqaper.isric.org/isqaper-rest/api/1.0/query"

    @staticmethod
    def fetch_soil_data(lon: float, lat: float, timeout: int = 30) -> Optional[Dict]:
        """Fetch soil data from ISRIC API"""
        try:
            response = requests.get(
                f"{SoilDataParser.ISRIC_API_URL}?lon={lon}&lat={lat}", 
                timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("features"):
                print("No soil data available for this location.")
                return None
            return data
        except requests.RequestException as e:
            print(f"Error fetching soil data: {e}")
            return None

    @staticmethod
    def extract_value(data: Dict, *keys: str, default: Any = None) -> Any:
        """Safely extract nested dictionary values"""
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
                if current is None:
                    return default
            else:
                return default
        return current if current is not None else default

    def parse_soil_data(self, raw_data: Dict) -> SoilDataSummary:
        """Parse raw API response into structured summary"""
        feature = raw_data["features"][0]
        props = feature.get("properties", {}).get("properties", {})

        # Coordinates
        geom = feature.get("geometry", {}).get("coordinates", [])
        lon = geom[0] if len(geom) > 0 else None
        lat = geom[1] if len(geom) > 1 else None

        # Extract physical properties
        sand = self.extract_value(props, 'SNDPPT_M_sl1_250m_ll_0-30cm.tif', 'value')
        clay = self.extract_value(props, 'CLYPPT_M_sl1_250m_ll_0-30cm.tif', 'value')
        silt = self.extract_value(props, 'SLTPPT_M_sl1_250m_ll_0-30cm.tif', 'value')
        bulk_density = self.extract_value(props, 'BLDFIE_M_sl1_250m_ll_0-30cm.tif', 'value')

        # Chemical properties
        ph = self.extract_value(props, 'PHIHOX_M_sl1_250m_ll_by10_0-30cm.tif', 'value')
        organic_carbon = self.extract_value(props, 'ORCDRC_M_sl1_250m_ll_0-30cm.tif', 'value')
        cec = self.extract_value(props, 'CECSOL_M_sl1_250m_ll_0-30cm.tif', 'value')
        ec = self.extract_value(props, 'Electrical_conductivity_0-29cm_250m.tif', 'value')

        # Nutrients
        total_n = self.extract_value(props, 'Total_nitrogen_0-29cm_250m.tif', 'value')
        total_p = self.extract_value(props, 'Total_phosphorus_0-29cm_250m.tif', 'value')
        total_k = self.extract_value(props, 'Total_potassium_0-29cm_250m.tif', 'value')
        exch_k = self.extract_value(props, 'Exchangeable_potassium_0-29cm_250m.tif', 'value')
        p_olsen = self.extract_value(props, 'Phosphorus_Olsen_method_0-29cm_250m.tif', 'value')

        # Water
        water_pf2 = self.extract_value(props, 'AWCh1_M_sl1_250m_ll_pF2_0-30cm.tif', 'value')
        water_pf2_5 = self.extract_value(props, 'AWCh1_M_sl1_250m_ll_pF2.5_0-30cm.tif', 'value')
        wilting = self.extract_value(props, 'AWCh1_M_sl1_250m_ll_pF4.2_0-30cm.tif', 'value')
        plant_water = self.extract_value(props, 'Plant_available_water_storage_capacity_mm_in_depth_of_0-30_cm.tif', 'value')

        # Classification & climate
        classification = feature.get("properties", {}).get("classification", {})
        soil_type = self.extract_value(classification, 'TAXNWRB_250m_ll.tif', 'value')

        climate = feature.get("properties", {}).get("climate", {})
        climate_type = self.extract_value(climate, 'World_Koppen_250m.tif', 'value')

        # Geomorphology
        geomorph = feature.get("properties", {}).get("geomorphology", {})
        elevation = self.extract_value(geomorph, 'Altitude_asl_meter.tif', 'value')
        slope = self.extract_value(geomorph, 'Slope_percentage_gdal.tif', 'value')

        # Biological
        bio = feature.get("properties", {}).get("biological_properties", {})
        microbial = self.extract_value(bio, 'Global_estimates_of_soil_microbial_abundance.tif', 'value')
        macrofauna = self.extract_value(bio, 'Soil_macrofauna.tif', 'value')

        # Threats
        threats = feature.get("properties", {}).get("threats", {})
        soil_loss = self.extract_value(threats, 'RUSLE_Soil_Loss_2012_250m_mosaic.tif', 'value')
        desert_vuln = self.extract_value(threats, 'Global_desertification_vulnerability_reclassified.tif', 'value')
        erosion_class = self.extract_value(threats, 'RUSLE_Soil_Loss_2012_250m_mosaic_reclassified.tif', 'value')

        # Climate/Meteo
        meteo = feature.get("properties", {}).get("meteo", {})
        annual_temp = self.extract_value(meteo, 'Annual_mean_temperature_oC_250m.tif', 'value')
        annual_precip = self.extract_value(meteo, 'Annual_precipitation_mm.tif', 'value')

        return SoilDataSummary(
            sand=sand,
            clay=clay,
            silt=silt,
            bulk_density=bulk_density,
            ph=ph,
            organic_carbon=organic_carbon,
            cec=cec,
            electrical_conductivity=ec,
            total_nitrogen=total_n,
            total_phosphorus=total_p,
            total_potassium=total_k,
            exchangeable_potassium=exch_k,
            phosphorus_olsen=p_olsen,
            water_capacity_pf2=water_pf2,
            water_capacity_pf2_5=water_pf2_5,
            wilting_point=wilting,
            plant_available_water=plant_water,
            soil_type=soil_type,
            climate_type=climate_type,
            elevation=elevation,
            slope=slope,
            microbial_abundance=microbial,
            macrofauna_groups=macrofauna,
            erosion_risk=erosion_class,
            soil_loss=soil_loss,
            desertification_vulnerability=desert_vuln,
            annual_temperature=annual_temp,
            annual_precipitation=annual_precip,
            latitude=lat,
            longitude=lon
        )


# ==================== INTEGRATED SOIL ANALYZER ====================

class IntegratedSoilAnalyzer:
    """Main analyzer class that combines soil and climate data for AI analysis"""
    
    def __init__(self, huggingface_token: Optional[str] = None):
        self.huggingface_token = huggingface_token or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HF_TOKEN")
        if not self.huggingface_token:
            raise ValueError("Hugging Face token is required")
            
        # Use the correct HuggingFace chat completions endpoint
        self.model_url = "https://router.huggingface.co/together/v1/chat/completions"
        
        self.headers = {
            "Authorization": f"Bearer {self.huggingface_token}",
            "Content-Type": "application/json"
        }
        
        self.max_retries = 3
        self.retry_delay = 5
        self.last_request_time = None
        self.min_request_interval = 2
        
        # Initialize the soil data parser
        self.soil_parser = SoilDataParser()
        
    def get_field_center(self, field_id: int) -> Dict[str, Any]:
        """Get the center coordinates of a field from the database"""
        try:
            field = Field.objects.get(pk=field_id)
            center = field.geometry.centroid

            if field.geometry.srid != 4326:
                transformer = Transformer.from_crs(field.geometry.srid, 4326, always_xy=True)
                lon, lat = transformer.transform(center.x, center.y)
            else:
                lon, lat = center.x, center.y

            return {
                "lat": lat,  
                "lon": lon,
                "name": field.name
            }
        except Field.DoesNotExist:
            raise ValueError(f"Field with ID {field_id} not found")
    
    def get_isric_soil_data(self, lat: float, lon: float) -> Optional[Dict[str, Any]]:
        """
        Fetch and parse soil data from ISRIC API using the SoilDataParser.
        Returns a dictionary compatible with the existing analysis pipeline.
        """
        try:
            print(f"DEBUG: Fetching ISRIC soil data for lat={lat}, lon={lon}")
            
            # Fetch raw data from ISRIC
            raw_data = self.soil_parser.fetch_soil_data(lon, lat)
            
            if not raw_data:
                print("ERROR: No soil data returned from ISRIC")
                return None
            
            # Parse the data into structured format
            soil_summary = self.soil_parser.parse_soil_data(raw_data)
            
            # Convert to dictionary, filtering out None values
            soil_dict = {k: v for k, v in asdict(soil_summary).items() if v is not None}
            
            print(f"DEBUG: ISRIC soil data keys: {list(soil_dict.keys())}")
            print(f"DEBUG: Sample values - sand: {soil_dict.get('sand')}, clay: {soil_dict.get('clay')}, ph: {soil_dict.get('ph')}")
            
            return soil_dict
            
        except Exception as e:
            print(f"ERROR fetching ISRIC soil data: {e}")
            return None

    @staticmethod
    def get_climate_data(lat: float, lon: float, days: int = 7) -> Optional[Dict[str, Any]]:
        """Fetch weather forecast data from Open-Meteo API"""
        base_url = "https://api.open-meteo.com/v1/forecast"

        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": [
                "weathercode",
                "temperature_2m_max",
                "temperature_2m_min",
                "sunrise",
                "sunset",
                "precipitation_probability_max",
                "uv_index_max",
                "apparent_temperature_mean"
            ],
            "forecast_days": days,
            "timezone": "auto"
        }

        try:
            print(f"DEBUG: Requesting climate data for lat={lat}, lon={lon}")
            response = requests.get(base_url, params=params)
            print(f"DEBUG: Climate API response status: {response.status_code}")
            response.raise_for_status()
            data = response.json()
            print(f"DEBUG: Climate data keys: {data.keys()}")
            return data
        except requests.RequestException as e:
            print(f"Climate API Error: {e}")
            return None

    @staticmethod
    def interpret_weather_code(code: int) -> str:
        """Convert WMO weather code to human-readable description"""
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
            print("ERROR: No daily data in climate predictions")
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
            daily_data = predictions.get('daily', {})
            time_data = daily_data.get('time', [])
            
            if not time_data:
                print("ERROR: No time data in daily predictions")
                return processed
                
            print(f"DEBUG: Processing {len(time_data)} days of climate data")
            
            temps_max = []
            temps_min = []
            
            for i in range(len(time_data)):
                try:
                    daily_entry = {
                        "date": daily_data['time'][i],
                        "max_temp": float(daily_data['temperature_2m_max'][i]),
                        "min_temp": float(daily_data['temperature_2m_min'][i]),
                        "avg_temp": float(daily_data['apparent_temperature_mean'][i]),
                        "weather_condition": self.interpret_weather_code(
                            int(daily_data['weathercode'][i])
                        ),
                        "precip_prob": int(daily_data['precipitation_probability_max'][i]),
                        "uv_index": float(daily_data['uv_index_max'][i])
                    }
                    
                    temps_max.append(daily_entry['max_temp'])
                    temps_min.append(daily_entry['min_temp'])
                    
                    processed['summary']['temp_range'].extend([daily_entry['max_temp'], daily_entry['min_temp']])
                    if daily_entry['precip_prob'] > 40:
                        processed['summary']['precipitation_days'] += 1
                    processed['summary']['weather_types'][daily_entry['weather_condition']] = \
                        processed['summary']['weather_types'].get(daily_entry['weather_condition'], 0) + 1
                    
                    processed['daily_details'].append(daily_entry)
                    
                except (KeyError, IndexError, ValueError) as e:
                    print(f"ERROR processing day {i}: {e}")
                    continue
            
            # Calculate averages
            if temps_max:
                processed['summary']['avg_max_temp'] = sum(temps_max) / len(temps_max)
            if temps_min:
                processed['summary']['avg_min_temp'] = sum(temps_min) / len(temps_min)
                
            # Find dominant weather
            if processed['summary']['weather_types']:
                processed['summary']['dominant_weather'] = max(
                    processed['summary']['weather_types'], 
                    key=processed['summary']['weather_types'].get
                )
            
            print(f"DEBUG: Processed climate summary: {processed['summary']}")

        except (KeyError, IndexError, TypeError) as e:
            print(f"Error processing climate data: {e}")
        
        return processed

    def analyze_combined_data(self, soil_data: Union[pd.DataFrame, Dict[str, Any], int], 
                             climate_data: Union[Dict[str, Any], str, int] = None) -> Dict[str, Any]:
        """
        Analyze combined soil and climate data using AI.
        
        Args:
            soil_data: Can be a field ID (int), DataFrame, or dictionary
            climate_data: Climate data as dict, JSON string, or None (will be fetched if soil_data is field ID)
            
        Returns:
            Dictionary containing analysis results and metadata
        """
        print(f"DEBUG: Starting analysis with soil_data type: {type(soil_data)}, climate_data type: {type(climate_data)}")
        
        # Store original field ID if provided
        field_id = soil_data if isinstance(soil_data, int) else None
        
        # Process input data - if field ID, fetch soil and climate data
        if isinstance(soil_data, int):
            print(f"DEBUG: Processing field ID: {soil_data}")
            field_center = self.get_field_center(soil_data)
            
            # Fetch ISRIC soil data
            soil_dict = self.get_isric_soil_data(field_center['lat'], field_center['lon'])
            if soil_dict is None:
                return {
                    "success": False,
                    "error": f"Could not retrieve ISRIC soil data for field ID {field_id}",
                    "timestamp": datetime.now().isoformat()
                }
            # Convert to DataFrame for consistency with existing code
            soil_data = pd.DataFrame([soil_dict])
            
            # Get climate data (ignore climate_data parameter when field_id is provided)
            raw_climate = self.get_climate_data(field_center['lat'], field_center['lon'])
            if raw_climate is None:
                return {
                    "success": False,
                    "error": f"Could not retrieve climate data for field ID {field_id}",
                    "timestamp": datetime.now().isoformat()
                }
                
            climate_data = self.format_weather_predictions(raw_climate)
        
        elif isinstance(soil_data, dict):
            # Convert dict to DataFrame
            soil_data = pd.DataFrame([soil_data])
        
        # Validate soil_data is now a DataFrame
        if not isinstance(soil_data, pd.DataFrame):
            return {
                "success": False,
                "error": f"Invalid soil_data type: {type(soil_data)}. Expected pandas DataFrame, dictionary, or field ID.",
                "timestamp": datetime.now().isoformat()
            }
        
        if soil_data.empty:
            return {
                "success": False,
                "error": "Empty soil data provided",
                "timestamp": datetime.now().isoformat()
            }
        
        # Process climate data
        if isinstance(climate_data, str):
            try:
                climate_data = json.loads(climate_data)
            except json.JSONDecodeError:
                climate_data = {"summary": {"note": "No climate data available"}}
        
        if not isinstance(climate_data, dict):
            climate_data = {"summary": {"note": "Invalid climate data format"}}
        
        # Ensure proper structure
        if "summary" not in climate_data and "daily_details" not in climate_data:
            climate_data = {"summary": climate_data}
            
        combined_data = {
            "soil_properties": soil_data.to_dict(orient='records')[0],
            "climate_conditions": climate_data
        }
        
        print(f"DEBUG: Combined data - soil keys: {list(combined_data['soil_properties'].keys())}")
        print(f"DEBUG: Combined data - climate keys: {list(combined_data['climate_conditions'].keys())}")
        
        # Create a concise prompt to reduce token count
        prompt = self._generate_concise_prompt(combined_data)
        print(f"DEBUG: Generated prompt length: {len(prompt)} characters")
        
        # Retry loop for API calls
        for retry in range(self.max_retries):
            try:
                print(f"DEBUG: Attempt {retry + 1} of {self.max_retries}")
                self._handle_rate_limit()
                
                # Use the correct chat completions format
                payload = {
                    "messages": [
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "model": "Qwen/Qwen2.5-7B-Instruct-Turbo",
                    "max_tokens": 1000,
                    "temperature": 0.7,
                    "top_p": 0.95
                }
                
                response = requests.post(
                    self.model_url,
                    headers=self.headers,
                    json=payload,
                    timeout=90
                )
                
                print(f"DEBUG: HuggingFace API response status: {response.status_code}")
                
                # Handle potential errors
                if response.status_code != 200:
                    error_msg = f"API Error: {response.status_code} - {response.text}"
                    print(error_msg)
                    if retry == self.max_retries - 1:
                        return {
                            "success": False,
                            "error": error_msg,
                            "model": "Qwen/Qwen2.5-7B-Instruct-Turbo",
                            "timestamp": datetime.now().isoformat(),
                            "metadata": {"retries": retry + 1}
                        }
                    time.sleep(self.retry_delay * (2 ** retry))
                    continue
                    
                # Process the response
                response_data = response.json()
                print(f"DEBUG: Raw API response type: {type(response_data)}")
                print(f"DEBUG: Raw API response preview: {str(response_data)[:500]}...")
                
                analysis = DataExtractor.extract_analysis(response_data)
                print(f"DEBUG: Extracted analysis length: {len(analysis)} characters")
                
                if not analysis.strip():
                    print("ERROR: Empty analysis received. Retrying...")
                    if retry == self.max_retries - 1:
                        return {
                            "success": False,
                            "error": "Empty analysis received from API",
                            "model": "Qwen/Qwen2.5-7B-Instruct-Turbo",
                            "timestamp": datetime.now().isoformat(),
                            "metadata": {"retries": retry + 1, "raw_response": response_data}
                        }
                    time.sleep(self.retry_delay * (2 ** retry))
                    continue
                
                return {
                    "success": True,
                    "model": "Qwen/Qwen2.5-7B-Instruct-Turbo",
                    "analysis": analysis,
                    "timestamp": datetime.now().isoformat(),
                    "metadata": {"retries": retry, "data_source": "ISRIC"}
                }
                
            except Exception as e:
                print(f"Exception during API request: {str(e)}")
                if retry == self.max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e),
                        "model": "Qwen/Qwen2.5-7B-Instruct-Turbo",
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
        """Generate a concise prompt to reduce token usage"""
        try:
            area = Field.area if hasattr(Field, 'area') else "N/A"
        except:
            area = "N/A"
            
        soil = combined_data['soil_properties']
        climate = combined_data['climate_conditions'].get('summary', {})
        
        # Create soil string using ISRIC data format
        soil_str = f"SOIL: sand:{soil.get('sand', 'N/A')}%, clay:{soil.get('clay', 'N/A')}%, "
        soil_str += f"silt:{soil.get('silt', 'N/A')}%, pH:{soil.get('ph', 'N/A')}, "
        soil_str += f"CEC:{soil.get('cec', 'N/A')} cmolc/kg, "
        soil_str += f"organic_carbon:{soil.get('organic_carbon', 'N/A')}%, "
        soil_str += f"N:{soil.get('total_nitrogen', 'N/A')} g/kg, "
        soil_str += f"P:{soil.get('total_phosphorus', 'N/A')} g/kg, "
        soil_str += f"K:{soil.get('total_potassium', 'N/A')} g/kg, "
        soil_str += f"plant_water:{soil.get('plant_available_water', 'N/A')} mm, "
        soil_str += f"soil_type:{soil.get('soil_type', 'N/A')}"
        
        # Get climate summary with null checks
        temp_max = climate.get('avg_max_temp')
        temp_min = climate.get('avg_min_temp')
        temp_str = f"Temp:{temp_max:.1f}°C max, {temp_min:.1f}°C min" if temp_max and temp_min else "Temp: Unknown"
        precip = climate.get('precipitation_days', 0)
        weather = climate.get('dominant_weather', 'Unknown')
        
        print(f"DEBUG: Soil string: {soil_str}")
        print(f"DEBUG: Climate string: {temp_str}, Precip: {precip}, Weather: {weather}")
        
        # Create prompt
        return f"""As an agricultural expert, analyze these field conditions and provide recommendations:

{soil_str}
Field Area: {area}

CLIMATE: {temp_str}, Precipitation days: {precip}, Pattern: {weather}

Provide:
1. Top 5 suitable crops with soil-climate synergies for each and based on area {area} provide yield estimation
2. Climate risks and mitigations
3. Planting timing recommendations
4. Irrigation strategy based on water retention and precipitation

Keep analysis CONCISE and practical for sustainable farming."""


# ==================== DATA EXTRACTOR ====================

class DataExtractor:
    """Utility class for extracting and parsing data from various sources"""
    
    @staticmethod
    def extract_analysis(result: Any) -> str:
        """Extract and clean analysis from HuggingFace chat completions response"""
        print(f"DEBUG: Extracting analysis from result type: {type(result)}")
        raw_text = ''
        
        # Handle the chat completions response format
        if isinstance(result, dict):
            if 'choices' in result and result['choices']:
                choice = result['choices'][0]
                if 'message' in choice:
                    raw_text = choice['message'].get('content', '')
                elif 'text' in choice:
                    raw_text = choice['text']
            elif 'generated_text' in result:
                raw_text = result['generated_text']
            elif 'content' in result:
                raw_text = result['content']
        elif isinstance(result, list) and result:
            if isinstance(result[0], dict):
                if 'generated_text' in result[0]:
                    raw_text = result[0]['generated_text']
                elif 'message' in result[0]:
                    raw_text = result[0]['message'].get('content', '')
                else:
                    raw_text = str(result[0])
            else:
                raw_text = str(result)
        
        # Clean up unwanted characters like '#' and '*'
        cleaned_text = re.sub(r'[#*]', '', raw_text)
        return cleaned_text.strip()

    @staticmethod
    def extract_soil_data(analysis_text: str) -> Dict[str, Optional[float]]:
        """Extract soil composition and nutrient data from analysis text using regex"""
        if not analysis_text:
            return {}
        
        text = analysis_text.lower()
        extracted_data = {}
        
        patterns = {
            'sand': [
                r'sand[:\s]*(\d+\.?\d*)%?',
                r'sand\s*content[:\s]*(\d+\.?\d*)%?',
                r'(\d+\.?\d*)%?\s*sand',
                r'-\s*sand[:\s]*(\d+\.?\d*)%?'
            ],
            'clay': [
                r'clay[:\s]*(\d+\.?\d*)%?',
                r'clay\s*content[:\s]*(\d+\.?\d*)%?',
                r'(\d+\.?\d*)%?\s*clay',
                r'-\s*clay[:\s]*(\d+\.?\d*)%?'
            ],
            'silt': [
                r'silt[:\s]*(\d+\.?\d*)%?',
                r'silt\s*content[:\s]*(\d+\.?\d*)%?',
                r'(\d+\.?\d*)%?\s*silt',
                r'-\s*silt[:\s]*(\d+\.?\d*)%?'
            ],
            'ph': [
                r'ph[:\s]*(\d+\.?\d*)',
                r'ph\s*level[:\s]*(\d+\.?\d*)',
                r'acidity[:\s]*(\d+\.?\d*)',
                r'alkalinity[:\s]*(\d+\.?\d*)'
            ],
            'nitrogen': [
                r'nitrogen[:\s]*(\d+\.?\d*)',
                r'n[:\s]*(\d+\.?\d*)\s*(?:ppm|mg/kg|%)',
                r'total\s*nitrogen[:\s]*(\d+\.?\d*)',
                r'-\s*nitrogen[:\s]*(\d+\.?\d*)'
            ],
            'organic_carbon': [
                r'organic\s*carbon[:\s]*(\d+\.?\d*)%?',
                r'soc[:\s]*(\d+\.?\d*)%?',
                r'carbon\s*content[:\s]*(\d+\.?\d*)%?',
                r'organic\s*matter[:\s]*(\d+\.?\d*)%?'
            ],
            'cec': [
                r'cec[:\s]*(\d+\.?\d*)',
                r'cation\s*exchange\s*capacity[:\s]*(\d+\.?\d*)',
                r'exchange\s*capacity[:\s]*(\d+\.?\d*)'
            ],
            'phosphorus': [
                r'phosphorus[:\s]*(\d+\.?\d*)',
                r'p[:\s]*(\d+\.?\d*)\s*(?:ppm|mg/kg)',
                r'available\s*phosphorus[:\s]*(\d+\.?\d*)'
            ],
            'potassium': [
                r'potassium[:\s]*(\d+\.?\d*)',
                r'k[:\s]*(\d+\.?\d*)\s*(?:ppm|mg/kg)',
                r'available\s*potassium[:\s]*(\d+\.?\d*)'
            ]
        }
        
        for data_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text)
                if match:
                    try:
                        extracted_data[data_type] = float(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue
        
        return extracted_data

    @staticmethod
    def extract_climate_data(analysis_text: str) -> Dict[str, Optional[float]]:
        """Extract climate data from analysis text using regex"""
        if not analysis_text:
            return {}
        
        text = analysis_text.lower()
        extracted_data = {}
        
        patterns = {
            'avg_temp': [
                r'average\s*temperature[:\s]*(\d+\.?\d*)',
                r'mean\s*temperature[:\s]*(\d+\.?\d*)',
                r'temp[:\s]*(\d+\.?\d*)°?c'
            ],
            'max_temp': [
                r'maximum\s*temperature[:\s]*(\d+\.?\d*)',
                r'max\s*temp[:\s]*(\d+\.?\d*)°?c',
                r'highest\s*temperature[:\s]*(\d+\.?\d*)'
            ],
            'min_temp': [
                r'minimum\s*temperature[:\s]*(\d+\.?\d*)',
                r'min\s*temp[:\s]*(\d+\.?\d*)°?c',
                r'lowest\s*temperature[:\s]*(\d+\.?\d*)'
            ],
            'rainfall': [
                r'rainfall[:\s]*(\d+\.?\d*)',
                r'precipitation[:\s]*(\d+\.?\d*)',
                r'annual\s*rainfall[:\s]*(\d+\.?\d*)',
                r'rain[:\s]*(\d+\.?\d*)\s*mm'
            ],
            'humidity': [
                r'humidity[:\s]*(\d+\.?\d*)%?',
                r'relative\s*humidity[:\s]*(\d+\.?\d*)%?'
            ]
        }
        
        for data_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text)
                if match:
                    try:
                        extracted_data[data_type] = float(match.group(1))
                        break
                    except (ValueError, IndexError):
                        continue
        
        return extracted_data

    @staticmethod
    def extract_recommendations(analysis_text: str) -> str:
        """Extract recommendations section from analysis text"""
        if not analysis_text:
            return ''
        
        # Split into lines for processing
        lines = analysis_text.split('\n')
        recommendations = []
        in_recommendations_section = False
        
        # Pattern matching for recommendation sections
        recommendation_indicators = [
            r'^1\.\s*top\s*\d+\s*suitable\s*crops',
            r'^2\.\s*climate\s*risks',
            r'^3\.\s*planting\s*timing',
            r'^4\.\s*irrigation\s*strategy',
            r'recommendations?:',
            r'suggested?\s*crops?:',
            r'best\s*practices?:'
        ]
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if this line starts a recommendations section
            for pattern in recommendation_indicators:
                if re.match(pattern, line_lower):
                    in_recommendations_section = True
                    recommendations.append(line)
                    break
            else:
                if in_recommendations_section:
                    # Continue adding lines until we hit a clear section break
                    if line.strip() == '' and len(recommendations) > 5:
                        # Stop if we hit multiple empty lines (likely end of section)
                        break
                    recommendations.append(line)
        
        return '\n'.join(recommendations)


# ==================== UTILITY FUNCTION ====================

def process_analysis_data(analysis_text: str) -> Dict[str, Any]:
    """
    Complete function to extract all relevant data from analysis text
    
    Args:
        analysis_text: Raw analysis text from AI model
        
    Returns:
        Dictionary containing extracted soil data, climate data, and recommendations
    """
    extractor = DataExtractor()
    
    # Extract soil data
    soil_data = extractor.extract_soil_data(analysis_text)
    
    # Extract climate data
    climate_data = extractor.extract_climate_data(analysis_text)
    
    # Extract recommendations
    recommendations = extractor.extract_recommendations(analysis_text)
    
    return {
        'soil_properties': soil_data,
        'climate_conditions': climate_data,
        'recommendations': recommendations,
        'raw_analysis': analysis_text
    }