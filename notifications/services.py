from django.utils import timezone
from django.template import Template, Context
from django.conf import settings
from datetime import datetime, timedelta
from .models import Notification, NotificationTemplate, NotificationPreference
from external_apis.sms_client import SMSService
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    """Main notification orchestration service"""
    
    def __init__(self):
        self.sms_service = SMSService()
    
    def send_task_reminder(self, task, hours_before=24):
        """Send reminder notification for upcoming task"""
        users_to_notify = [task.assigned_to]
        
        # Also notify farm owner if different
        if task.farm.owner != task.assigned_to:
            users_to_notify.append(task.farm.owner)
        
        template = NotificationTemplate.objects.filter(
            template_type='task_reminder',
            is_active=True
        ).first()
        
        for user in users_to_notify:
            if self._should_send_notification(user, 'task_reminders'):
                context = {
                    'task': task,
                    'user': user,
                    'farm': task.farm,
                    'field': task.field,
                    'hours_before': hours_before,
                }
                
                self._create_notification(
                    user, template, context,
                    scheduled_at=timezone.now()
                )
    
    def send_weather_warning(self, task, weather_data):
        """Send weather-related warning for task"""
        template = NotificationTemplate.objects.filter(
            template_type='weather_warning',
            is_active=True
        ).first()
        
        context = {
            'task': task,
            'weather': weather_data,
            'warnings': weather_data.get('warnings', []),
            'recommendations': weather_data.get('recommendations', []),
        }
        
        users_to_notify = [task.assigned_to, task.farm.owner]
        
        for user in set(users_to_notify):  # Remove duplicates
            if self._should_send_notification(user, 'weather_alerts'):
                self._create_notification(
                    user, template, context,
                    scheduled_at=timezone.now()
                )
    
    def send_weather_suggestions(self, task, suggestions):
        """Send weather-based scheduling suggestions"""
        template = NotificationTemplate.objects.filter(
            template_type='weather_warning',  # Reuse template
            is_active=True
        ).first()
        
        context = {
            'task': task,
            'suggestions': suggestions[:3],  # Top 3 suggestions
            'current_date': task.scheduled_date,
        }
        
        if self._should_send_notification(task.assigned_to, 'weather_alerts'):
            self._create_notification(
                task.assigned_to, template, context,
                scheduled_at=timezone.now()
            )
    
    def send_compliance_reminder(self, task, days_until_due=7):
        """Send compliance deadline reminder"""
        template = NotificationTemplate.objects.filter(
            template_type='compliance_due',
            is_active=True
        ).first()
        
        context = {
            'task': task,
            'days_until_due': days_until_due,
            'compliance': getattr(task, 'compliance', None),
        }
        
        # Notify farm owner for compliance matters
        if self._should_send_notification(task.farm.owner, 'compliance_reminders'):
            self._create_notification(
                task.farm.owner, template, context,
                scheduled_at=timezone.now()
            )
    
    def send_system_alert(self, users, title, message, context_data=None):
        """Send system-wide alerts"""
        template = NotificationTemplate.objects.filter(
            template_type='system_alert',
            is_active=True
        ).first()
        
        context = {
            'title': title,
            'message': message,
            'context_data': context_data or {},
        }
        
        for user in users:
            if self._should_send_notification(user, 'system_notifications'):
                self._create_notification(
                    user, template, context,
                    scheduled_at=timezone.now()
                )
    
    def _should_send_notification(self, user, notification_type):
        """Check if notification should be sent based on user preferences"""
        try:
            prefs = user.notification_preferences
            return getattr(prefs, notification_type, True)
        except NotificationPreference.DoesNotExist:
            return False  # No quiet hours if no preferences
    
    def _create_notification(self, user, template, context, scheduled_at=None):
        """Create notification records for different channels"""
        if scheduled_at is None:
            scheduled_at = timezone.now()
        
        # Check if it's quiet hours for push/SMS
        is_quiet = self._is_quiet_hours(user)
        
        try:
            prefs = user.notification_preferences
        except NotificationPreference.DoesNotExist:
            # Create default preferences
            prefs = NotificationPreference.objects.create(user=user)
        
        # Render templates
        if template:
            title = self._render_template(template.subject_template, context)
            message = self._render_template(template.body_template, context)
        else:
            title = context.get('title', 'Notification')
            message = context.get('message', '')
        
        notifications_created = []
        
        # Email notification (not affected by quiet hours)
        if prefs.email_enabled and user.email:
            notification = Notification.objects.create(
                recipient=user,
                notification_type='email',
                template=template,
                title=title,
                message=message,
                scheduled_at=scheduled_at,
                task=context.get('task'),
                farm=context.get('farm'),
                context_data=context
            )
            notifications_created.append(notification)
        
        # SMS notification (respect quiet hours)
        if prefs.sms_enabled and user.phone_number and not is_quiet:
            sms_message = template.sms_template if template else message[:160]
            sms_message = self._render_template(sms_message, context)
            
            notification = Notification.objects.create(
                recipient=user,
                notification_type='sms',
                template=template,
                title=title,
                message=sms_message,
                scheduled_at=scheduled_at,
                task=context.get('task'),
                farm=context.get('farm'),
                context_data=context
            )
            notifications_created.append(notification)
        
        # Push notification (respect quiet hours)
        if prefs.push_enabled and not is_quiet:
            push_title = template.push_title_template if template else title
            push_body = template.push_body_template if template else message
            
            notification = Notification.objects.create(
                recipient=user,
                notification_type='push',
                template=template,
                title=self._render_template(push_title, context),
                message=self._render_template(push_body, context),
                scheduled_at=scheduled_at,
                task=context.get('task'),
                farm=context.get('farm'),
                context_data=context
            )
            notifications_created.append(notification)
        
        # In-app notification (always create)
        notification = Notification.objects.create(
            recipient=user,
            notification_type='in_app',
            template=template,
            title=title,
            message=message,
            scheduled_at=scheduled_at,
            task=context.get('task'),
            farm=context.get('farm'),
            context_data=context
        )
        notifications_created.append(notification)
        
        return notifications_created
    
    def _render_template(self, template_string, context):
        """Render Django template string with context"""
        if not template_string:
            return ""
        
        try:
            template = Template(template_string)
            return template.render(Context(context))
        except Exception as e:
            logger.error(f"Template rendering error: {e}")
            return template_string  # Return original if rendering fails
    
    def process_pending_notifications(self):
        """Process all pending notifications"""
        pending_notifications = Notification.objects.filter(
            status='pending',
            scheduled_at__lte=timezone.now()
        ).order_by('scheduled_at')
        
        processed_count = 0
        
        for notification in pending_notifications:
            try:
                success = self._send_notification(notification)
                if success:
                    notification.status = 'sent'
                    notification.sent_at = timezone.now()
                    processed_count += 1
                else:
                    notification.status = 'failed'
                    notification.retry_count += 1
            except Exception as e:
                logger.error(f"Failed to send notification {notification.id}: {e}")
                notification.status = 'failed'
                notification.error_message = str(e)
                notification.retry_count += 1
            
            notification.save()
        
        return processed_count
    
    def _send_notification(self, notification):
        """Send individual notification based on type"""
        if notification.notification_type == 'email':
            return self._send_email(notification)
        elif notification.notification_type == 'sms':
            return self._send_sms(notification)
        elif notification.notification_type == 'push':
            return self._send_push(notification)
        elif notification.notification_type == 'whatsapp':
            return self._send_whatsapp(notification)
        elif notification.notification_type == 'in_app':
            return True  # In-app notifications are already "sent" when created
        
        return False
    
    def _send_email(self, notification):
        """Send email notification"""
        from django.core.mail import send_mail
        
        try:
            send_mail(
                subject=notification.title,
                message=notification.message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[notification.recipient.email],
                fail_silently=False,
            )
            return True
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
            return False
    
    def _send_sms(self, notification):
        """Send SMS notification"""
        try:
            result = self.sms_service.send_sms(
                to=notification.recipient.phone_number,
                message=notification.message
            )
            
            if result.get('success'):
                notification.external_id = result.get('message_id', '')
                return True
            else:
                notification.error_message = result.get('error', 'SMS sending failed')
                return False
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
            notification.error_message = str(e)
            return False
    
    def _send_push(self, notification):
        """Send push notification (placeholder for push service)"""
        # This would integrate with Firebase, OneSignal, etc.
        logger.info(f"Push notification would be sent to {notification.recipient.username}")
        return True
    
    def _send_whatsapp(self, notification):
        """Send WhatsApp notification"""
        try:
            result = self.sms_service.send_whatsapp(
                to=notification.recipient.phone_number,
                message=notification.message
            )
            
            if result.get('success'):
                notification.external_id = result.get('message_id', '')
                return True
            else:
                notification.error_message = result.get('error', 'WhatsApp sending failed')
                return False
        except Exception as e:
            logger.error(f"WhatsApp sending failed: {e}")
            notification.error_message = str(e)
            return False
