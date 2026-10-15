from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Task
from .services import TaskSchedulingService, WeatherTaskService
from notifications.services import NotificationService

@shared_task
def create_recurring_tasks():
    """Create recurring task instances"""
    completed_tasks = Task.objects.filter(
        status='completed',
        recurrence_type__in=['daily', 'weekly', 'monthly', 'seasonal']
    ).exclude(recurrence_type='none')
    
    for task in completed_tasks:
        # Check if next instance doesn't already exist
        next_date = TaskSchedulingService._calculate_next_occurrence(
            task.scheduled_date,
            task.recurrence_type,
            task.recurrence_interval
        )
        
        existing = Task.objects.filter(
            parent_task=task.parent_task or task,
            scheduled_date__date=next_date.date()
        ).exists()
        
        if not existing:
            TaskSchedulingService.create_next_recurring_task(task)

@shared_task
def send_task_reminders():
    """Send reminders for upcoming tasks"""
    tomorrow = timezone.now() + timedelta(days=1)
    
    upcoming_tasks = Task.objects.filter(
        status='pending',
        scheduled_date__date=tomorrow.date()
    ).select_related('assigned_to', 'farm')
    
    notification_service = NotificationService()
    
    for task in upcoming_tasks:
        notification_service.send_task_reminder(task)

@shared_task
def check_weather_dependent_tasks():
    """Check weather conditions for upcoming weather-dependent tasks"""
    weather_service = WeatherTaskService()
    
    # Check tasks for next 3 days
    end_date = timezone.now() + timedelta(days=3)
    weather_tasks = Task.objects.filter(
        status='pending',
        weather_dependent=True,
        scheduled_date__lte=end_date
    )
    
    notification_service = NotificationService()
    
    for task in weather_tasks:
        suitability = weather_service.check_task_weather_suitability(task)
        
        if not suitability['suitable']:
            # Send weather warning
            notification_service.send_weather_warning(task, suitability)
            
            # Auto-suggest better dates
            suggestions = weather_service.suggest_optimal_dates(task)
            if suggestions:
                notification_service.send_weather_suggestions(task, suggestions)

@shared_task
def mark_overdue_tasks():
    """Mark overdue tasks"""
    now = timezone.now()
    
    overdue_tasks = Task.objects.filter(
        status='pending',
        scheduled_date__lt=now
    )
    
    count = overdue_tasks.update(status='overdue')
    return f"Marked {count} tasks as overdue"