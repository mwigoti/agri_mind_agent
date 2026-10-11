from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('auth/', views.auth, name='auth'),
    path('services/', views.services, name='services'),
    path('contact/', views.contact, name='contact'),
    path('research/', views.research, name='research'),
    path('signup/', views.signup, name='signup'),
    path('map/', views.map, name='map'),
    path('weather/', views.weather, name='weather'),
    path('upgrade/', views.upgrade, name="upgrade"),
    path('signin/', views.signin, name="signin"),
    path('pricing/', views.pricing, name="pricing")
]