from celery import shared_task
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.gis.geos import Point
from base.models import Farm
from .services import WeatherService
from .models import WeatherAlert
import logging

logger = logging.getLogger(__name__)

@shared_task
def fetch_weather_forecasts():
    """Fetch weather forecasts for all active farms"""
    weather_service = WeatherService()
    
    farms = Farm.objects.filter(location__isnull=False)
    forecasts_updated = 0
    
    for farm in farms:
        try:
            # Get 7-day forecast
            forecasts = weather_service.get_multi_day_forecast(farm.location, days=7)
            forecasts_updated += len(forecasts)
            
        except Exception as e:
            logger.error(f"Failed to fetch weather for farm {farm.id}: {e}")
    
    return f"Updated forecasts for {forecasts_updated} farm-days"

@shared_task
def check_weather_alerts():
    """Check for weather alerts and create notifications"""
    weather_service = WeatherService()
    farms = Farm.objects.filter(location__isnull=False)
    
    alerts_created = 0
    
    for farm in farms:
        try:
            # Get current and next day forecast
            current_forecast = weather_service.get_current_weather(farm.location)
            tomorrow_forecast = weather_service.get_forecast(
                farm.location, 
                (timezone.now() + timedelta(days=1)).date()
            )
            
            # Check for alert conditions
            alerts = []
            
            # Frost warning
            if (tomorrow_forecast.get('min_temp', 20) < 2 and 
                timezone.now().month in [5, 6, 7, 8]):  # Winter months
                alerts.append({
                    'type': 'frost',
                    'severity': 'high',
                    'title': 'Frost Warning',
                    'description': f"Minimum temperature expected: {tomorrow_forecast['min_temp']}°C"
                })
            
            # High wind warning
            if current_forecast.get('wind_speed', 0) > 50:
                alerts.append({
                    'type': 'wind',
                    'severity': 'medium',
                    'title': 'High Wind Warning',
                    'description': f"Wind speed: {current_forecast['wind_speed']} km/h"
                })
            
            # Heavy rain warning
            if tomorrow_forecast.get('precipitation', 0) > 25:
                alerts.append({
                    'type': 'rain',
                    'severity': 'medium',
                    'title': 'Heavy Rain Expected',
                    'description': f"Expected rainfall: {tomorrow_forecast['precipitation']}mm"
                })
            
            # Create alert records
            for alert_data in alerts:
                WeatherAlert.objects.get_or_create(
                    location=farm.location,
                    alert_type=alert_data['type'],
                    start_time=timezone.now(),
                    defaults={
                        'severity': alert_data['severity'],
                        'title': alert_data['title'],
                        'description': alert_data['description'],
                        'end_time': timezone.now() + timedelta(hours=24),
                    }
                )
                alerts_created += 1
                
        except Exception as e:
            logger.error(f"Failed to check alerts for farm {farm.id}: {e}")
    
    return f"Created {alerts_created} weather alerts"

@shared_task
def cleanup_old_weather_data():
    """Clean up old weather forecast data"""
    cutoff_date = timezone.now() - timedelta(days=30)
    
    from .models import WeatherForecast
    deleted_count = WeatherForecast.objects.filter(
        created_at__lt=cutoff_date
    ).delete()[0]
    
    # Also clean up expired alerts
    expired_alerts = WeatherAlert.objects.filter(
        end_time__lt=timezone.now(),
        is_active=True
    ).update(is_active=False)
    
    return f"Deleted {deleted_count} old forecasts, deactivated {expired_alerts} expired alerts"
