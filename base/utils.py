import requests
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from decimal import Decimal
from .models import WeatherData, SmartRecommendation, FieldActivity, Crop

logger = logging.getLogger(__name__)

class WeatherService:
    """Service class for weather data integration"""
    
    def __init__(self):
        self.api_key = getattr(settings, 'WEATHER_API_KEY', '')
        self.base_url = "http://api.openweathermap.org/data/2.5"
    
    def get_current_weather(self, lat, lon):
        """Get current weather for given coordinates"""
        try:
            url = f"{self.base_url}/weather"
            params = {
                'lat': lat,
                'lon': lon,
                'appid': self.api_key,
                'units': 'metric'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return self._parse_current_weather(data)
        except Exception as e:
            logger.error(f"Error fetching current weather: {str(e)}")
        return None
    
    def get_forecast(self, lat, lon, days=7):
        """Get weather forecast for given coordinates"""
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
            if response.status_code == 200:
                data = response.json()
                return self._parse_forecast(data, days)
        except Exception as e:
            logger.error(f"Error fetching forecast: {str(e)}")
        return []
    
    def _parse_current_weather(self, data):
        """Parse current weather data from API response"""
        main = data.get('main', {})
        wind = data.get('wind', {})
        weather = data.get('weather', [{}])[0]
        
        return {
            'temperature': main.get('temp', 0),
            'temperature_min': main.get('temp_min', 0),
            'temperature_max': main.get('temp_max', 0),
            'humidity': main.get('humidity', 0),
            'pressure': main.get('pressure', 0),
            'wind_speed': wind.get('speed', 0),
            'wind_direction': wind.get('deg', 0),
            'weather_condition': weather.get('description', ''),
            'precipitation': data.get('rain', {}).get('1h', 0)
        }
    
    def _parse_forecast(self, data, days):
        """Parse forecast data from API response"""
        forecast_list = []
        daily_data = data.get('daily', [])[:days]
        
        for day_data in daily_data:
            forecast_list.append({
                'date': timezone.datetime.fromtimestamp(day_data['dt'], tz=timezone.utc),
                'temperature_min': day_data['temp']['min'],
                'temperature_max': day_data['temp']['max'],
                'temperature_avg': day_data['temp']['day'],
                'humidity': day_data['humidity'],
                'pressure': day_data['pressure'],
                'wind_speed': day_data['wind_speed'],
                'wind_direction': day_data['wind_deg'],
                'weather_condition': day_data['weather'][0]['description'],
                'precipitation': day_data.get('rain', {}).get('1h', 0),
                'uv_index': day_data.get('uvi', 0)
            })
        
        return forecast_list

class SmartRecommendationEngine:
    """AI-powered recommendation engine for farm activities"""
    
    def __init__(self):
        self.weather_service = WeatherService()
    
    def generate_recommendations(self, field):
        """Generate smart recommendations for a field"""
        recommendations = []
        
        # Get weather data
        center = field.geometry.centroid
        current_weather = self.weather_service.get_current_weather(center.y, center.x)
        forecast = self.weather_service.get_forecast(center.y, center.x)
        
        if current_weather:
            recommendations.extend(self._weather_based_recommendations(field, current_weather))
        
        if forecast:
            recommendations.extend(self._forecast_based_recommendations(field, forecast))
        
        recommendations.extend(self._activity_based_recommendations(field))
        recommendations.extend(self._seasonal_recommendations(field))
        
        return self._filter_and_rank_recommendations(recommendations)
    
    def _weather_based_recommendations(self, field, weather):
        """Generate recommendations based on current weather"""
        recommendations = []
        
        # Irrigation recommendations
        if weather['humidity'] < 50 and weather['precipitation'] < 5:
            recommendations.append({
                'type': 'irrigation',
                'title': 'Irrigation Recommended',
                'message': f"Low humidity ({weather['humidity']}%) and minimal precipitation detected. Consider irrigating crops.",
                'urgency': 'medium',
                'confidence': 0.8,
                'factors': {
                    'humidity': weather['humidity'],
                    'precipitation': weather['precipitation']
                }
            })
        
        # Wind-based recommendations
        if weather['wind_speed'] > 25:
            recommendations.append({
                'type': 'weather_alert',
                'title': 'High Wind Alert',
                'message': f"Strong winds ({weather['wind_speed']} km/h) detected. Avoid spraying operations.",
                'urgency': 'high',
                'confidence': 0.9,
                'factors': {'wind_speed': weather['wind_speed']}
            })
        
        # Temperature-based recommendations
        if weather['temperature'] < 5:
            recommendations.append({
                'type': 'weather_alert',
                'title': 'Frost Risk Alert',
                'message': f"Low temperature ({weather['temperature']}°C) detected. Protect sensitive crops.",
                'urgency': 'high',
                'confidence': 0.95,
                'factors': {'temperature': weather['temperature']}
            })
        
        return recommendations
    
    def _forecast_based_recommendations(self, field, forecast):
        """Generate recommendations based on weather forecast"""
        recommendations = []
        
        for day_forecast in forecast[:3]:  # Next 3 days
            # Rain-based planting recommendations
            if day_forecast['precipitation'] > 10 and day_forecast['temperature_avg'] > 15:
                recommendations.append({
                    'type': 'planting_optimal',
                    'title': 'Optimal Planting Conditions',
                    'message': f"Good rainfall ({day_forecast['precipitation']}mm) and temperature expected on {day_forecast['date'].strftime('%Y-%m-%d')}.",
                    'urgency': 'medium',
                    'confidence': 0.85,
                    'recommended_date': day_forecast['date'],
                    'factors': {
                        'precipitation': day_forecast['precipitation'],
                        'temperature': day_forecast['temperature_avg']
                    }
                })
        
        return recommendations
    
    def _activity_based_recommendations(self, field):
        """Generate recommendations based on field activity history"""
        recommendations = []
        
        # Get recent activities
        recent_activities = FieldActivity.objects.filter(
            field=field,
            date__gte=timezone.now() - timedelta(days=30)
        )
        
        # Check for missing irrigation
        last_irrigation = recent_activities.filter(activity_type='irrigation').first()
        if not last_irrigation or (timezone.now() - last_irrigation.date).days > 7:
            recommendations.append({
                'type': 'irrigation',
                'title': 'Irrigation Schedule Check',
                'message': 'No irrigation recorded in the past 7 days. Consider checking soil moisture levels.',
                'urgency': 'low',
                'confidence': 0.6,
                'factors': {'days_since_irrigation': 7 if not last_irrigation else (timezone.now() - last_irrigation.date).days}
            })
        
        # Check for maintenance schedule
        last_maintenance = recent_activities.filter(activity_type='maintenance').first()
        if not last_maintenance or (timezone.now() - last_maintenance.date).days > 14:
            recommendations.append({
                'type': 'activity',
                'title': 'Equipment Maintenance Due',
                'message': 'Regular equipment maintenance helps prevent costly breakdowns.',
                'urgency': 'low',
                'confidence': 0.7,
                'factors': {'days_since_maintenance': 14 if not last_maintenance else (timezone.now() - last_maintenance.date).days}
            })
        
        return recommendations
    
    def _seasonal_recommendations(self, field):
        """Generate seasonal recommendations"""
        recommendations = []
        current_month = timezone.now().month
        
        # Spring planting recommendations (March-May)
        if current_month in [3, 4, 5]:
            recommendations.append({
                'type': 'planting_optimal',
                'title': 'Spring Planting Season',
                'message': 'Optimal time for planting spring crops. Consider soil temperature and moisture.',
                'urgency': 'medium',
                'confidence': 0.8,
                'factors': {'season': 'spring', 'month': current_month}
            })
        
        # Fall harvest recommendations (September-November)
        elif current_month in [9, 10, 11]:
            recommendations.append({
                'type': 'harvest_optimal',
                'title': 'Fall Harvest Season',
                'message': 'Monitor crop maturity for optimal harvest timing.',
                'urgency': 'medium',
                'confidence': 0.8,
                'factors': {'season': 'fall', 'month': current_month}
            })
        
        return recommendations
    
    def _filter_and_rank_recommendations(self, recommendations):
        """Filter duplicate recommendations and rank by importance"""
        # Remove duplicates based on type and title
        unique_recs = {}
        for rec in recommendations:
            key = f"{rec['type']}_{rec['title']}"
            if key not in unique_recs or rec['confidence'] > unique_recs[key]['confidence']:
                unique_recs[key] = rec
        
        # Sort by urgency and confidence
        urgency_order = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1, 'info': 0}
        sorted_recs = sorted(
            unique_recs.values(),
            key=lambda x: (urgency_order.get(x['urgency'], 0), x['confidence']),
            reverse=True
        )
        
        return sorted_recs[:10]  # Return top 10 recommendations

class ActivityOptimizer:
    """Optimize activity timing based on weather and field conditions"""
    
    def __init__(self):
        self.weather_service = WeatherService()
    
    def calculate_optimal_timing(self, field, activity_type, days_ahead=14):
        """Calculate optimal timing for an activity"""
        center = field.geometry.centroid
        forecast = self.weather_service.get_forecast(center.y, center.x, days_ahead)
        
        if not forecast:
            return []
        
        optimizations = []
        
        for day_data in forecast:
            score = self._calculate_activity_score(activity_type, day_data)
            
            optimizations.append({
                'date': day_data['date'],
                'activity_type': activity_type,
                'weather_score': score['weather'],
                'overall_score': score['overall'],
                'factors': score['factors']
            })
        
        return sorted(optimizations, key=lambda x: x['overall_score'], reverse=True)
    
    def _calculate_activity_score(self, activity_type, weather_data):
        """Calculate activity suitability score based on weather"""
        scores = {
            'temperature': 0,
            'precipitation': 0,
            'wind': 0,
            'humidity': 0
        }
        
        temp = weather_data['temperature_avg']
        precip = weather_data['precipitation']
        wind = weather_data['wind_speed']
        humidity = weather_data['humidity']
        
        if activity_type == 'planting':
            # Optimal planting conditions
            scores['temperature'] = max(0, min(1, (temp - 10) / 20))  # 10-30°C range
            scores['precipitation'] = min(1, max(0.3, precip / 15))   # Some rain helpful
            scores['wind'] = max(0, 1 - wind / 25)                    # Low wind preferred
            scores['humidity'] = max(0.3, min(1, humidity / 80))      # Moderate humidity
            
        elif activity_type == 'irrigation':
            # Irrigation timing
            scores['temperature'] = max(0, min(1, temp / 35))         # Warmer = more need
            scores['precipitation'] = max(0, 1 - precip / 10)         # Less rain = more need
            scores['wind'] = max(0.2, 1 - wind / 20)                  # Low-moderate wind ok
            scores['humidity'] = max(0, 1 - humidity / 100)           # Low humidity = more need
            
        elif activity_type == 'harvest':
            # Harvest conditions
            scores['temperature'] = max(0, min(1, (temp - 5) / 25))  # 5-30°C range
            scores['precipitation'] = max(0, 1 - precip / 5)          # Dry conditions preferred
            scores['wind'] = max(0.3, 1 - wind / 30)                  # Moderate wind ok
            scores['humidity'] = max(0.4, 1 - humidity / 90)          # Lower humidity preferred
            
        elif activity_type == 'maintenance':
            # Equipment maintenance
            scores['temperature'] = max(0, min(1, (temp - 0) / 30))  # Above freezing
            scores['precipitation'] = max(0, 1 - precip / 3)          # Dry preferred
            scores['wind'] = max(0.5, 1 - wind / 35)                  # Wind less critical
            scores['humidity'] = 0.7  # Less critical for maintenance
            
        else:
            # Default scoring
            scores = {key: 0.5 for key in scores}
        
        # Calculate weighted overall score
        weights = {
            'temperature': 0.3,
            'precipitation': 0.3,
            'wind': 0.2,
            'humidity': 0.2
        }
        
        overall_score = sum(scores[factor] * weight for factor, weight in weights.items())
        
        return {
            'weather': overall_score,
            'overall': overall_score,  # Can be enhanced with crop stage, soil conditions, etc.
            'factors': {
                'temperature': temp,
                'precipitation': precip,
                'wind_speed': wind,
                'humidity': humidity,
                'individual_scores': scores
            }
        }
