from django.urls import path
from .views import *
from .views import SaveFieldView, DeleteFieldView, VRAAnalysisView, USSDView

urlpatterns = [
    # Basic pages
    path('', home, name='home'),
    path('services/', services, name='services'),
    path('contact/', contact, name='contact'),
    path('research/', research, name='research'),
    path('register/', register, name='register'),
    path('map/', map, name='map'),
    
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
]