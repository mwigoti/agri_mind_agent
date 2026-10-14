from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import WeatherForecastViewSet, WeatherAlertViewSet, WeatherStationViewSet

router = DefaultRouter()
router.register(r'forecasts', WeatherForecastViewSet, basename='forecast')
router.register(r'alerts', WeatherAlertViewSet, basename='alert')  
router.register(r'stations', WeatherStationViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
urlpatterns = [
    path('', include(router.urls)),
]