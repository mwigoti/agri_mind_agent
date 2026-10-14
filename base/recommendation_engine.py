# recommendation_engine.py
from django.utils import timezone
from datetime import datetime, timedelta
from .models import WeatherData, FieldActivity, SmartRecommendation, Crop, CropGrowthStage
from .weather_utils import get_weather_suitability_score
import json

class RecommendationEngine:
    """AI-powered recommendation engine for farm activities"""
    
    def __init__(self):
        self.urgency_weights = {
            'critical': 1.0,
            'high': 0.8,
            'medium': 0.6,
            'low': 0.4,
            'info': 0.2
        }
    
    def generate_recommendations(self, field):
        """Generate dynamic recommendations for a field"""
        recommendations = []
        
        # Get recent weather data
        weather_data = self._get_recent_weather(field)
        if not weather_data:
            return recommendations
        
        # Get current activities
        current_activities = self._get_current_activities(field)
        
        # Generate different types of recommendations
        recommendations.extend(self._weather_based_recommendations(field, weather_data))
        recommendations.extend(self._irrigation_recommendations(field, weather_data))
        recommendations.extend(self._pest_control_recommendations(field, weather_data))
        recommendations.extend(self._planting_recommendations(field, weather_data))
        recommendations.extend(self._harvest_recommendations(field, weather_data))
        recommendations.extend(self._maintenance_recommendations(field, weather_data))
        
        # Filter and score recommendations
        scored_recommendations = []
        for rec in recommendations:
            confidence = self._calculate_confidence(rec, weather_data)
            if confidence > 0.3:  # Only include recommendations with decent confidence
                rec['confidence'] = confidence
                rec['field_id'] = field.id
                rec['field_name'] = field.name
                scored_recommendations.append(rec)
        
        return scored_recommendations
    
    def _get_recent_weather(self, field):
        """Get recent weather data for the field"""
        try:
            return WeatherData.objects.filter(
                field=field,
                date__gte=timezone.now() - timedelta(days=1),
                is_forecast=False
            ).order_by('-date').first()
        except:
            return None
    
    def _get_current_activities(self, field):
        """Get current and planned activities"""
        return FieldActivity.objects.filter(
            field=field,
            date__gte=timezone.now() - timedelta(days=7),
            completion_status__in=['planned', 'in_progress']
        )
    
    def _weather_based_recommendations(self, field, weather):
        """Generate weather-based recommendations"""
        recommendations = []
        
        # Extreme weather alerts
        if weather.temperature_max > 35:
            recommendations.append({
                'type': 'weather_alert',
                'title': 'Extreme Heat Warning',
                'message': f'High temperature of {weather.temperature_max}°C expected. Consider scheduling activities for early morning or evening.',
                'urgency': 'high',
                'valid_until': timezone.now() + timedelta(days=1),
                'recommended_date': timezone.now() + timedelta(hours=6)
            })
        
        if weather.precipitation > 20:
            recommendations.append({
                'type': 'weather_alert',
                'title': 'Heavy Rain Alert',
                'message': f'Heavy rainfall ({weather.precipitation}mm) expected. Postpone outdoor activities and check drainage.',
                'urgency': 'medium',
                'valid_until': timezone.now() + timedelta(days=1),
                'recommended_date': timezone.now() + timedelta(days=1)
            })
        
        if weather.wind_speed > 25:
            recommendations.append({
                'type': 'weather_alert',
                'title': 'High Wind Warning',
                'message': f'Strong winds ({weather.wind_speed} km/h) expected. Secure equipment and avoid spraying activities.',
                'urgency': 'medium',
                'valid_until': timezone.now() + timedelta(days=1),
                'recommended_date': None
            })
        
        return recommendations
    
    def _irrigation_recommendations(self, field, weather):
        """Generate irrigation recommendations"""
        recommendations = []
        
        # Check humidity and recent precipitation
        if weather.humidity < 45 and weather.precipitation < 2:
            urgency = 'high' if weather.humidity < 35 else 'medium'
            recommendations.append({
                'type': 'irrigation',
                'title': 'Irrigation Recommended',
                'message': f'Low humidity ({weather.humidity}%) and minimal recent rainfall. Consider irrigating within 24 hours.',
                'urgency': urgency,
                'valid_until': timezone.now() + timedelta(days=2),
                'recommended_date': timezone.now() + timedelta(hours=12)
            })
        
        # Check for optimal irrigation conditions
        if 50 <= weather.humidity <= 70 and weather.precipitation < 5 and weather.wind_speed < 15:
            recommendations.append({
                'type': 'irrigation',
                'title': 'Optimal Irrigation Conditions',
                'message': 'Current conditions are ideal for irrigation. Minimal wind and good humidity levels.',
                'urgency': 'low',
                'valid_until': timezone.now() + timedelta(hours=12),
                'recommended_date': timezone.now() + timedelta(hours=2)
            })
        
        return recommendations
    
    def _pest_control_recommendations(self, field, weather):
        """Generate pest control recommendations"""
        recommendations = []
        
        # Optimal pest control conditions
        if (weather.precipitation == 0 and weather.wind_speed < 10 and 
            20 <= weather.temperature_avg <= 28):
            recommendations.append({
                'type': 'pest_control',
                'title': 'Optimal Pest Control Conditions',
                'message': 'Perfect conditions for pest control: no rain, low wind, and moderate temperature.',
                'urgency': 'low',
                'valid_until': timezone.now() + timedelta(hours=8),
                'recommended_date': timezone.now() + timedelta(hours=1)
            })
        
        # Weather conditions favoring pests
        if weather.humidity > 75 and 25 <= weather.temperature_avg <= 30:
            recommendations.append({
                'type': 'pest_warning',
                'title': 'Increased Pest Activity Expected',
                'message': 'High humidity and warm temperatures favor pest development. Monitor crops closely.',
                'urgency': 'medium',
                'valid_until': timezone.now() + timedelta(days=3),
                'recommended_date': timezone.now() + timedelta(days=1)
            })
        
        return recommendations
    
    def _planting_recommendations(self, field, weather):
        """Generate planting recommendations"""
        recommendations = []
        
        # Optimal planting conditions
        if (18 <= weather.temperature_avg <= 25 and 
            2 <= weather.precipitation <= 8 and 
            weather.wind_speed < 15):
            
            recommendations.append({
                'type': 'planting_optimal',
                'title': 'Excellent Planting Conditions',
                'message': 'Ideal temperature, light rainfall, and calm winds. Perfect for planting new crops.',
                'urgency': 'high',
                'valid_until': timezone.now() + timedelta(days=2),
                'recommended_date': timezone.now() + timedelta(hours=24)
            })
        
        # Upcoming favorable forecast
        forecast_weather = self._get_forecast_weather(field, days=3)
        if forecast_weather:
            avg_temp = sum(w.temperature_avg for w in forecast_weather) / len(forecast_weather)
            total_rain = sum(w.precipitation for w in forecast_weather)
            
            if 18 <= avg_temp <= 26 and 5 <= total_rain <= 15:
                recommendations.append({
                    'type': 'planting_optimal',
                    'title': 'Favorable Planting Weather Ahead',
                    'message': f'Next 3 days show good conditions: avg temp {avg_temp:.1f}°C, total rain {total_rain:.1f}mm.',
                    'urgency': 'medium',
                    'valid_until': timezone.now() + timedelta(days=1),
                    'recommended_date': timezone.now() + timedelta(days=1)
                })