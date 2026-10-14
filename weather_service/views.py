from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.gis.geos import Point
from datetime import datetime, timedelta
from .models import WeatherForecast, WeatherAlert, WeatherStation
from .serializers import WeatherForecastSerializer, WeatherAlertSerializer, WeatherStationSerializer
from .services import WeatherService

class WeatherForecastViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WeatherForecastSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return WeatherForecast.objects.all().order_by('-forecast_date')
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current weather for a location"""
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        
        if not lat or not lon:
            return Response(
                {'error': 'lat and lon parameters are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            location = Point(float(lon), float(lat))
            weather_service = WeatherService()
            current_weather = weather_service.get_current_weather(location)
            
            return Response(current_weather)
        except ValueError:
            return Response(
                {'error': 'Invalid lat/lon values'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def forecast(self, request):
        """Get weather forecast for location and date range"""
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        days = int(request.query_params.get('days', 7))
        
        if not lat or not lon:
            return Response(
                {'error': 'lat and lon parameters are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            location = Point(float(lon), float(lat))
            weather_service = WeatherService()
            forecasts = weather_service.get_multi_day_forecast(location, days)
            
            return Response({'forecasts': forecasts})
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def agricultural_suitability(self, request):
        """Check weather suitability for agricultural activities"""
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        activity = request.query_params.get('activity', 'general')
        date_str = request.query_params.get('date')
        
        if not all([lat, lon]):
            return Response(
                {'error': 'lat, lon parameters are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            location = Point(float(lon), float(lat))
            
            if date_str:
                check_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            else:
                check_date = datetime.now().date()
            
            weather_service = WeatherService()
            suitability = weather_service.check_agricultural_suitability(
                location, check_date, activity
            )
            
            return Response(suitability)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class WeatherAlertViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = WeatherAlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return WeatherAlert.objects.filter(
            is_active=True,
            end_time__gte=datetime.now()
        ).order_by('-severity', 'start_time')
    
    @action(detail=False, methods=['get'])
    def for_location(self, request):
        """Get weather alerts for a specific location"""
        lat = request.query_params.get('lat')
        lon = request.query_params.get('lon')
        radius = float(request.query_params.get('radius', 50))  # km
        
        if not lat or not lon:
            return Response(
                {'error': 'lat and lon parameters are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            location = Point(float(lon), float(lat))
            
            alerts = WeatherAlert.objects.filter(
                is_active=True,
                end_time__gte=datetime.now(),
                location__distance_lte=(location, radius * 1000)  # Convert to meters
            ).order_by('-severity', 'start_time')
            
            serializer = self.get_serializer(alerts, many=True)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class WeatherStationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WeatherStation.objects.filter(is_active=True)
    serializer_class = WeatherStationSerializer
    permission_classes = [permissions.IsAuthenticated]
