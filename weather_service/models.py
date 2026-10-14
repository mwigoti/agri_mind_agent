from django.db import models

from django.contrib.gis.db import models as gis_models
import uuid

class WeatherStation(models.Model):
    """Weather station data source"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    location = gis_models.PointField()
    provider = models.CharField(max_length=100)  # Meteomatics, OpenWeather, etc.
    station_id = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.provider})"

class WeatherForecast(models.Model):
    """Cached weather forecast data"""
    location = gis_models.PointField()
    forecast_date = models.DateField()
    forecast_time = models.TimeField(null=True, blank=True)
    
    # Temperature data
    temperature = models.FloatField(null=True, blank=True)  # Current/avg temp
    min_temperature = models.FloatField(null=True, blank=True)
    max_temperature = models.FloatField(null=True, blank=True)
    feels_like = models.FloatField(null=True, blank=True)
    
    # Precipitation
    precipitation = models.FloatField(default=0)  # mm
    precipitation_probability = models.IntegerField(default=0)  # %
    humidity = models.IntegerField(null=True, blank=True)  # %
    
    # Wind
    wind_speed = models.FloatField(null=True, blank=True)  # km/h
    wind_direction = models.IntegerField(null=True, blank=True)  # degrees
    wind_gust = models.FloatField(null=True, blank=True)  # km/h
    
    # Other conditions
    pressure = models.FloatField(null=True, blank=True)  # hPa
    visibility = models.FloatField(null=True, blank=True)  # km
    uv_index = models.IntegerField(null=True, blank=True)
    cloud_cover = models.IntegerField(null=True, blank=True)  # %
    
    # Metadata
    weather_condition = models.CharField(max_length=100, blank=True)  # sunny, rainy, etc.
    weather_description = models.CharField(max_length=255, blank=True)
    provider = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['location', 'forecast_date', 'forecast_time', 'provider']
        indexes = [
            models.Index(fields=['forecast_date', 'location']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Weather for {self.forecast_date} - {self.temperature}°C"

class WeatherAlert(models.Model):
    """Weather alerts and warnings"""
    ALERT_TYPES = [
        ('frost', 'Frost Warning'),
        ('heat', 'Heat Warning'),
        ('wind', 'High Wind'),
        ('rain', 'Heavy Rain'),
        ('storm', 'Storm Warning'),
        ('drought', 'Drought Conditions'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('extreme', 'Extreme'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    location = gis_models.PointField()
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.get_alert_type_display()} - {self.get_severity_display()}"

