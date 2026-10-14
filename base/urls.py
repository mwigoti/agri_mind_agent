from django.urls import path
from .models import *
from .views import *


urlpatterns = [
    path('', home, name='home'),    
    path('services/', services, name='services'),
    path('contact/', contact, name='contact'),
    path('research/', research, name='research'),
    path('register/', register, name='register'),
    path('map/', map, name='map'),
    
    path('weather/', weather, name='weather'),
    path('upgrade/', upgrade, name="upgrade"),
    path('login/', login_view, name="login"),
    path('logout/', logout_user, name='logout'),
    path('pricing/', pricing, name="pricing"),    
    path('save-field/', SaveFieldView.as_view(), name='save-field'),
    path('api/myfields/', get_fields_geojson, name='api-myfields'),
    path('api/delete-field/<int:id>/', DeleteFieldView.as_view(), name='delete-field'), 
    path('api/analyze-field/<int:id>/', analyze_field_view, name="analyze-field"),
    
    path('res/', res, name='res'),
    path('api/vra-analysis/<int:field_id>/', VRAAnalysisView.as_view(), name='vra-analysis-api'),
    path('vra_pageanalysis/<int:field_id>/', vra_page, name='vra-page' ),
    path('api/vra-engine-status/', check_vra_engine_status, name='vra-engine-status'),
   
]
