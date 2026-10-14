from django.shortcuts import render

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from .models import Notification, NotificationTemplate, NotificationPreference
from .serializers import (NotificationSerializer, NotificationTemplateSerializer, 
                         NotificationPreferenceSerializer)
from .services import NotificationService

class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = Notification.objects.filter(
            recipient=self.request.user
        )
        
        # Filter by type
        notification_type = self.request.query_params.get('type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by read/unread
        unread_only = self.request.query_params.get('unread')
        if unread_only and unread_only.lower() == 'true':
            queryset = queryset.filter(read_at__isnull=True)
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark notification as read"""
        notification = self.get_object()
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save()
        
        return Response({'status': 'marked as read'})
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """Mark all notifications as read"""
        updated_count = Notification.objects.filter(
            recipient=request.user,
            read_at__isnull=True
        ).update(read_at=timezone.now())
        
        return Response({'status': f'{updated_count} notifications marked as read'})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = Notification.objects.filter(
            recipient=request.user,
            read_at__isnull=True
        ).count()
        
        return Response({'unread_count': count})
    
    @action(detail=False, methods=['get'])
    def dashboard_summary(self, request):
        """Get notification summary for dashboard"""
        user_notifications = Notification.objects.filter(recipient=request.user)
        
        summary = {
            'total': user_notifications.count(),
            'unread': user_notifications.filter(read_at__isnull=True).count(),
            'recent': user_notifications.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=7)
            ).count(),
            'by_type': {}
        }
        
        # Count by notification type
        for choice in Notification.NOTIFICATION_TYPES:
            type_code = choice[0]
            count = user_notifications.filter(notification_type=type_code).count()
            summary['by_type'][type_code] = count
        
        return Response(summary)

class NotificationPreferenceViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return NotificationPreference.objects.filter(user=self.request.user)
    
    def get_object(self):
        """Get or create notification preferences for the user"""
        try:
            return NotificationPreference.objects.get(user=self.request.user)
        except NotificationPreference.DoesNotExist:
            return NotificationPreference.objects.create(user=self.request.user)
    
    @action(detail=False, methods=['get', 'post'])
    def my_preferences(self, request):
        """Get or update user's notification preferences"""
        preferences = self.get_object()
        
        if request.method == 'GET':
            serializer = self.get_serializer(preferences)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            serializer = self.get_serializer(preferences, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class NotificationTemplateViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NotificationTemplate.objects.filter(is_active=True)
    serializer_class = NotificationTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

