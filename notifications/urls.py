from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NotificationViewSet, NotificationPreferenceViewSet, NotificationTemplateViewSet

router = DefaultRouter()
router.register(r'notifications', NotificationViewSet, basename='notification')
router.register(r'preferences', NotificationPreferenceViewSet, basename='preference')
router.register(r'templates', NotificationTemplateViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
  # Default to sending if no preferences set
    
def _is_quiet_hours(self, user):
        """Check if current time is within user's quiet hours"""
        try:
            prefs = user.notification_preferences
            now_time = timezone.now().time()
            
            if prefs.quiet_hours_start < prefs.quiet_hours_end:
                # Same day quiet hours (e.g., 22:00 to 07:00 next day)
                return prefs.quiet_hours_start <= now_time <= prefs.quiet_hours_end
            else:
                # Cross-midnight quiet hours
                return now_time >= prefs.quiet_hours_start or now_time <= prefs.quiet_hours_end
        except NotificationPreference.DoesNotExist:urlpatterns = [
    path('', include(router.urls)),
]