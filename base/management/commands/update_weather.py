from django.core.management.base import BaseCommand
from ...models import Field
from ...weather_service import WeatherService

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
                weather = weather_service.get_field_weather(field, days=days)
                if weather.get('stored'):
                    self.stdout.write(f'✓ Updated weather data for {field.name}')
                elif weather.get('current') is not None or weather.get('forecast'):
                    self.stdout.write(self.style.ERROR(f'Live weather fetched but not saved for {field.name}'))
                elif weather.get('error') == 'invalid_coordinates':
                    self.stdout.write(self.style.ERROR(
                        f'Skipped {field.name}: geometry centroid must be valid WGS84 latitude/longitude; '
                        'correct the saved field polygon.'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(f'No live weather data available for {field.name}'))
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error updating weather for {field.name}: {str(e)}')
                )
        
        self.stdout.write(self.style.SUCCESS(f'Weather refresh finished for {fields.count()} fields'))
