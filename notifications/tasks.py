from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from .models import Notification
from .services import NotificationService
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_pending_notifications():
    """Process all pending notifications"""
    service = NotificationService()
    processed_count = service.process_pending_notifications()
    
    return f"Processed {processed_count} notifications"

@shared_task
def retry_failed_notifications():
    """Retry failed notifications that haven't exceeded max retries"""
    failed_notifications = Notification.objects.filter(
        status='failed',
        retry_count__lt=models.F('max_retries'),
        scheduled_at__gte=timezone.now() - timedelta(hours=24)  # Don't retry very old ones
    )
    
    service = NotificationService()
    retried_count = 0
    
    for notification in failed_notifications:
        try:
            success = service._send_notification(notification)
            if success:
                notification.status = 'sent'
                notification.sent_at = timezone.now()
                retried_count += 1
            else:
                notification.retry_count += 1
            
            notification.save()
        except Exception as e:
            logger.error(f"Retry failed for notification {notification.id}: {e}")
            notification.retry_count += 1
            notification.error_message = str(e)
            notification.save()
    
    return f"Retried {retried_count} failed notifications"

@shared_task
def cleanup_old_notifications():
    """Clean up old notifications to prevent database bloat"""
    cutoff_date = timezone.now() - timedelta(days=90)  # Keep 3 months
    
    # Delete old read notifications
    deleted_count = Notification.objects.filter(
        created_at__lt=cutoff_date,
        read_at__isnull=False
    ).delete()[0]
    
    # Archive very old unread notifications (mark as read)
    archive_cutoff = timezone.now() - timedelta(days=180)  # 6 months
    archived_count = Notification.objects.filter(
        created_at__lt=archive_cutoff,
        read_at__isnull=True
    ).update(read_at=timezone.now())
    
    return f"Deleted {deleted_count} old notifications, archived {archived_count}"

@shared_task
def send_daily_digest():
    """Send daily digest of activities to users who have it enabled"""
    from base.models import User
    from calendar_service.models import Task
    
    # This would be implemented based on user preferences
    # For now, it's a placeholder
    
    users_with_digest = User.objects.filter(
        notification_preferences__isnull=False,
        # Add digest preference field to model
    )
    
    digest_count = 0
    service = NotificationService()
    
    for user in users_with_digest:
        # Get user's tasks for today and tomorrow
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        
        tasks_today = Task.objects.filter(
            assigned_to=user,
            scheduled_date__date=today,
            status='pending'
        )
        
        tasks_tomorrow = Task.objects.filter(
            assigned_to=user,
            scheduled_date__date=tomorrow,
            status='pending'
        )
        
        if tasks_today.exists() or tasks_tomorrow.exists():
            context = {
                'user': user,
                'tasks_today': list(tasks_today),
                'tasks_tomorrow': list(tasks_tomorrow),
                'date': today,
            }
            
            # Create digest notification
            service.send_system_alert(
                [user],
                f"Daily Digest - {today.strftime('%B %d, %Y')}",
                "Your daily task summary",
                context
            )
            digest_count += 1
    
    return f"Sent {digest_count} daily digests"
