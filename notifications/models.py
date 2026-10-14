from django.db import models

from django.contrib.auth import get_user_model
from base.models import Field
from calendar_service.models import Task
import uuid

User = get_user_model()

class NotificationTemplate(models.Model):
    """Templates for different types of notifications"""
    TEMPLATE_TYPES = [
        ('task_reminder', 'Task Reminder'),
        ('task_overdue', 'Task Overdue'),
        ('weather_warning', 'Weather Warning'),
        ('system_alert', 'System Alert'),
        ('compliance_due', 'Compliance Due'),
    ]
    
    name = models.CharField(max_length=255)
    template_type = models.CharField(max_length=50, choices=TEMPLATE_TYPES)
    subject_template = models.CharField(max_length=255)
    body_template = models.TextField()
    sms_template = models.CharField(max_length=160, blank=True)  # SMS character limit
    push_title_template = models.CharField(max_length=100, blank=True)
    push_body_template = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"

class Notification(models.Model):
    """Individual notification records"""
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('push', 'Push Notification'),
        ('whatsapp', 'WhatsApp'),
        ('in_app', 'In-App Notification'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Content
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Metadata
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    scheduled_at = models.DateTimeField()
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Context
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True)
    farm = models.ForeignKey(Field, on_delete=models.CASCADE, null=True, blank=True)
    context_data = models.JSONField(default=dict)
    
    # Delivery tracking
    external_id = models.CharField(max_length=255, blank=True)  # Provider message ID
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    max_retries = models.IntegerField(default=3)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['scheduled_at', 'status']),
            models.Index(fields=['notification_type', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.recipient.username} ({self.get_status_display()})"

class NotificationPreference(models.Model):
    """User notification preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Notification types preferences
    email_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    whatsapp_enabled = models.BooleanField(default=False)
    
    # Content preferences
    task_reminders = models.BooleanField(default=True)
    weather_alerts = models.BooleanField(default=True)
    compliance_reminders = models.BooleanField(default=True)
    system_notifications = models.BooleanField(default=True)
    
    # Timing preferences
    quiet_hours_start = models.TimeField(default='22:00')
    quiet_hours_end = models.TimeField(default='07:00')
    timezone = models.CharField(max_length=50, default='Africa/Nairobi')
    
    # Frequency limits
    max_sms_per_day = models.IntegerField(default=10)
    max_email_per_day = models.IntegerField(default=50)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
