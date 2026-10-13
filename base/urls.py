from django.urls import path
from . import views
from . import models

urlpatterns = [
    path('', views.home, name='home'),
    
    path('services/', views.services, name='services'),
    path('contact/', views.contact, name='contact'),
    path('research/', views.research, name='research'),
    path('register/', views.register, name='register'),
    path('map/', views.map, name='map'),
    path('weather/', views.weather, name='weather'),
    path('upgrade/', views.upgrade, name="upgrade"),
    path('login/', views.login, name="login"),
    path('pricing/', views.pricing, name="pricing"),
    path('field/<int:id>', views.pricing, name="pricing"),
    
]
