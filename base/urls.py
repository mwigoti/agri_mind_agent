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
    path('login/', login, name="login"),
    path('pricing/', pricing, name="pricing"),
    
    path('save-field/', SaveFieldView.as_view(), name='save-field'),
     path('api/myfields/', get_fields_geojson, name='api-myfields'),
    
]
