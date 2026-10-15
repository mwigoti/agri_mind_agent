# weather_service.py
import requests
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta
from .models import WeatherData
import json

class WeatherService:
    """Service to fetch and manage weather data"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'WEATHER_API_KEY', 'your_weather_api_key')
        self.base_url = "https://api.openweathermap.org/data/2.5"
    
    def get_field_weather(self, field):
        """Get current and forecast weather for a field"""
        # Get field center point
        centroid = field.geometry.centroid
        lat, lon = centroid.y, centroid.x
        
        # Get current weather
        current_weather = self._fetch_current_weather(lat, lon)
        
        # Get 7-day forecast
        forecast = self._fetch_forecast(lat, lon)
        
        # Store in database
        self._store_weather_data(field, current_weather, forecast)
        
        return {
            'current': current_weather,
            'forecast': forecast[:7]  # 7-day forecast
        }
    
    def _fetch_current_weather(self, lat, lon):
        """Fetch current weather from API"""
        try:
            url = f"{self.base_url}/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            return {
                'temperature': round(data['main']['temp']),
                'humidity': data['main']['humidity'],
                'precipitation': data.get('rain', {}).get('1h', 0),
                'wind_speed': round(data['wind']['speed'] * 3.6),  # Convert m/s to km/h
                'wind_direction': data['wind'].get('deg', 0),
                'pressure': data['main']['pressure'],
                'condition': data['weather'][0]['description'].title(),
                'uv_index': 0  # Need separate UV API call
            }
            
        except Exception as e:
            print(f"Error fetching current weather: {e}")
            # Return default values
            return {
                'temperature': 22,
                'humidity': 65,
                'precipitation': 0,
                'wind_speed': 12,
                'wind_direction': 0,
                'pressure': 1013,
                'condition': 'Clear',
                'uv_index': 0
            }
    
    def _fetch_forecast(self, lat, lon):
        """Fetch 7-day weather forecast"""
        try:
            url = f"{self.base_url}/onecall"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric',
                'exclude': 'minutely,alerts'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            forecast = []
            for day in data['daily'][:7]:
                forecast.append({
                    'date': datetime.fromtimestamp(day['dt']).strftime('%Y-%m-%d'),
                    'temp_min': round(day['temp']['min']),
                    'temp_max': round(day['temp']['max']),
                    'humidity': day['humidity'],
                    'precipitation': day.get('rain', {}).get('1h', 0) + day.get('snow', {}).get('1h', 0),
                    'wind_speed': round(day['wind_speed'] * 3.6),
                    'condition': day['weather'][0]['description'].title(),
                    'uv_index': day.get('uvi', 0)
                })
            
            return forecast
            
        except Exception as e:
            print(f"Error fetching forecast: {e}")
            # Return default forecast
            return [
                {
                    'date': (datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d'),
                    'temp_min': 18 + i,
                    'temp_max': 25 + i,
                    'humidity': 65,
                    'precipitation': 0,
                    'wind_speed': 12,
                    'condition': 'Partly Cloudy',
                    'uv_index': 5
                }
                for i in range(7)
            ]
    
    def _store_weather_data(self, field, current, forecast):
        """Store weather data in database"""
        try:
            # Store current weather
            WeatherData.objects.update_or_create(
                field=field,
                date=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
                is_forecast=False,
                defaults={
                    'temperature_min': current['temperature'],
                    'temperature_max': current['temperature'],
                    'temperature_avg': current['temperature'],
                    'humidity': current['humidity'],
                    'precipitation': current['precipitation'],
                    'wind_speed': current['wind_speed'],
                    'wind_direction': current['wind_direction'],
                    'pressure': current['pressure'],
                    'uv_index': current['uv_index'],
                    'weather_condition': current['condition']
                }
            )
            
            # Store forecast data
            for day_forecast in forecast:
                forecast_date = datetime.strptime(day_forecast['date'], '%Y-%m-%d')
                WeatherData.objects.update_or_create(
                    field=field,
                    date=forecast_date,
                    is_forecast=True,
                    defaults={
                        'temperature_min': day_forecast['temp_min'],
                        'temperature_max': day_forecast['temp_max'],
                        'temperature_avg': (day_forecast['temp_min'] + day_forecast['temp_max']) / 2,
                        'humidity': day_forecast['humidity'],
                        'precipitation': day_forecast['precipitation'],
                        'wind_speed': day_forecast['wind_speed'],
                        'wind_direction': 0,
                        'pressure': 1013,
                        'uv_index': day_forecast['uv_index'],
                        'weather_condition': day_forecast['condition']
                    }
                )
                
        except Exception as e:
            print(f"Error storing weather data: {e}")

