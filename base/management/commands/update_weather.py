from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from ...models import Field, WeatherData
from ...utils import WeatherService

class Command(BaseCommand):
    help = 'Update weather data for all fields'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of forecast days to fetch (default: 7)'
        )
    
    def handle(self, *args, **options):
        weather_service = WeatherService()
        days = options['days']
        
        fields = Field.objects.all()
        self.stdout.write(f'Updating weather data for {fields.count()} fields...')
        
        for field in fields:
            try:
                center = field.geometry.centroid
                lat, lon = center.y, center.x
                
                # Get current weather
                current = weather_service.get_current_weather(lat, lon)
                if current:
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
                            'weather_condition': current['weather_condition'],
                            'uv_index': 0
                        }
                    )
                
                # Get forecast data
                forecast = weather_service.get_forecast(lat, lon, days)
                for day_data in forecast:
                    WeatherData.objects.update_or_create(
                        field=field,
                        date=day_data['date'].replace(hour=12, minute=0, second=0, microsecond=0),
                        is_forecast=True,
                        defaults={
                            'temperature_min': day_data['temperature_min'],
                            'temperature_max': day_data['temperature_max'],
                            'temperature_avg': day_data['temperature_avg'],
                            'humidity': day_data['humidity'],
                            'precipitation': day_data['precipitation'],
                            'wind_speed': day_data['wind_speed'],
                            'wind_direction': day_data['wind_direction'],
                            'pressure': day_data['pressure'],
                            'weather_condition': day_data['weather_condition'],
                            'uv_index': day_data['uv_index']
                        }
                    )
                
                self.stdout.write(f'✓ Updated weather data for {field.name}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error updating weather for {field.name}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated weather data for {fields.count()} fields')
        )