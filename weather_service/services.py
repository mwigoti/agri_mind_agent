import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from django.utils import timezone
from datetime import datetime, timedelta
from .models import WeatherForecast, WeatherAlert
import logging

logger = logging.getLogger(__name__)

class WeatherService:
    """Main weather service orchestrator"""
    
    def __init__(self):
        self.providers = {
            'meteomatics': MeteomaticsClient(),
            'openweather': OpenWeatherClient(),
        }
        self.default_provider = 'openweather'
    
    def get_current_weather(self, location):
        """Get current weather for a location"""
        try:
            provider = self.providers[self.default_provider]
            return provider.get_current_weather(location)
        except Exception as e:
            logger.error(f"Failed to get current weather: {e}")
            # Fallback to cached data
            return self._get_cached_weather(location, timezone.now().date())
    
    def get_forecast(self, location, date, provider=None):
        """Get weather forecast for specific date"""
        if provider is None:
            provider = self.default_provider
        
        # Check cache first
        cached = self._get_cached_weather(location, date)
        if cached and self._is_cache_fresh(cached):
            return cached
        
        try:
            weather_client = self.providers[provider]
            forecast_data = weather_client.get_forecast(location, date)
            
            # Cache the result
            self._cache_forecast(location, date, forecast_data, provider)
            
            return forecast_data
        except Exception as e:
            logger.error(f"Failed to get forecast from {provider}: {e}")
            return cached or {}
    
    def get_multi_day_forecast(self, location, days=7, provider=None):
        """Get multi-day forecast"""
        forecasts = []
        start_date = timezone.now().date()
        
        for i in range(days):
            date = start_date + timedelta(days=i)
            forecast = self.get_forecast(location, date, provider)
            if forecast:
                forecast['date'] = date
                forecasts.append(forecast)
        
        return forecasts
    
    def check_agricultural_suitability(self, location, date, activity_type):
        """Check weather suitability for specific agricultural activities"""
        forecast = self.get_forecast(location, date)
        if not forecast:
            return {'suitable': False, 'reason': 'Weather data unavailable'}
        
        suitability_rules = {
            'spraying': {
                'max_wind_speed': 15,  # km/h
                'max_rain_probability': 30,  # %
                'min_temperature': 5,  # °C
                'max_temperature': 35,  # °C
            },
            'harvesting': {
                'max_rain_probability': 20,
                'max_wind_speed': 25,
            },
            'planting': {
                'max_wind_speed': 20,
                'min_temperature': 8,
                'max_temperature': 30,
                'max_rain_probability': 50,
            },
            'irrigation': {
                'max_rain_probability': 40,
            }
        }
        
        rules = suitability_rules.get(activity_type, {})
        warnings = []
        
        # Check each condition
        if 'max_wind_speed' in rules and forecast.get('wind_speed', 0) > rules['max_wind_speed']:
            warnings.append(f"Wind too strong: {forecast['wind_speed']} km/h")
        
        if 'max_rain_probability' in rules and forecast.get('precipitation_probability', 0) > rules['max_rain_probability']:
            warnings.append(f"Rain likely: {forecast['precipitation_probability']}%")
        
        if 'min_temperature' in rules and forecast.get('min_temperature', 20) < rules['min_temperature']:
            warnings.append(f"Temperature too low: {forecast['min_temperature']}°C")
        
        if 'max_temperature' in rules and forecast.get('max_temperature', 20) > rules['max_temperature']:
            warnings.append(f"Temperature too high: {forecast['max_temperature']}°C")
        
        return {
            'suitable': len(warnings) == 0,
            'warnings': warnings,
            'forecast': forecast
        }
    
    def _get_cached_weather(self, location, date):
        """Get cached weather data"""
        try:
            forecast = WeatherForecast.objects.filter(
                location__distance_lte=(location, 5000),  # Within 5km
                forecast_date=date
            ).order_by('created_at').last()
            
            if forecast:
                return {
                    'temperature': forecast.temperature,
                    'min_temp': forecast.min_temperature,
                    'max_temp': forecast.max_temperature,
                    'precipitation': forecast.precipitation,
                    'precipitation_probability': forecast.precipitation_probability,
                    'humidity': forecast.humidity,
                    'wind_speed': forecast.wind_speed,
                    'wind_direction': forecast.wind_direction,
                    'pressure': forecast.pressure,
                    'weather_condition': forecast.weather_condition,
                    'uv_index': forecast.uv_index,
                    'cloud_cover': forecast.cloud_cover,
                }
        except Exception as e:
            logger.error(f"Error getting cached weather: {e}")
        
        return None
    
    def _is_cache_fresh(self, cached_data, max_age_hours=6):
        """Check if cached data is still fresh"""
        if isinstance(cached_data, dict):
            return True  # Assume fresh if it's processed dict
        
        if hasattr(cached_data, 'updated_at'):
            age = timezone.now() - cached_data.updated_at
            return age.total_seconds() < (max_age_hours * 3600)
        
        return False
    
    def _cache_forecast(self, location, date, forecast_data, provider):
        """Cache forecast data"""
        try:
            WeatherForecast.objects.update_or_create(
                location=location,
                forecast_date=date,
                provider=provider,
                defaults={
                    'temperature': forecast_data.get('temperature'),
                    'min_temperature': forecast_data.get('min_temp'),
                    'max_temperature': forecast_data.get('max_temp'),
                    'precipitation': forecast_data.get('precipitation', 0),
                    'precipitation_probability': forecast_data.get('precipitation_probability', 0),
                    'humidity': forecast_data.get('humidity'),
                    'wind_speed': forecast_data.get('wind_speed'),
                    'wind_direction': forecast_data.get('wind_direction'),
                    'pressure': forecast_data.get('pressure'),
                    'weather_condition': forecast_data.get('weather_condition', ''),
                    'weather_description': forecast_data.get('description', ''),
                    'uv_index': forecast_data.get('uv_index'),
                    'cloud_cover': forecast_data.get('cloud_cover'),
                }
            )
        except Exception as e:
            logger.error(f"Error caching forecast: {e}")

class OpenWeatherClient:
    """OpenWeatherMap API client"""
    
    def __init__(self):
        self.api_key = settings.WEATHER_API_SETTINGS['OPENWEATHER']['API_KEY']
        self.base_url = settings.WEATHER_API_SETTINGS['OPENWEATHER']['BASE_URL']
    
    def get_current_weather(self, location):
        """Get current weather from OpenWeatherMap"""
        url = f"{self.base_url}/weather"
        params = {
            'lat': location.y,
            'lon': location.x,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        return self._parse_current_weather(data)
    
    def get_forecast(self, location, date):
        """Get forecast for specific date"""
        url = f"{self.base_url}/forecast"
        params = {
            'lat': location.y,
            'lon': location.x,
            'appid': self.api_key,
            'units': 'metric'
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Find forecast for the specific date
        target_date = date.strftime('%Y-%m-%d')
        for item in data['list']:
            forecast_date = datetime.fromtimestamp(item['dt']).strftime('%Y-%m-%d')
            if forecast_date == target_date:
                return self._parse_forecast_item(item)
        
        return {}
    
    def _parse_current_weather(self, data):
        """Parse OpenWeather current weather response"""
        return {
            'temperature': data['main']['temp'],
            'min_temp': data['main']['temp_min'],
            'max_temp': data['main']['temp_max'],
            'humidity': data['main']['humidity'],
            'pressure': data['main']['pressure'],
            'wind_speed': data.get('wind', {}).get('speed', 0) * 3.6,  # Convert m/s to km/h
            'wind_direction': data.get('wind', {}).get('deg'),
            'weather_condition': data['weather'][0]['main'].lower(),
            'description': data['weather'][0]['description'],
            'cloud_cover': data.get('clouds', {}).get('all', 0),
            'precipitation': data.get('rain', {}).get('1h', 0) + data.get('snow', {}).get('1h', 0),
        }
    
    def _parse_forecast_item(self, item):
        """Parse individual forecast item"""
        return {
            'temperature': item['main']['temp'],
            'min_temp': item['main']['temp_min'],
            'max_temp': item['main']['temp_max'],
            'humidity': item['main']['humidity'],
            'pressure': item['main']['pressure'],
            'wind_speed': item.get('wind', {}).get('speed', 0) * 3.6,
            'wind_direction': item.get('wind', {}).get('deg'),
            'weather_condition': item['weather'][0]['main'].lower(),
            'description': item['weather'][0]['description'],
            'precipitation_probability': item.get('pop', 0) * 100,  # Convert to percentage
            'cloud_cover': item.get('clouds', {}).get('all', 0),
            'precipitation': item.get('rain', {}).get('3h', 0) + item.get('snow', {}).get('3h', 0),
        }

class MeteomaticsClient:
    """Meteomatics API client for more detailed agricultural weather"""
    
    def __init__(self):
        self.username = settings.WEATHER_API_SETTINGS['METEOMATICS']['USERNAME']
        self.password = settings.WEATHER_API_SETTINGS['METEOMATICS']['PASSWORD']
        self.base_url = settings.WEATHER_API_SETTINGS['METEOMATICS']['BASE_URL']
    
    def get_current_weather(self, location):
        """Get current weather from Meteomatics"""
        now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        params = [
            't_2m:C',  # Temperature
            'relative_humidity_2m:p',  # Humidity
            'wind_speed_10m:kmh',  # Wind speed
            'wind_dir_10m:d',  # Wind direction
            'precip_1h:mm',  # Precipitation
            'msl_pressure:hPa',  # Pressure
        ]
        
        coordinates = f"{location.y},{location.x}"
        url = f"{self.base_url}/{now}/{','.join(params)}/{coordinates}/json"
        
        response = requests.get(
            url,
            auth=(self.username, self.password),
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        return self._parse_meteomatics_data(data)
    
    def get_forecast(self, location, date):
        """Get forecast from Meteomatics"""
        date_str = date.strftime('%Y-%m-%dT12:00:00Z')  # Noon forecast
        params = [
            't_2m:C', 't_min_2m_24h:C', 't_max_2m_24h:C',
            'relative_humidity_2m:p',
            'wind_speed_10m:kmh', 'wind_dir_10m:d',
            'precip_24h:mm', 'prob_precip_1h:p',
            'msl_pressure:hPa',
            'uv:idx',
            'total_cloud_cover:p'
        ]
        
        coordinates = f"{location.y},{location.x}"
        url = f"{self.base_url}/{date_str}/{','.join(params)}/{coordinates}/json"
        
        response = requests.get(
            url,
            auth=(self.username, self.password),
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        return self._parse_meteomatics_data(data)
    
    def _parse_meteomatics_data(self, data):
        """Parse Meteomatics API response"""
        result = {}
        
        for param_data in data['data']:
            param = param_data['parameter']
            value = param_data['coordinates'][0]['dates'][0]['value']
            
            if 't_2m:C' in param:
                result['temperature'] = value
            elif 't_min_2m_24h:C' in param:
                result['min_temp'] = value
            elif 't_max_2m_24h:C' in param:
                result['max_temp'] = value
            elif 'relative_humidity_2m:p' in param:
                result['humidity'] = value
            elif 'wind_speed_10m:kmh' in param:
                result['wind_speed'] = value
            elif 'wind_dir_10m:d' in param:
                result['wind_direction'] = value
            elif 'precip' in param:
                result['precipitation'] = value
            elif 'prob_precip' in param:
                result['precipitation_probability'] = value
            elif 'msl_pressure:hPa' in param:
                result['pressure'] = value
            elif 'uv:idx' in param:
                result['uv_index'] = value
            elif 'total_cloud_cover:p' in param:
                result['cloud_cover'] = value
        
        return result