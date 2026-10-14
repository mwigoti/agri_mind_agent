from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TaskViewSet, TaskCategoryViewSet, TaskTemplateViewSet, ComplianceRecordViewSet

router = DefaultRouter()
router.register(r'tasks', TaskViewSet, basename='task')
router.register(r'categories', TaskCategoryViewSet)
router.register(r'templates', TaskTemplateViewSet, basename='template')
router.register(r'compliance', ComplianceRecordViewSet, basename='compliance')

urlpatterns = [
    path('', include(router.urls)),
]# AgriVision Django Project Structure
