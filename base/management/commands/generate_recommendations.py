from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from ...models import Field, SmartRecommendation
from ...utils import SmartRecommendationEngine

class Command(BaseCommand):
    help = 'Generate smart recommendations for all fields'
    
    def handle(self, *args, **options):
        recommendation_engine = SmartRecommendationEngine()
        
        fields = Field.objects.all()
        self.stdout.write(f'Generating recommendations for {fields.count()} fields...')
        
        total_recommendations = 0
        
        for field in fields:
            try:
                # Clear old recommendations
                SmartRecommendation.objects.filter(
                    field=field,
                    valid_until__lt=timezone.now()
                ).delete()
                
                # Generate new recommendations
                recommendations = recommendation_engine.generate_recommendations(field)
                
                for rec_data in recommendations:
                    # Check if similar recommendation already exists
                    existing = SmartRecommendation.objects.filter(
                        field=field,
                        recommendation_type=rec_data['type'],
                        title=rec_data['title'],
                        valid_until__gte=timezone.now(),
                        is_read=False
                    ).first()
                    
                    if not existing:
                        SmartRecommendation.objects.create(
                            field=field,
                            recommendation_type=rec_data['type'],
                            title=rec_data['title'],
                            message=rec_data['message'],
                            urgency=rec_data['urgency'],
                            confidence_score=rec_data['confidence'],
                            valid_until=timezone.now() + timedelta(days=3),
                            recommended_action_date=rec_data.get('recommended_date'),
                            metadata=rec_data.get('factors', {})
                        )
                        total_recommendations += 1
                
                self.stdout.write(f'✓ Generated {len(recommendations)} recommendations for {field.name}')
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error generating recommendations for {field.name}: {str(e)}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated {total_recommendations} new recommendations')
        )