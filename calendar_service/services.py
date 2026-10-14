from django.utils import timezone
from datetime import timedelta, datetime
from .models import Task
from weather_service.services import WeatherService

class TaskSchedulingService:
    """Service for handling task scheduling logic"""
    
    @staticmethod
    def create_next_recurring_task(task):
        """Create the next instance of a recurring task"""
        if task.recurrence_type == 'none':
            return None
        
        next_date = TaskSchedulingService._calculate_next_occurrence(
            task.scheduled_date, 
            task.recurrence_type, 
            task.recurrence_interval
        )
        
        if task.recurrence_end_date and next_date.date() > task.recurrence_end_date:
            return None
        
        next_task = Task.objects.create(
            title=task.title,
            description=task.description,
            category=task.category,
            farm=task.farm,
            field=task.field,
            assigned_to=task.assigned_to,
            created_by=task.created_by,
            scheduled_date=next_date,
            due_date=task.due_date,
            estimated_duration=task.estimated_duration,
            priority=task.priority,
            recurrence_type=task.recurrence_type,
            recurrence_interval=task.recurrence_interval,
            recurrence_end_date=task.recurrence_end_date,
            parent_task=task.parent_task or task,
            weather_dependent=task.weather_dependent,
            min_temperature=task.min_temperature,
            max_temperature=task.max_temperature,
            max_wind_speed=task.max_wind_speed,
            avoid_rain=task.avoid_rain,
        )
        
        return next_task
    
    @staticmethod
    def _calculate_next_occurrence(current_date, recurrence_type, interval):
        """Calculate the next occurrence date"""
        if recurrence_type == 'daily':
            return current_date + timedelta(days=interval)
        elif recurrence_type == 'weekly':
            return current_date + timedelta(weeks=interval)
        elif recurrence_type == 'monthly':
            # Simple monthly calculation (may need refinement)
            return current_date + timedelta(days=30 * interval)
        elif recurrence_type == 'seasonal':
            return current_date + timedelta(days=90 * interval)
        
        return current_date

class WeatherTaskService:
    """Service for weather-aware task scheduling"""
    
    def __init__(self):
        self.weather_service = WeatherService()
    
    def check_task_weather_suitability(self, task):
        """Check if weather conditions are suitable for a task"""
        if not task.weather_dependent:
            return {'suitable': True, 'warnings': [], 'recommendations': []}
        
        try:
            forecast = self.weather_service.get_forecast(
                task.field.farm.location if task.field else task.farm.location,
                task.scheduled_date.date()
            )
            
            warnings = []
            recommendations = []
            suitable = True
            
            # Temperature checks
            if task.min_temperature and forecast.get('min_temp', 0) < task.min_temperature:
                suitable = False
                warnings.append(f"Temperature too low: {forecast.get('min_temp')}°C < {task.min_temperature}°C")
                recommendations.append("Consider rescheduling to a warmer day")
            
            if task.max_temperature and forecast.get('max_temp', 50) > task.max_temperature:
                suitable = False
                warnings.append(f"Temperature too high: {forecast.get('max_temp')}°C > {task.max_temperature}°C")
                recommendations.append("Schedule for early morning or late evening")
            
            # Wind speed checks
            if task.max_wind_speed and forecast.get('wind_speed', 0) > task.max_wind_speed:
                suitable = False
                warnings.append(f"Wind too strong: {forecast.get('wind_speed')} km/h > {task.max_wind_speed} km/h")
                recommendations.append("Wait for calmer conditions, especially for spraying")
            
            # Rain checks
            if task.avoid_rain and forecast.get('precipitation_probability', 0) > 30:
                suitable = False
                warnings.append(f"Rain likely: {forecast.get('precipitation_probability')}% chance")
                recommendations.append("Postpone until after rain passes")
            
            return {
                'suitable': suitable,
                'warnings': warnings,
                'recommendations': recommendations,
                'forecast': forecast
            }
            
        except Exception as e:
            return {
                'suitable': True,  # Default to suitable if weather check fails
                'warnings': ['Weather data unavailable'],
                'recommendations': ['Proceed with caution'],
                'error': str(e)
            }
    
    def suggest_optimal_dates(self, task, date_range_days=14):
        """Suggest optimal dates for weather-dependent tasks"""
        if not task.weather_dependent:
            return []
        
        suggestions = []
        start_date = timezone.now().date()
        
        for days_ahead in range(1, date_range_days + 1):
            check_date = start_date + timedelta(days=days_ahead)
            test_task = task
            test_task.scheduled_date = datetime.combine(check_date, task.scheduled_date.time())
            
            suitability = self.check_task_weather_suitability(test_task)
            if suitability['suitable']:
                suggestions.append({
                    'date': check_date,
                    'score': self._calculate_suitability_score(suitability['forecast']),
                    'forecast': suitability['forecast']
                })
        
        # Sort by suitability score (higher is better)
        suggestions.sort(key=lambda x: x['score'], reverse=True)
        return suggestions[:5]  # Return top 5 suggestions
    
    def _calculate_suitability_score(self, forecast):
        """Calculate a suitability score based on weather conditions"""
        score = 100
        
        # Deduct points for unfavorable conditions
        if forecast.get('precipitation_probability', 0) > 0:
            score -= forecast['precipitation_probability'] * 0.5
        
        if forecast.get('wind_speed', 0) > 15:  # High wind
            score -= (forecast['wind_speed'] - 15) * 2
        
        # Temperature extremes
        temp = forecast.get('max_temp', 25)
        if temp > 35 or temp < 5:
            score -= abs(temp - 25) * 2
        
        return max(0, score)