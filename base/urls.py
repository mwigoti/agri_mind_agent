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
    path('api/send-report/', send_analysis_report, name='send_report'),
    path('api/test-email/', test_email_config, name='test_email'),
]
