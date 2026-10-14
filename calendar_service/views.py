from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q
from datetime import datetime, timedelta
from .models import Task, TaskCategory, TaskTemplate, ComplianceRecord
from .serializers import (TaskSerializer, TaskCategorySerializer, 
                         TaskTemplateSerializer, ComplianceRecordSerializer,
                         TaskCreateSerializer)
from .services import TaskSchedulingService, WeatherTaskService
from base.permissions import IsFarmMemberOrOwner

class TaskCategoryViewSet(viewsets.ModelViewSet):
    queryset = TaskCategory.objects.all()
    serializer_class = TaskCategorySerializer
    permission_classes = [permissions.IsAuthenticated]

class TaskViewSet(viewsets.ModelViewSet):
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated, IsFarmMemberOrOwner]
    
    def get_queryset(self):
        queryset = Task.objects.filter(
            Q(farm__owner=self.request.user) | 
            Q(farm__members=self.request.user) |
            Q(assigned_to=self.request.user)
        ).distinct()
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date and end_date:
            queryset = queryset.filter(
                scheduled_date__date__range=[start_date, end_date]
            )
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        # Filter by field
        field_id = self.request.query_params.get('field')
        if field_id:
            queryset = queryset.filter(field_id=field_id)
            
        return queryset.select_related('category', 'field', 'assigned_to', 'farm')
    
    def get_serializer_class(self):
        if self.action == 'create':
            return TaskCreateSerializer
        return TaskSerializer
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Mark task as completed"""
        task = self.get_object()
        task.status = 'completed'
        task.completed_at = timezone.now()
        task.completion_notes = request.data.get('notes', '')
        task.completion_photos = request.data.get('photos', [])
        task.save()
        
        # Create next recurring instance if applicable
        if task.recurrence_type != 'none':
            TaskSchedulingService.create_next_recurring_task(task)
        
        return Response({'status': 'Task completed successfully'})
    
    @action(detail=True, methods=['post'])
    def postpone(self, request, pk=None):
        """Postpone task to new date"""
        task = self.get_object()
        new_date = request.data.get('new_date')
        reason = request.data.get('reason', '')
        
        if not new_date:
            return Response({'error': 'new_date is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        task.scheduled_date = new_date
        task.status = 'postponed'
        task.completion_notes = f"Postponed: {reason}"
        task.save()
        
        return Response({'status': 'Task postponed successfully'})
    
    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        """Get tasks formatted for calendar display"""
        queryset = self.get_queryset()
        
        calendar_data = []
        for task in queryset:
            calendar_data.append({
                'id': str(task.id),
                'title': task.title,
                'start': task.scheduled_date.isoformat(),
                'end': (task.scheduled_date + task.estimated_duration).isoformat(),
                'backgroundColor': task.category.color if task.category else '#3B82F6',
                'extendedProps': {
                    'status': task.status,
                    'priority': task.priority,
                    'field': task.field.name if task.field else None,
                    'assigned_to': task.assigned_to.get_full_name(),
                    'weather_dependent': task.weather_dependent,
                }
            })
        
        return Response(calendar_data)
    
    @action(detail=False, methods=['get'])
    def dashboard_stats(self, request):
        """Get dashboard statistics"""
        queryset = self.get_queryset()
        today = timezone.now().date()
        
        stats = {
            'total_tasks': queryset.count(),
            'pending_tasks': queryset.filter(status='pending').count(),
            'overdue_tasks': queryset.filter(
                status='pending', 
                scheduled_date__date__lt=today
            ).count(),
            'completed_today': queryset.filter(
                status='completed',
                completed_at__date=today
            ).count(),
            'upcoming_this_week': queryset.filter(
                status='pending',
                scheduled_date__date__range=[
                    today, 
                    today + timedelta(days=7)
                ]
            ).count(),
        }
        
        return Response(stats)
    
    @action(detail=False, methods=['post'])
    def weather_check(self, request):
        """Check weather suitability for upcoming tasks"""
        upcoming_tasks = self.get_queryset().filter(
            status='pending',
            weather_dependent=True,
            scheduled_date__date__range=[
                timezone.now().date(),
                timezone.now().date() + timedelta(days=3)
            ]
        )
        
        weather_service = WeatherTaskService()
        results = []
        
        for task in upcoming_tasks:
            suitability = weather_service.check_task_weather_suitability(task)
            results.append({
                'task_id': str(task.id),
                'task_title': task.title,
                'scheduled_date': task.scheduled_date,
                'suitable': suitability['suitable'],
                'warnings': suitability['warnings'],
                'recommendations': suitability['recommendations']
            })
        
        return Response(results)

class TaskTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TaskTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, IsFarmMemberOrOwner]
    
    def get_queryset(self):
        return TaskTemplate.objects.filter(
            Q(farm__owner=self.request.user) | 
            Q(farm__members=self.request.user)
        ).distinct()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def create_task(self, request, pk=None):
        """Create a new task from template"""
        template = self.get_object()
        task_data = request.data.copy()
        
        # Set template defaults
        task_data.update({
            'title': template.name,
            'description': template.description,
            'category': template.category.id,
            'estimated_duration': template.estimated_duration,
            'weather_dependent': template.weather_dependent,
        })
        
        serializer = TaskCreateSerializer(data=task_data, context={'request': request})
        if serializer.is_valid():
            task = serializer.save()
            return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ComplianceRecordViewSet(viewsets.ModelViewSet):
    serializer_class = ComplianceRecordSerializer
    permission_classes = [permissions.IsAuthenticated, IsFarmMemberOrOwner]
    
    def get_queryset(self):
        return ComplianceRecord.objects.filter(
            Q(task__farm__owner=self.request.user) | 
            Q(task__farm__members=self.request.user)
        ).distinct()

# Create your views here.
