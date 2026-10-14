from django.db import models

# Create your models here.

from django.contrib.auth import get_user_model
from base.models import Field
import uuid
from datetime import datetime, timedelta

User = get_user_model()

class TaskCategory(models.Model):
    """Categories for different types of farming tasks"""
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default='#3B82F6')  # Hex color
    
    class Meta:
        verbose_name_plural = "Task Categories"
    
    def __str__(self):
        return self.name

class Task(models.Model):
    """Core task model with recurrence support"""
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'), 
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('postponed', 'Postponed'),
    ]
    
    RECURRENCE_CHOICES = [
        ('none', 'No Recurrence'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('seasonal', 'Seasonal'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(TaskCategory, on_delete=models.SET_NULL, null=True)
    
    # Assignment
    farm = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='tasks')
    field = models.ForeignKey(Field, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='assigned_tasks')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    
    # Scheduling
    scheduled_date = models.DateTimeField()
    due_date = models.DateTimeField(null=True, blank=True)
    estimated_duration = models.DurationField(default=timedelta(hours=1))
    
    # Status and priority
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    
    # Recurrence
    recurrence_type = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default='none')
    recurrence_interval = models.PositiveIntegerField(default=1)  # Every X days/weeks/months
    recurrence_end_date = models.DateField(null=True, blank=True)
    parent_task = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='recurring_instances')
    
    # Completion tracking
    completed_at = models.DateTimeField(null=True, blank=True)
    completion_notes = models.TextField(blank=True)
    completion_photos = models.JSONField(default=list)  # Store photo URLs
    
    # Weather sensitivity
    weather_dependent = models.BooleanField(default=False)
    min_temperature = models.FloatField(null=True, blank=True)
    max_temperature = models.FloatField(null=True, blank=True)
    max_wind_speed = models.FloatField(null=True, blank=True)
    avoid_rain = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['scheduled_date', 'priority']
        indexes = [
            models.Index(fields=['farm', 'scheduled_date']),
            models.Index(fields=['assigned_to', 'status']),
            models.Index(fields=['field', 'scheduled_date']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.farm.name} ({self.get_status_display()})"

class TaskTemplate(models.Model):
    """Reusable task templates"""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(TaskCategory, on_delete=models.CASCADE)
    estimated_duration = models.DurationField(default=timedelta(hours=1))
    weather_dependent = models.BooleanField(default=False)
    instructions = models.TextField(blank=True)
    farm = models.ForeignKey(Farm, on_delete=models.CASCADE, related_name='task_templates')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} - {self.farm.name}"

class ComplianceRecord(models.Model):
    """Compliance and certification records linked to tasks"""
    task = models.OneToOneField(Task, on_delete=models.CASCADE, related_name='compliance')
    certification_type = models.CharField(max_length=100)  # Organic, GAP, etc.
    inspector_notes = models.TextField(blank=True)
    documents = models.JSONField(default=list)  # Document URLs
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"Compliance: {self.task.title} - {self.certification_type}"
