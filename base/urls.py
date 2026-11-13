from django.contrib import admin
from django.urls import path
from .views import *
from .views import SaveFieldView, DeleteFieldView, VRAAnalysisView, USSDView
from . import views_agent
from . import views_chat

urlpatterns = [
        path(
        'api/analyze-crop/',
        AnalyzeCropView.as_view(),
        name='analyze_crop',
    ),
 
    # Polled every 4 s by the frontend JS  →  GET  returns pipeline status + metrics
    path(
        'api/analysis-status/<int:pk>/',
        AnalysisStatusView.as_view(),
        name='analysis_status',
    ),

        path('api/field-metrics/', upload_field_metric, name='field_metrics'),
        path('api/dashboard/field/<int:field_id>/', field_dashboard_summary, name='field_dashboard_summary'),
        path('api/advisory-review/<int:review_id>/decision/', advisory_review_decision, name='advisory_review_decision'),

    # Basic pages
    path('', home, name='home'),
    path('services/', services, name='services'),
    path('contact/', contact, name='contact'),
    path('research/', research, name='research'),
    path('register/', register, name='register'),
    path('map/', map, name='map'),
    path('health/', health, name='health'),
    path('api/register-crop/', register_crop_monitoring, name='register_crop_monitoring'),
    
    # Auth and pricing
    path('login/', login_view, name="login"),
    path('logout/', logout_user, name='logout'),
    path('pricing/', pricing, name="pricing"),
    path('upgrade/', upgrade, name="upgrade"),
    
    # Field management
    path('save-field/', SaveFieldView.as_view(), name='save-field'),
    path('api/myfields/', get_fields_geojson, name='api-myfields'),
    path('api/delete-field/<int:id>/', DeleteFieldView.as_view(), name='delete-field'),
    path('api/analyze-field/<int:id>/', analyze_field_view, name="analyze-field"),
    path('api/get-active-crops/', get_active_crops, name='get_active_crops'),
    
    # VRA (Variable Rate Application)
    path('res/', res, name='res'),
    path('api/vra-analysis/<int:field_id>/', VRAAnalysisView.as_view(), name='vra-analysis-api'),
    path('vra_page/<int:field_id>/', vra_page, name='vra-page'),
    path('api/vra-engine-status/', check_vra_engine_status, name='vra-engine-status'),
    
    # Activities
    path('field_activity/', activity, name='activity'),


    
    # Weather integration
    path('weather/', weather, name='weather'),
    
    
    # Smart recommendations
    path('recommendations/<int:field_id>/', get_smart_recommendations, name='get_smart_recommendations'),
    path('recommendations/<int:recommendation_id>/read/', mark_recommendation_read, name='mark_recommendation_read'),
    
    # Optimization
    path('optimization/<int:field_id>/', get_activity_optimization, name='get_activity_optimization'),
    
    # USSD integration
    path('ussd/callback/', USSDView.as_view(), name='ussd_callback'),
    path('seasons/', seasons, name = 'seasons'),
    path('api/analyze-crop/', analyze_crop, name='analyze_crop'),
    path('api/analysis-status/<int:result_id>/', 
         analysis_status, name='analysis_status'),
    
    # Report generation
    path('api/report/', generate_report, name='generate_report'),
    
    # Individual analysis endpoints
    path('api/indices/', get_vegetation_indices, name='get_indices'),
    path('api/yield/', get_yield_prediction, name='get_yield'),
    path('api/health/', get_health_score, name='get_health'),
    path('api/trends/', analyze_temporal_trends, name='analyze_trends'),
    path('api/zones/', create_management_zones, name='create_zones'),
    
    # Health check
    path('api/health-check/', health_check, name='health_check'),

    # AgriMind Agent Integration Endpoints
    path('api/agent/status/', views_agent.AgriMindStatusView.as_view(), name='agrimind_status'),
    path('api/agent/advisory/<int:field_id>/', views_agent.AgriMindFieldAdvisoryView.as_view(), name='agrimind_field_advisory'),
    path('api/agent/decide/<str:thread_id>/', views_agent.AgriMindDecisionView.as_view(), name='agrimind_decision'),
    path('api/agent/rankings/', views_agent.AgriMindRankingsView.as_view(), name='agrimind_rankings'),
    path('api/agent/chat/', views_chat.ChatAPIView.as_view(), name='agrimind_chat'),
    path('chat/', views_chat.chat_page, name='chat'),
]
