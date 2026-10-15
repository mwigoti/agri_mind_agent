from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.timezone import now
from django.contrib.gis.db import models








class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
    
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    registered_via_ussd = models.BooleanField(default=False)
    ussd_registration_date = models.DateTimeField(null=True, blank=True)

    
    objects = CustomUserManager()

    def __str__(self):
        return self.email

class Field(models.Model):
    owner=models.ForeignKey(CustomUser, on_delete=models.CASCADE, default=True)
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    geometry = models.PolygonField(srid=4326, geography=True)
 
    created_at = models.DateTimeField(default=now)
    area = models.FloatField(default=0.0)

    def __str__(self):
        return self.name

class USSDSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=15)
    current_step = models.CharField(max_length=50, default='start')
    data = models.JSONField(default=dict)  # Store temporary registration data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.session_id} - {self.phone_number}"

    class Meta:
        db_table = 'ussd_sessions'
        
        
class Crop(models.Model):
    """Crop types with growing requirements for smart recommendations"""
    name = models.CharField(max_length=100)
    scientific_name = models.CharField(max_length=150, blank=True)
    min_temp = models.IntegerField(help_text="Minimum temperature in Celsius")
    max_temp = models.IntegerField(help_text="Maximum temperature in Celsius")
    optimal_temp_min = models.IntegerField(help_text="Optimal minimum temperature")
    optimal_temp_max = models.IntegerField(help_text="Optimal maximum temperature")
    water_requirement = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='medium'
    )
    growing_season_days = models.IntegerField(help_text="Average growing season in days")
    planting_months = models.JSONField(default=list, help_text="List of optimal planting months (1-12)")
    harvest_months = models.JSONField(default=list, help_text="List of optimal harvest months (1-12)")
    drought_tolerance = models.CharField(
        max_length=20,
        choices=[('low', 'Low'), ('medium', 'Medium'), ('high', 'High')],
        default='medium'
    )
    
    def __str__(self):
        return self.name

class FieldActivity(models.Model):
    """Enhanced activity model with weather correlation"""
    ACTIVITY_TYPES = [
        ('planting', 'Planting'),
        ('harvest', 'Harvest'),
        ('irrigation', 'Irrigation'),
        ('maintenance', 'Maintenance'),
        ('fertilizing', 'Fertilizing'),
        ('pest_control', 'Pest Control'),
        ('soil_preparation', 'Soil Preparation'),
        ('weeding', 'Weeding'),
    ]
    
    PRIORITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    field = models.ForeignKey('Field', on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    crop = models.ForeignKey(Crop, on_delete=models.SET_NULL, null=True, blank=True)
    date = models.DateTimeField()
    duration_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    weather_conditions = models.JSONField(default=dict, blank=True)
    completion_status = models.CharField(
        max_length=20,
        choices=[('planned', 'Planned'), ('in_progress', 'In Progress'), ('completed', 'Completed'), ('cancelled', 'Cancelled')],
        default='planned'
    )
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.field.name} - {self.get_activity_type_display()} - {self.date.strftime('%Y-%m-%d')}"

class WeatherData(models.Model):
    """Store weather data for fields"""
    field = models.ForeignKey('Field', on_delete=models.CASCADE, related_name='weather_data')
    date = models.DateTimeField()
    temperature_min = models.DecimalField(max_digits=5, decimal_places=2)
    temperature_max = models.DecimalField(max_digits=5, decimal_places=2)
    temperature_avg = models.DecimalField(max_digits=5, decimal_places=2)
    humidity = models.DecimalField(max_digits=5, decimal_places=2)
    precipitation = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    wind_speed = models.DecimalField(max_digits=5, decimal_places=2)
    wind_direction = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(360)])
    pressure = models.DecimalField(max_digits=7, decimal_places=2)
    uv_index = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    weather_condition = models.CharField(max_length=50)
    is_forecast = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['field', 'date', 'is_forecast']
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.field.name} - {self.date.strftime('%Y-%m-%d')} - {self.weather_condition}"

class SmartRecommendation(models.Model):
    """AI-powered recommendations based on weather and field conditions"""
    RECOMMENDATION_TYPES = [
        ('activity', 'Activity Recommendation'),
        ('irrigation', 'Irrigation Alert'),
        ('pest_warning', 'Pest Warning'),
        ('weather_alert', 'Weather Alert'),
        ('planting_optimal', 'Optimal Planting Time'),
        ('harvest_optimal', 'Optimal Harvest Time'),
    ]
    
    URGENCY_LEVELS = [
        ('info', 'Information'),
        ('low', 'Low Priority'),
        ('medium', 'Medium Priority'),
        ('high', 'High Priority'),
        ('critical', 'Critical'),
    ]
    
    field = models.ForeignKey('Field', on_delete=models.CASCADE, related_name='recommendations')
    recommendation_type = models.CharField(max_length=20, choices=RECOMMENDATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    urgency = models.CharField(max_length=10, choices=URGENCY_LEVELS, default='info')
    confidence_score = models.DecimalField(max_digits=3, decimal_places=2, default=0.5)
    valid_from = models.DateTimeField(default=now)
    valid_until = models.DateTimeField()
    is_read = models.BooleanField(default=False)
    is_acted_upon = models.BooleanField(default=False)
    related_weather = models.ForeignKey(WeatherData, on_delete=models.SET_NULL, null=True, blank=True)
    recommended_action_date = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-urgency', '-created_at']
    
    def __str__(self):
        return f"{self.field.name} - {self.title}"

class CropGrowthStage(models.Model):
    """Track crop growth stages for better recommendations"""
    GROWTH_STAGES = [
        ('seedling', 'Seedling'),
        ('vegetative', 'Vegetative'),
        ('flowering', 'Flowering'),
        ('fruiting', 'Fruiting'),
        ('maturation', 'Maturation'),
        ('harvest_ready', 'Harvest Ready'),
    ]
    
    field = models.ForeignKey('Field', on_delete=models.CASCADE, related_name='growth_stages')
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE)
    stage = models.CharField(max_length=20, choices=GROWTH_STAGES)
    start_date = models.DateField()
    expected_end_date = models.DateField()
    actual_end_date = models.DateField(null=True, blank=True)
    stage_health = models.CharField(
        max_length=20,
        choices=[('poor', 'Poor'), ('fair', 'Fair'), ('good', 'Good'), ('excellent', 'Excellent')],
        default='good'
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['field', 'crop', 'stage', 'start_date']
    
    def __str__(self):
        return f"{self.field.name} - {self.crop.name} - {self.get_stage_display()}"

class WeatherAlert(models.Model):
    """Weather alerts for field management"""
    ALERT_TYPES = [
        ('frost', 'Frost Warning'),
        ('drought', 'Drought Alert'),
        ('heavy_rain', 'Heavy Rain Warning'),
        ('hail', 'Hail Alert'),
        ('high_wind', 'High Wind Warning'),
        ('extreme_heat', 'Extreme Heat Alert'),
    ]
    
    field = models.ForeignKey('Field', on_delete=models.CASCADE, related_name='weather_alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(
        max_length=10,
        choices=[('minor', 'Minor'), ('moderate', 'Moderate'), ('major', 'Major'), ('severe', 'Severe')],
        default='moderate'
    )
    message = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    recommended_actions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-severity', '-start_time']
    
    def __str__(self):
        return f"{self.field.name} - {self.get_alert_type_display()} - {self.get_severity_display()}"

class ActivityOptimization(models.Model):
    """Store optimization data for activity timing"""
    field = models.ForeignKey('Field', on_delete=models.CASCADE, related_name='optimizations')
    activity_type = models.CharField(max_length=20, choices=FieldActivity.ACTIVITY_TYPES)
    optimal_date_range_start = models.DateTimeField()
    optimal_date_range_end = models.DateTimeField()
    weather_score = models.DecimalField(max_digits=3, decimal_places=2)
    crop_stage_score = models.DecimalField(max_digits=3, decimal_places=2)
    overall_score = models.DecimalField(max_digits=3, decimal_places=2)
    factors_considered = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-overall_score']
    
    def __str__(self):
        return f"{self.field.name} - {self.get_activity_type_display()} - Score: {self.overall_score}"