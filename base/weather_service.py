# weather_service.py
import logging
import math
from datetime import datetime

import requests
from django.utils import timezone

from .models import WeatherData

logger = logging.getLogger(__name__)

class WeatherService:
    """Fetch weather data from the Open-Meteo source already used by field analysis."""

    base_url = "https://api.open-meteo.com/v1/forecast"

    @staticmethod
    def _valid_coordinates(lat, lon):
        try:
            lat, lon = float(lat), float(lon)
        except (TypeError, ValueError):
            return False
        return math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180

    @staticmethod
    def _weather_condition(code):
        labels = {
            0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
            45: 'Fog', 48: 'Depositing rime fog', 51: 'Light drizzle',
            53: 'Moderate drizzle', 55: 'Dense drizzle', 56: 'Freezing drizzle',
            57: 'Dense freezing drizzle', 61: 'Slight rain', 63: 'Moderate rain',
            65: 'Heavy rain', 66: 'Freezing rain', 67: 'Heavy freezing rain',
            71: 'Slight snow', 73: 'Moderate snow', 75: 'Heavy snow', 77: 'Snow grains',
            80: 'Slight rain showers', 81: 'Moderate rain showers', 82: 'Violent rain showers',
            85: 'Slight snow showers', 86: 'Heavy snow showers', 95: 'Thunderstorm',
            96: 'Thunderstorm with hail', 99: 'Severe thunderstorm with hail',
        }
        try:
            return labels.get(int(code), 'Unknown')
        except (TypeError, ValueError):
            return 'Unknown'
    
    def get_field_weather(self, field, days=7):
        """Get current and forecast weather for a field"""
        # Get field center point
        centroid = field.geometry.centroid
        lat, lon = centroid.y, centroid.x
        if not self._valid_coordinates(lat, lon):
            logger.warning(
                "Skipping weather refresh for field %s: invalid centroid latitude=%s longitude=%s",
                field.pk, lat, lon,
            )
            return {'current': None, 'forecast': [], 'stored': False, 'error': 'invalid_coordinates'}
        
        # Get current weather
        current_weather = self._fetch_current_weather(lat, lon)
        
        # Get 7-day forecast
        forecast = self._fetch_forecast(lat, lon, days=days)
        
        # Store in database
        stored = False
        if current_weather is not None or forecast:
            stored = self._store_weather_data(field, current_weather, forecast)
        
        return {
            'current': current_weather,
            'forecast': forecast[:days],
            'stored': stored,
        }
    
    def _fetch_current_weather(self, lat, lon):
        """Fetch current conditions from Open-Meteo."""
        try:
            if not self._valid_coordinates(lat, lon):
                logger.warning("Skipping current weather request for invalid coordinates (%s, %s)", lat, lon)
                return None
            params = {
                'latitude': lat,
                'longitude': lon,
                'current': 'temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,wind_direction_10m,surface_pressure,weather_code',
                'daily': 'temperature_2m_min,temperature_2m_max',
                'forecast_days': 1,
                'timezone': 'auto',
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            current = data.get('current') or {}
            daily = data.get('daily') or {}
            temp_min = (daily.get('temperature_2m_min') or [None])[0]
            temp_max = (daily.get('temperature_2m_max') or [None])[0]
            required = (
                'temperature_2m', 'relative_humidity_2m', 'precipitation',
                'wind_speed_10m', 'wind_direction_10m', 'surface_pressure',
            )
            if any(current.get(key) is None for key in required):
                logger.warning("Open-Meteo current response lacked required weather values")
                return None

            return {
                'temperature': current.get('temperature_2m'),
                'temperature_min': temp_min if temp_min is not None else current.get('temperature_2m'),
                'temperature_max': temp_max if temp_max is not None else current.get('temperature_2m'),
                'humidity': current.get('relative_humidity_2m'),
                'precipitation': current.get('precipitation'),
                'wind_speed': current.get('wind_speed_10m'),
                'wind_direction': current.get('wind_direction_10m'),
                'pressure': current.get('surface_pressure'),
                'condition': self._weather_condition(current.get('weather_code')),
                'uv_index': 0,
            }
        except Exception as e:
            logger.warning("Open-Meteo current weather request failed: %s", e)
            return None

    def _fetch_forecast(self, lat, lon, days=7):
        """Fetch daily forecast values, including precipitation sums in millimeters."""
        try:
            if not self._valid_coordinates(lat, lon):
                logger.warning("Skipping forecast request for invalid coordinates (%s, %s)", lat, lon)
                return []
            params = {
                'latitude': lat,
                'longitude': lon,
                'daily': 'temperature_2m_min,temperature_2m_max,temperature_2m_mean,relative_humidity_2m_mean,precipitation_sum,wind_speed_10m_max,wind_direction_10m_dominant,surface_pressure_mean,weather_code,uv_index_max',
                'forecast_days': days,
                'timezone': 'auto',
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            daily = response.json().get('daily') or {}
            forecast = []
            dates = daily.get('time') or []
            for index, forecast_date in enumerate(dates[:days]):
                def value(key, default=None):
                    values = daily.get(key) or []
                    return values[index] if index < len(values) else default

                row = {
                    'date': forecast_date,
                    'temp_min': value('temperature_2m_min'),
                    'temp_max': value('temperature_2m_max'),
                    'temp_mean': value('temperature_2m_mean'),
                    'humidity': value('relative_humidity_2m_mean'),
                    'precipitation': value('precipitation_sum'),
                    'wind_speed': value('wind_speed_10m_max'),
                    'wind_direction': value('wind_direction_10m_dominant'),
                    'pressure': value('surface_pressure_mean'),
                    'condition': self._weather_condition(value('weather_code')),
                    'uv_index': value('uv_index_max', 0),
                }
                required = ('temp_min', 'temp_max', 'humidity', 'precipitation', 'wind_speed', 'wind_direction', 'pressure')
                if any(row[key] is None for key in required):
                    logger.warning("Skipping incomplete Open-Meteo forecast row for %s", forecast_date)
                    continue
                forecast.append(row)
            return forecast
        except Exception as e:
            logger.warning("Open-Meteo forecast request failed: %s", e)
            return []
    
    def _store_weather_data(self, field, current, forecast):
        """Store weather data in database"""
        try:
            # Store current weather
            if current is not None:
                WeatherData.objects.update_or_create(
                    field=field,
                    date=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0),
                    is_forecast=False,
                    defaults={
                        'temperature_min': current['temperature_min'],
                        'temperature_max': current['temperature_max'],
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
                if timezone.is_aware(timezone.now()):
                    forecast_date = timezone.make_aware(forecast_date, timezone.get_current_timezone())
                WeatherData.objects.update_or_create(
                    field=field,
                    date=forecast_date,
                    is_forecast=True,
                    defaults={
                        'temperature_min': day_forecast['temp_min'],
                        'temperature_max': day_forecast['temp_max'],
                        'temperature_avg': day_forecast['temp_mean'] if day_forecast['temp_mean'] is not None else (day_forecast['temp_min'] + day_forecast['temp_max']) / 2,
                        'humidity': day_forecast['humidity'],
                        'precipitation': day_forecast['precipitation'],
                        'wind_speed': day_forecast['wind_speed'],
                        'wind_direction': day_forecast['wind_direction'],
                        'pressure': day_forecast['pressure'],
                        'uv_index': day_forecast['uv_index'],
                        'weather_condition': day_forecast['condition']
                    }
                )
            return True
        except Exception as e:
            logger.exception("Failed to save weather data for field %s: %s", field.pk, e)
            return False

