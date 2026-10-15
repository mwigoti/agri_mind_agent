from __future__ import annotations

# Standard Library
import json
import logging
import os
import threading
import traceback
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict

# Third-Party Libraries
import ee
import numpy as np
import requests
import stripe

# Django Core
from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.core.mail import send_mail, BadHeaderError
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Max, Min, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

# GIS
from django.contrib.gis.geos import GEOSGeometry, Polygon

# Django REST Framework
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

# Local Applications
from .agrivision_gee_analysis import *
from .analysis import IntegratedSoilAnalyzer
from .models import *

# IMPORTANT:
# Remove this import from here if possible and lazy-load it
# inside the report generation view.
# from .report_generator import AgrivisionReportGenerator

logger = logging.getLogger(__name__)

CustomUser = get_user_model()
# Create your views here.
def home(request):
    return render(request, 'index.html')

from .forms import MyUserCreationForm

def register(request):
    page = "register"
    
    if request.method == 'POST':
        form = MyUserCreationForm(request.POST)
        
        if form.is_valid():
            user = form.save(commit=False)
            user.email = user.email.lower()
            user.save()
            
            return redirect('map')
    else:
        form = MyUserCreationForm()
    
    return render(request, 'register.html', {"form": form, "page": page})

def login_view(request):
    page = 'login'
    if request.user.is_authenticated:
        return redirect('map')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        try:
            user = CustomUser.objects.get(email=email)
        except:
            messages.error(request, 'User does not exist')

        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('map')
        else:
            messages.error(request, 'Username OR password does not exit')

    context = {'page': page}
    return render(request, 'login.html', context)
@login_required(login_url="login")
def logout_user(request):
    logout(request)
    return redirect("home")

def services(request):
    return render(request, 'service.html')


def contact(request):
    if request.method == 'POST':
        # Retrieve form data from POST request
        name = request.POST.get('name')
        organization = request.POST.get('organization', 'N/A')  # Optional field
        email = request.POST.get('email')
        message = request.POST.get('message')

        if name and email and message:
            # Construct email content
            subject = f'New Contact Form Submission from {name}'
            message_body = f'''
            Name: {name}
            Organization: {organization}
            Email: {email}

            Message:
            {message}
            '''

            try:
                # Send email with a reply-to header instead of using user's email as from_email
                send_mail(
                    subject,
                    message_body,
                    settings.DEFAULT_FROM_EMAIL,  # Use a verified email address for from_email
                    [settings.DEFAULT_TO_EMAIL],  # Your default email address
                    fail_silently=False,
                    reply_to=[email]  # User's email set as reply-to
                )
                messages.success(request, 'Your message has been sent successfully.')
                return redirect('/')  # Redirect to the same page or a 'thank you' page
            except BadHeaderError:
                messages.error(request, 'Invalid header found.')
            except Exception as e:
                messages.error(request, f'An error occurred while sending your message: {e}')
        else:
            messages.error(request, 'Please fill in all required fields.')
    
    return render(request, 'contact.html')



def research(request):
    return render(request, 'research.html')

def signup(request):
    return render(request, 'signup.html')

@login_required(login_url="login")
def map(request):
    return render(request, 'map.html')

def weather(request):
    return render(request, 'weather.html')

def upgrade(request):
    amount = request.GET.get('amount', 0)
    return render(request, 'upgrade.html', {'amount': amount})


def pricing(request):
    return render(request, 'pricing.html')


class SaveFieldView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            name = data.get('name', 'Unnamed Field')
            coordinates = data.get('coordinates')
            area = data.get('area', 0.0)
            owner = request.user

            if not coordinates or len(coordinates) < 3:
                return Response({"error": "At least 3 points are required"}, status=status.HTTP_400_BAD_REQUEST)

            #  Convert from [lat, lng] → (lng, lat) for PostGIS
            coords_lnglat = [(lng, lat) for lat, lng in coordinates]

            #  Ensure polygon is closed
            if coords_lnglat[0] != coords_lnglat[-1]:
                coords_lnglat.append(coords_lnglat[0])

            # Create polygon with WGS84 SRID
            polygon = Polygon(coords_lnglat, srid=4326)

            field = Field.objects.create(
                owner=owner,
                name=name,
                geometry=polygon,
                area=area
            )

            serializer = FieldGeoJSONSerializer(field)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


           
# Retrieve fields as geojson from db

from rest_framework.decorators import api_view
from .models import Field
from .serializers import FieldGeoJSONSerializer

@api_view(['GET'])
def get_fields_geojson(request):
    fields = Field.objects.filter(owner=request.user)  # Query all fields
    serializer = FieldGeoJSONSerializer(fields, many=True)  # Serialize data
    return Response(serializer.data) 
    
@method_decorator(csrf_exempt, name='dispatch')
class DeleteFieldView(APIView):
    def delete(self, request, id):
        field = get_object_or_404(Field, id=id)
        field.delete()
        return Response({'message': 'Field deleted successfully'}, status=status.HTTP_200_OK)

from django.shortcuts import render

def analyze_field_view(request, id):
    """
    Enhanced field analysis view with proper data extraction
    """
    try:
        # Get the field object
        field = get_object_or_404(Field, id=id)
        area = field.area
        
        # Initialize the analyzer
        analyzer = IntegratedSoilAnalyzer()
        
        # Get the raw analysis result (this contains the AI response)
        # Note: climate_data is ignored when soil_data is an int (field ID)
        raw_result = analyzer.analyze_combined_data(soil_data=id)
        
        if not raw_result.get("success", False):
            error_msg = raw_result.get("error", "Analysis failed")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({"success": False, "error": error_msg})
            return render(request, 'analysis.html', {
                "result": json.dumps({"error": error_msg}), 
                "id": id, 
                "area": f"{area:.2f}"
            })
        
        # Extract the analysis text from the raw result
        analysis_text = raw_result.get("analysis", "")
        from base.analysis import DataExtractor
        
        extractor = DataExtractor()
        extracted_soil_data = extractor.extract_soil_data(analysis_text)
        extracted_climate_data = extractor.extract_climate_data(analysis_text)
        extracted_recommendations = extractor.extract_recommendations(analysis_text)
        
        # Get the original soil and climate data from the analyzer
        field_center = analyzer.get_field_center(id)
        original_soil_data = analyzer.get_isric_soil_data(field_center['lat'], field_center['lon'])
        raw_climate = analyzer.get_climate_data(field_center['lat'], field_center['lon'])
        original_climate_data = analyzer.format_weather_predictions(raw_climate) if raw_climate else {}
        
        # Merge original data with extracted data (extracted data takes precedence if available)
        merged_soil_data = {}
        
        # FIX: Check if original_soil_data is a dict (not DataFrame)
        if original_soil_data is not None and isinstance(original_soil_data, dict):
            merged_soil_data = original_soil_data.copy()
        
        # Override with extracted values where available
        for key, value in extracted_soil_data.items():
            if value is not None:
                merged_soil_data[key] = value
        
        # Merge climate data
        merged_climate_data = original_climate_data.copy()
        if extracted_climate_data:
            if 'summary' not in merged_climate_data:
                merged_climate_data['summary'] = {}
            merged_climate_data['summary'].update(extracted_climate_data)
        
        # Create the final result structure
        final_result = {
            "success": True,
            "analysis": analysis_text,
            "soil_properties": merged_soil_data,
            "climate_conditions": merged_climate_data,
            "recommendations": extracted_recommendations,
            "field_info": {
                "id": id,
                "name": field.name,
                "area": area,
                "center": field_center
            },
            "timestamp": raw_result.get("timestamp"),
            "model": raw_result.get("model"),
            "metadata": raw_result.get("metadata", {})
        }
        
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                "success": True, 
                "result": final_result
            })
        
        # For regular requests, render the template
        context = {
            "result": json.dumps(final_result),
            "id": id,
            "area": f"{area:.2f}",
            "field_name": field.name
        }
        
        return render(request, 'analysis.html', context)
        
    except Exception as e:
        error_msg = f"Error analyzing field: {str(e)}"
        print(f"DEBUG: {error_msg}")  # For debugging
        import traceback
        traceback.print_exc()  # Print full stack trace for debugging
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({"success": False, "error": error_msg}, status=500)
        
        return render(request, 'analysis.html', {
            "result": json.dumps({"success": False, "error": error_msg}),
            "id": id,
            "area": "0.00"
        })


def get_field_data_view(request, id):
    """
    API endpoint to get field data for AJAX requests
    """
    try:
        field = get_object_or_404(Field, id=id)
        analyzer = IntegratedSoilAnalyzer()
        
        # Get field center coordinates
        field_center = analyzer.get_field_center(id)
        
        # Get soil data from ISRIC (returns dict)
        soil_data = analyzer.get_isric_soil_data(field_center['lat'], field_center['lon'])
        
        # Get climate data from Open-Meteo
        raw_climate = analyzer.get_climate_data(field_center['lat'], field_center['lon'])
        climate_data = analyzer.format_weather_predictions(raw_climate) if raw_climate else {}
        
        response_data = {
            "success": True,
            "field_info": {
                "id": id,
                "name": field.name,
                "area": field.area,
                "center": field_center
            },
            #  FIX: soil_data is already a dict, no need to convert
            "soil_properties": soil_data if soil_data is not None else {},
            "climate_conditions": climate_data
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        import traceback
        traceback.print_exc()  # Print full stack trace for debugging
        return JsonResponse({
            "success": False,
            "error": str(e)
        }, status=500)

        
def load(request):
    return render(request, 'load.html')


def activity(request):
    return render(request, "activity.html")


def res(request):
    return render(request, 'result.html')


def health(request):
    return render(request, "health.html")











logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class VRAAnalysisView(APIView):
    """
    Enhanced VRA Analysis View with better error handling and logging
    """
    
    def post(self, request, field_id):
        try:
            logger.info(f"Starting VRA analysis for field {field_id}")
            
            # Get the field from database
            field = get_object_or_404(Field, id=field_id, owner=request.user)
            logger.info(f"Found field: {field.name} (Area: {field.area} ha)")
            
            # Prepare field data for Rust engine
            field_data = self.prepare_field_data(field)
            logger.info(f"Prepared field data: {json.dumps(field_data, indent=2)}")
            
            # Check if Rust engine is running first
            if not self.check_rust_engine_health():
                return Response({
                    "success": False,
                    "error": "VRA Analysis Engine is not running. Please start the Rust service.",
                    "troubleshooting": {
                        "service_url": "http://127.0.0.1:8001",
                        "startup_command": "cargo run --release",
                        "health_endpoint": "/health"
                    }
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
            
            # Send to Rust analysis engine
            rust_response = self.send_to_rust_engine(field_data)
            
            if rust_response.get('success'):
                # Store analysis results if needed
                self.store_analysis_results(field, rust_response.get('data'))
                
                return Response({
                    "success": True,
                    "message": "VRA analysis completed successfully",
                    "field_id": field_id,
                    "field_name": field.name,
                    "field_area": field.area,
                    "analysis_data": rust_response.get('data'),
                    "processing_info": {
                        "analysis_type": "Variable Rate Application",
                        "satellite_data_source": "Microsoft Planetary Computer",
                        "clustering_method": "K-means"
                    }
                }, status=status.HTTP_200_OK)
            else:
                error_msg = rust_response.get('error', 'Unknown analysis engine error')
                logger.error(f"Rust engine error for field {field_id}: {error_msg}")
                
                return Response({
                    "success": False,
                    "error": error_msg,
                    "field_id": field_id,
                    "field_name": field.name,
                    "troubleshooting": self.get_troubleshooting_info(error_msg)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Field.DoesNotExist:
            logger.error(f"Field {field_id} not found or access denied for user {request.user}")
            return Response({
                "success": False,
                "error": "Field not found or access denied"
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Unexpected VRA Analysis error for field {field_id}: {str(e)}", exc_info=True)
            return Response({
                "success": False,
                "error": f"Analysis failed: {str(e)}",
                "error_type": type(e).__name__
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def prepare_field_data(self, field):
        """
        Prepare field data in the format expected by Rust engine
        """
        try:
            # Convert Django geometry to GeoJSON
            geometry_geojson = json.loads(field.geometry.geojson)
            
            # Prepare VRAAnalysisRequest format (as per Rust code)
            request_data = {
                "field_id": field.id,
                "user_id": field.owner.id,
                "geometry": geometry_geojson,
                "num_zones": 5,  # Default to 5 zones
                "indices": ["NDVI", "EVI", "SAVI", "NDMI"]  # Request multiple indices
            }
            
            logger.info(f"Prepared VRA request data for field {field.id}")
            return request_data
            
        except Exception as e:
            logger.error(f"Error preparing field data: {str(e)}")
            raise Exception(f"Failed to prepare field data: {str(e)}")
    
    def check_rust_engine_health(self):
        """
        Check if the Rust VRA engine is running and healthy
        """
        try:
            response = requests.post(
                "http://127.0.0.1:8001/health",
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                health_data = response.json()
                logger.info(f"Rust engine health check passed: {health_data.get('status', 'unknown')}")
                return True
            else:
                logger.error(f"Rust engine health check failed: HTTP {response.status_code}")
                return False
                
        except requests.exceptions.ConnectionError:
            logger.error("Cannot connect to Rust VRA engine - service appears to be down")
            return False
        except Exception as e:
            logger.error(f"Health check error: {str(e)}")
            return False
    
    def send_to_rust_engine(self, field_data):
        """
        Send field data to Rust analysis engine with enhanced error handling
        """
        # Try the single field endpoint first
        endpoints = [
            ("http://127.0.0.1:8001/analyze-field-enhanced", field_data),
            ("http://127.0.0.1:8001/generate-vra-maps", [field_data])  # Fallback to batch endpoint
        ]
        
        for endpoint_url, payload in endpoints:
            try:
                logger.info(f"Sending request to {endpoint_url}")
                logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
                
                response = requests.post(
                    endpoint_url,
                    json=payload,
                    headers={
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    timeout=300  # 5 minutes timeout for satellite data processing
                )
                
                logger.info(f"Response status: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                
                # Log raw response for debugging
                raw_response = response.text
                logger.debug(f"Raw response (first 500 chars): {raw_response[:500]}...")
                
                if response.status_code == 200:
                    try:
                        response_data = response.json()
                        logger.info("Successfully received JSON response from Rust engine")
                        return {
                            "success": True,
                            "data": response_data
                        }
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON response: {str(e)}")
                        logger.error(f"Raw response: {raw_response}")
                        return {
                            "success": False,
                            "error": f"Invalid JSON response from analysis engine: {str(e)}"
                        }
                else:
                    logger.error(f"HTTP error {response.status_code}: {raw_response}")
                    return {
                        "success": False,
                        "error": f"Analysis engine returned HTTP {response.status_code}: {raw_response}"
                    }
                
            except requests.exceptions.Timeout:
                logger.error(f"Timeout for endpoint {endpoint_url}")
                error_msg = "Analysis engine timeout - satellite data processing took too long"
                if endpoint_url == endpoints[-1][0]:  # Last endpoint
                    return {"success": False, "error": error_msg}
                continue  # Try next endpoint
                
            except requests.exceptions.ConnectionError:
                logger.error(f"Connection error for endpoint {endpoint_url}")
                error_msg = "Cannot connect to analysis engine. Please ensure the Rust service is running on port 8001."
                if endpoint_url == endpoints[-1][0]:  # Last endpoint
                    return {"success": False, "error": error_msg}
                continue  # Try next endpoint
                
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for endpoint {endpoint_url}: {str(e)}")
                error_msg = f"Request error: {str(e)}"
                if endpoint_url == endpoints[-1][0]:  # Last endpoint
                    return {"success": False, "error": error_msg}
                continue  # Try next endpoint
                
            except Exception as e:
                logger.error(f"Unexpected error for endpoint {endpoint_url}: {str(e)}")
                error_msg = f"Unexpected error: {str(e)}"
                if endpoint_url == endpoints[-1][0]:  # Last endpoint
                    return {"success": False, "error": error_msg}
                continue  # Try next endpoint
        
        # If we reach here, all endpoints failed
        return {
            "success": False,
            "error": "All analysis engine endpoints failed"
        }
    
    def store_analysis_results(self, field, analysis_data):
        """
        Store analysis results in database if needed
        """
        try:
            logger.info(f"VRA analysis completed for field {field.id} - {field.name}")
            
            # Extract key metrics for logging
            if isinstance(analysis_data, dict):
                if 'field' in analysis_data:
                    field_data = analysis_data['field']
                    zones_count = len(field_data.get('vra_zones', []))
                    health_score = field_data.get('analysis_summary', {}).get('overall_health_score', 0)
                    logger.info(f"Analysis results: {zones_count} zones, {health_score:.1f}% health score")
                elif 'fields' in analysis_data:
                    fields_data = analysis_data['fields']
                    if fields_data:
                        zones_count = len(fields_data[0].get('vra_zones', []))
                        health_score = fields_data[0].get('analysis_summary', {}).get('overall_health_score', 0)
                        logger.info(f"Batch analysis results: {zones_count} zones, {health_score:.1f}% health score")
            
            # Optional: Save to database
            # You could create a VRAAnalysis model and save the results here
            
        except Exception as e:
            logger.error(f"Error storing analysis results: {str(e)}")
    
    def get_troubleshooting_info(self, error_msg):
        """
        Provide troubleshooting information based on the error
        """
        troubleshooting = {
            "common_solutions": [
                "Ensure the Rust VRA Analysis Engine is running on port 8001",
                "Check if the field geometry is valid",
                "Verify internet connection for satellite data access",
                "Restart the Rust service if it appears to be stuck"
            ],
            "service_commands": {
                "start_service": "cd /path/to/rust/project && cargo run --release",
                "check_health": "curl -X POST http://127.0.0.1:8001/health",
                "view_logs": "Check the Rust service console output"
            }
        }
        if "connection" in error_msg.lower():
            troubleshooting["specific_issue"] = "Service Connection"
            troubleshooting["likely_cause"] = "The Rust VRA Analysis Engine is not running"
            
        elif "timeout" in error_msg.lower():
            troubleshooting["specific_issue"] = "Processing Timeout"
            troubleshooting["likely_cause"] = "Large field or slow satellite data download"
            
        elif "json" in error_msg.lower():
            troubleshooting["specific_issue"] = "Response Format"
            troubleshooting["likely_cause"] = "Service returned invalid or empty response"
            
        return troubleshooting


# Enhanced status check function
def check_vra_engine_status(request):
    """
    Enhanced VRA engine status check with detailed diagnostics
    """
    try:
        logger.info("Checking VRA engine status...")
        
        response = requests.post(
            "http://127.0.0.1:8001/health", 
            timeout=10,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            try:
                health_data = response.json()
                logger.info(f"VRA engine is healthy: {health_data}")
                
                return JsonResponse({
                    "status": "online",
                    "service": health_data.get("service", "VRA Analysis Engine"),
                    "version": health_data.get("version", "Unknown"),
                    "message": "Service is running and ready",
                    "capabilities": health_data.get("capabilities", []),
                    "satellite_data_source": health_data.get("satellite_data_source", "Microsoft Planetary Computer"),
                    "last_checked": "2025-07-28T11:58:00Z"
                })
            except json.JSONDecodeError:
                logger.error("Health endpoint returned invalid JSON")
                return JsonResponse({
                    "status": "warning",
                    "message": "Service is running but returned invalid response format"
                })
        else:
            logger.error(f"Health check failed with status {response.status_code}")
            return JsonResponse({
                "status": "error",
                "message": f"Service returned status {response.status_code}",
                "response_text": response.text[:200]
            })
            
    except requests.exceptions.ConnectionError:
        logger.error("Cannot connect to VRA engine - service appears to be down")
        return JsonResponse({
            "status": "offline",
            "message": "VRA Analysis Engine is not running",
            "troubleshooting": {
                "check_service": "Ensure Rust service is running on port 8001",
                "start_command": "cargo run --release",
                "port": 8001
            }
        })
    except requests.exceptions.Timeout:
        logger.error("VRA engine health check timed out")
        return JsonResponse({
            "status": "timeout",
            "message": "Service health check timed out"
        })
    except Exception as e:
        logger.error(f"Unexpected error checking VRA engine status: {str(e)}")
        return JsonResponse({
            "status": "error",
            "message": f"Error checking service: {str(e)}"
        })
        
        
@login_required(login_url="login")
def vra_page(request, field_id=None):
    """
    VRA Analysis page that properly handles field ID
    """
    try:
        if field_id:
            # Get the specific field
            field = get_object_or_404(Field, id=field_id, owner=request.user)
            context = {
                'field_id': field.id,
                'field_name': field.name,
                'field_area': field.area,
            }
        else:
            # No field ID provided - show field selection or redirect
            user_fields = Field.objects.filter(owner=request.user)
            if user_fields.count() == 1:
                # If user has only one field, use that
                field = user_fields.first()
                return redirect('vra-page', field_id=field.id)
            elif user_fields.count() > 1:
               
                context = {
                    'fields': user_fields,
                    'show_field_selector': True
                }
            else:
                # No fields - redirect to map
                messages.error(request, 'Please create a field first before running VRA analysis')
                return redirect('map')
        
        return render(request, 'vra_analysis.html', context)
        
    except Field.DoesNotExist:
        messages.error(request, 'Field not found or access denied')
        return redirect('map')
    except Exception as e:
        logger.error(f"Error in vra_page: {str(e)}")
        messages.error(request, 'An error occurred loading the VRA analysis page')
        return redirect('map')
    
from django.http import HttpResponse

from django.views.decorators.http import require_POST

from django.views import View
from django.utils.timezone import now



import re
from .models import USSDSession

@method_decorator(csrf_exempt, name='dispatch')
class USSDView(View):
    
    def post(self, request):
        try:
            session_id = request.POST.get('sessionId', '')
            phone_number = request.POST.get('phoneNumber', '')
            text = request.POST.get('text', '')
            
            logger.info(f"USSD Request - Session: {session_id}, Phone: {phone_number}, Text: '{text}'")
            
            if not session_id or not phone_number:
                return HttpResponse("END Invalid request", content_type='text/plain')
            
            phone_number = self.clean_phone_number(phone_number)
            
            session, created = USSDSession.objects.get_or_create(
                session_id=session_id,
                defaults={
                    'phone_number': phone_number,
                    'current_step': 'start',
                    'data': {}
                }
            )
            
            response_text = self.process_menu(session, text)
            return HttpResponse(response_text, content_type='text/plain')
            
        except Exception as e:
            logger.error(f"USSD Error: {str(e)}")
            return HttpResponse("END Service unavailable", content_type='text/plain')
    
    def clean_phone_number(self, phone_number):
        cleaned = phone_number.strip()
        if cleaned.startswith('0'):
            cleaned = '+254' + cleaned[1:]
        elif not cleaned.startswith('+254'):
            cleaned = '+254' + cleaned.lstrip('+')
        return cleaned
    
    def process_menu(self, session, user_input):
        current_input = user_input.split('*')[-1] if user_input else ''
        
        if session.current_step == 'start':
            return self.start_menu(session)
        elif session.current_step == 'main_menu':
            return self.handle_main_menu(session, current_input)
        elif session.current_step == 'register_first_name':
            return self.handle_first_name(session, current_input)
        elif session.current_step == 'register_last_name':
            return self.handle_last_name(session, current_input)
        elif session.current_step == 'confirm_registration':
            return self.handle_confirmation(session, current_input)
        else:
            session.current_step = 'start'
            session.save()
            return self.start_menu(session)
    
    def start_menu(self, session):
        existing_user = CustomUser.objects.filter(phone_number=session.phone_number).first()
        
        if existing_user:
            field_count = existing_user.field_set.count()
            return (f"END Welcome back, {existing_user.first_name}! 🌱\n"
                   f"Phone: {existing_user.phone_number}\n"
                   f"Fields: {field_count}\n"
                   f"Email: {existing_user.email}")
        
        session.current_step = 'main_menu'
        session.save()
        
        return ("CON Welcome to Agrivision! 🌱\n"
                "Your Smart Farming Partner\n\n"
                "1. Register New Account\n"
                "2. About Agrivision\n"
                "0. Exit")
    
    def handle_main_menu(self, session, choice):
        if choice == '1':
            session.current_step = 'register_first_name'
            session.save()
            return "CON Enter your FIRST NAME:\n\n0. Back"
        elif choice == '2':
            return ("END About Agrivision 🌱\n\n"
                   "Smart farming platform for field management,\n"
                   "crop advisory, and agricultural resources.\n\n"
                   "Join thousands of farmers!")
        elif choice == '0':
            session.delete()
            return "END Thank you! 🌾"
        else:
            return ("CON Invalid choice:\n\n"
                   "1. Register New Account\n"
                   "2. About Agrivision\n"
                   "0. Exit")
    
    def handle_first_name(self, session, first_name):
        if first_name == '0':
            session.current_step = 'main_menu'
            session.save()
            return self.start_menu(session)
        
        if not first_name or len(first_name.strip()) < 2:
            return "CON Invalid name! Enter at least 2 characters:\n\n0. Back"
        
        session.data['first_name'] = first_name.strip().title()
        session.current_step = 'register_last_name'
        session.save()
        
        return f"CON First Name: {session.data['first_name']} ✓\n\nEnter your LAST NAME:\n\n0. Back"
    
    def handle_last_name(self, session, last_name):
        if last_name == '0':
            session.current_step = 'main_menu'
            session.save()
            return self.start_menu(session)
        
        if not last_name or len(last_name.strip()) < 2:
            return "CON Invalid name! Enter at least 2 characters:\n\n0. Back"
        
        session.data['last_name'] = last_name.strip().title()
        session.current_step = 'confirm_registration'
        session.save()
        
        return (f"CON CONFIRM DETAILS:\n\n"
               f"📱 Phone: {session.phone_number}\n"
               f"👤 Name: {session.data['first_name']} {session.data['last_name']}\n\n"
               f"1. ✅ CONFIRM\n"
               f"0. ❌ Cancel")
    
    def handle_confirmation(self, session, choice):
        if choice == '1':
            try:
                # Generate unique email and username
                phone_clean = re.sub(r'[^\d]', '', session.phone_number)
                email = f"{session.data['first_name'].lower()}.{session.data['last_name'].lower()}.{phone_clean[-6:]}@agrivision.ussd"
                username = f"{session.data['first_name'].lower()}{session.data['last_name'].lower()}{phone_clean[-4:]}"
                
                # Ensure uniqueness
                counter = 1
                base_email, base_username = email, username
                while CustomUser.objects.filter(email=email).exists():
                    email = f"{base_email.split('@')[0]}.{counter}@agrivision.ussd"
                    counter += 1
                
                counter = 1
                while CustomUser.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                # Create user
                user = CustomUser.objects.create_user(
                    email=email,
                    username=username,
                    first_name=session.data['first_name'],
                    last_name=session.data['last_name'],
                    phone_number=session.phone_number,
                    registered_via_ussd=True,
                    ussd_registration_date=now(),
                    password=None
                )
                
                session.delete()
                
                return (f"END 🎉 SUCCESS! 🎉\n\n"
                       f"Welcome {user.first_name}!\n\n"
                       f"📱 Phone: {user.phone_number}\n"
                       f"📧 Email: {user.email}\n\n"
                       f"🌾 Happy farming!")
                
            except Exception as e:
                logger.error(f"Registration error: {str(e)}")
                return "END Registration failed. Try again later."
        
        elif choice == '0':
            session.delete()
            return "END Registration cancelled."
        else:
            return (f"CON Invalid choice:\n\n"
                   f"📱 Phone: {session.phone_number}\n"
                   f"👤 Name: {session.data['first_name']} {session.data['last_name']}\n\n"
                   f"1. ✅ CONFIRM\n"
                   f"0. ❌ Cancel")
WEATHER_API_KEY = settings.WEATHER_API_KEY 
WEATHER_API_BASE_URL = "http://api.openweathermap.org/data/2.5"
# views.py
from django.shortcuts import render, get_object_or_404







from django.core.cache import cache
from django.db.models import Q


from .models import Field, FieldActivity, WeatherData, SmartRecommendation, Crop
from .weather_service import WeatherService  # We'll create this
from .recommendation_engine import RecommendationEngine  # We'll create this

@login_required
def activity_dashboard(request):
    """Render the main activity dashboard"""
    return render(request, 'activity.html')

@login_required
@require_http_methods(["GET"])
def get_user_fields(request):
    """Get user's fields with caching for fast dropdown loading"""
    cache_key = f"user_fields_{request.user.id}"
    fields_data = cache.get(cache_key)
    
    if not fields_data:
        fields = Field.objects.filter(owner=request.user).values(
            'id', 'name', 'area', 'created_at'
        )
        fields_data = list(fields)
        # Cache for 30 minutes
        cache.set(cache_key, fields_data, 60 * 30)
    
    return JsonResponse({
        'status': 'success',
        'fields': fields_data
    })

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def create_activity(request):
    """Create new field activity with email notifications"""
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['field_id', 'activity_type', 'date', 'crop_name']
        for field in required_fields:
            if not data.get(field):
                return JsonResponse({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }, status=400)
        
        # Get or create crop
        crop = None
        if data.get('crop_name'):
            crop, created = Crop.objects.get_or_create(
                name=data['crop_name'].title(),
                defaults={
                    'min_temp': 10,
                    'max_temp': 35,
                    'optimal_temp_min': 18,
                    'optimal_temp_max': 28,
                    'water_requirement': 'medium',
                    'growing_season_days': 90
                }
            )
        
        # Get field
        field = get_object_or_404(Field, id=data['field_id'], owner=request.user)
        
        # Create activity
        activity = FieldActivity.objects.create(
            field=field,
            activity_type=data['activity_type'],
            crop=crop,
            date=datetime.fromisoformat(data['date'].replace('Z', '+00:00')),
            duration_hours=data.get('duration', 0),
            description=data.get('description', ''),
            cost=data.get('cost', 0),
            priority=data.get('priority', 'medium'),
            notes=data.get('notes', '')
        )
        
        # Clear cache for user activities
        cache.delete(f"user_activities_{request.user.id}")
        
        # Send email notification
        send_activity_email(request.user, activity, 'created')
        
        # Schedule reminder if activity is in future
        if activity.date > timezone.now():
            schedule_activity_reminder(request.user, activity)
        
        return JsonResponse({
            'status': 'success',
            'message': 'Activity created successfully',
            'activity_id': activity.id
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def get_user_activities(request):
    """Get user's activities with caching"""
    cache_key = f"user_activities_{request.user.id}"
    activities_data = cache.get(cache_key)
    
    if not activities_data:
        activities = FieldActivity.objects.filter(
            field__owner=request.user
        ).select_related('field', 'crop').order_by('-date')[:50]
        
        activities_data = []
        for activity in activities:
            activities_data.append({
                'id': activity.id,
                'title': f"{activity.get_activity_type_display()} - {activity.crop.name if activity.crop else 'General'}",
                'date': activity.date.isoformat(),
                'type': activity.activity_type,
                'field': activity.field.name,
                'crop': activity.crop.name if activity.crop else '',
                'duration': float(activity.duration_hours),
                'cost': float(activity.cost),
                'priority': activity.priority,
                'status': activity.completion_status,
                'description': activity.description
            })
        
        # Cache for 15 minutes
        cache.set(cache_key, activities_data, 60 * 15)
    
    return JsonResponse({
        'status': 'success',
        'activities': activities_data
    })

@login_required
@require_http_methods(["GET"])
def get_weather_data(request, field_id):
    """Get current and forecast weather data for a field"""
    field = get_object_or_404(Field, id=field_id, owner=request.user)
    
    # Try to get from cache first
    cache_key = f"weather_field_{field_id}"
    weather_data = cache.get(cache_key)
    
    if not weather_data:
        # Get from database or external API
        weather_service = WeatherService()
        weather_data = weather_service.get_field_weather(field)
        
        # Cache for 10 minutes (weather changes frequently)
        cache.set(cache_key, weather_data, 60 * 10)
    
    return JsonResponse({
        'status': 'success',
        'weather': weather_data
    })

@login_required
@require_http_methods(["GET"])
def get_smart_recommendations(request):
    """Get dynamic AI recommendations based on current conditions"""
    user_fields = Field.objects.filter(owner=request.user)
    
    # Generate recommendations for all user fields
    recommendation_engine = RecommendationEngine()
    all_recommendations = []
    
    for field in user_fields:
        # Get fresh recommendations (not cached as they should be real-time)
        recommendations = recommendation_engine.generate_recommendations(field)
        all_recommendations.extend(recommendations)
    
    # Sort by urgency and confidence
    urgency_order = {'critical': 5, 'high': 4, 'medium': 3, 'low': 2, 'info': 1}
    all_recommendations.sort(
        key=lambda x: (urgency_order.get(x['urgency'], 0), x['confidence']),
        reverse=True
    )
    
    return JsonResponse({
        'status': 'success',
        'recommendations': all_recommendations[:10]  # Return top 10
    })

@login_required
@require_http_methods(["POST"])
def mark_recommendation_read(request, recommendation_id):
    """Mark a recommendation as read"""
    try:
        recommendation = get_object_or_404(
            SmartRecommendation, 
            id=recommendation_id,
            field__owner=request.user
        )
        recommendation.is_read = True
        recommendation.save()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Recommendation marked as read'
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@require_http_methods(["GET"])
def get_activity_optimization(request, field_id):
    """Get optimized timing for activities"""
    field = get_object_or_404(Field, id=field_id, owner=request.user)
    
    cache_key = f"activity_optimization_{field_id}"
    optimization_data = cache.get(cache_key)
    
    if not optimization_data:
        recommendation_engine = RecommendationEngine()
        optimization_data = recommendation_engine.get_activity_timing_optimization(field)
        
        # Cache for 1 hour
        cache.set(cache_key, optimization_data, 60 * 60)
    
    return JsonResponse({
        'status': 'success',
        'optimization': optimization_data
    })

def send_activity_email(user, activity, action_type):
    """Send email notification for activity"""
    subject_map = {
        'created': f'New Activity Scheduled: {activity.get_activity_type_display()}',
        'reminder': f'Activity Reminder: {activity.get_activity_type_display()}',
        'completed': f'Activity Completed: {activity.get_activity_type_display()}'
    }
    
    subject = subject_map.get(action_type, 'Activity Update')
    
    message = f"""
    Dear {user.first_name or user.username},
    
    Activity Details:
    - Type: {activity.get_activity_type_display()}
    - Field: {activity.field.name}
    - Date: {activity.date.strftime('%Y-%m-%d %H:%M')}
    - Duration: {activity.duration_hours} hours
    - Priority: {activity.get_priority_display()}
    
    {activity.description if activity.description else ''}
    
    Best regards,
    Agrivision Team
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    except Exception as e:
        print(f"Failed to send email: {e}")

def schedule_activity_reminder(user, activity):
    """Schedule reminder email for activity"""

    from datetime import timedelta
    
    # Schedule reminder 24 hours before activity
    reminder_time = activity.date - timedelta(hours=24)
    
    if reminder_time > timezone.now():
        # You can use Celery or Django-Q for scheduling
        # For now, we'll store it in database and check periodically
        pass
@login_required
@require_http_methods(["GET"])
def get_active_crops(request):
    """Get all active crops for user's fields"""
    try:
        # Get user's fields
        user_fields = Field.objects.filter(owner=request.user)
        
        # Get the most recent planting activity for each field
        active_crops = []
        
        for field in user_fields:
            # Get the most recent planting activity that has a crop
            latest_planting = FieldActivity.objects.filter(
                field=field,
                activity_type='planting',
                crop__isnull=False
            ).select_related('crop').order_by('-date').first()
            
            if latest_planting:
                # Extract variety and irrigation from notes or weather_conditions
                variety = ''
                irrigation_type = ''
                
                # Try to get from weather_conditions JSON field
                if latest_planting.weather_conditions:
                    variety = latest_planting.weather_conditions.get('variety', '')
                    irrigation_type = latest_planting.weather_conditions.get('irrigation_type', '')
                
                # If not in weather_conditions, try parsing from notes
                if not variety and latest_planting.notes:
                    if 'Variety:' in latest_planting.notes:
                        variety = latest_planting.notes.split('Variety:')[1].split('|')[0].strip()
                
                if not irrigation_type and latest_planting.notes:
                    if 'Irrigation:' in latest_planting.notes:
                        irrigation_type = latest_planting.notes.split('Irrigation:')[1].split('|')[0].strip()
                
                active_crops.append({
                    'field_id': field.id,
                    'field_name': field.name,
                    'crop_id': latest_planting.crop.id,
                    'crop_name': latest_planting.crop.name,
                    'planting_date': latest_planting.date.isoformat(),
                    'activity_id': latest_planting.id,
                    'variety': variety,
                    'irrigation_type': irrigation_type,
                    'notes': latest_planting.notes
                })
        
        return JsonResponse({
            'status': 'success',
            'crops': active_crops
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
@login_required
@csrf_exempt
@require_http_methods(["POST"])
def register_crop_monitoring(request):
    """Register a new crop for monitoring on a field"""
    try:
        data = json.loads(request.body)
        
        # Required fields validation
        required = ['field_id', 'crop_name', 'planting_date']
        for field in required:
            if field not in data:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Missing required field: {field}'
                }, status=400)
        
        # Get field and verify ownership
        field = get_object_or_404(Field, id=data['field_id'], owner=request.user)
        
        # Get or create the Crop
        crop, created = Crop.objects.get_or_create(
            name=data['crop_name'].title(),
            defaults={
                'min_temp': 10,
                'max_temp': 35,
                'optimal_temp_min': 18,
                'optimal_temp_max': 28,
                'water_requirement': 'medium',
                'growing_season_days': 90,
                'planting_months': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                'harvest_months': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
                'drought_tolerance': 'medium'
            }
        )
        
        # Create planting activity
        planting_date = datetime.fromisoformat(data['planting_date'].replace('Z', '+00:00'))
        activity = FieldActivity.objects.create(
            field=field,
            activity_type='planting',
            crop=crop,
            date=planting_date,
            description=f"Planted {crop.name}",
            notes=data.get('notes', ''),
            completion_status='completed'
        )
        
        # Create initial growth stage
        CropGrowthStage.objects.create(
            field=field,
            crop=crop,
            stage='seedling',
            start_date=planting_date.date(),
            expected_end_date=(planting_date + timedelta(days=14)).date(),
            stage_health='good'
        )
        
        return JsonResponse({
            'status': 'success',
            'message': 'Crop monitoring started successfully',
            'activity_id': activity.id,
            'crop_id': crop.id,
            'crop_created': created
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
        
          
def seasons(request):
    return render(request, 'seasons.html')





@csrf_exempt
@require_http_methods(["POST"])
def analyze_field(request):
    """
    Main endpoint for field analysis
    
    Request Body:
    {
        "field_coordinates": [[[lon, lat], [lon, lat], ...]],
        "field_name": "Field A",
        "crop_type": "wheat",
        "growth_stage": "flowering",
        "soil_data": {
            "ph": 6.5,
            "moisture": 0.25,
            "field_capacity": 0.35,
            "nitrogen": 45,
            "phosphorus": 25,
            "potassium": 180,
            "organic_matter": 2.8
        },
        "weather_data": {
            "temperature": 24,
            "rainfall_7day": 15,
            "humidity": 65
        },
        "start_date": "2024-01-01",
        "end_date": "2024-01-31"
    }
    
    Returns:
        JSON response with complete analysis
    """
    try:
        # Parse request data
        data = json.loads(request.body)
        
        # Validate required fields
        required_fields = ['field_coordinates', 'field_name', 'crop_type', 
                          'growth_stage', 'soil_data', 'weather_data']
        for field in required_fields:
            if field not in data:
                return JsonResponse({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }, status=400)
        
        # Run analysis
        results = analyze_field(
            field_coordinates=data['field_coordinates'],
            field_name=data['field_name'],
            crop_type=data['crop_type'],
            growth_stage=data['growth_stage'],
            soil_data=data['soil_data'],
            weather_data=data['weather_data'],
            start_date=data.get('start_date'),
            end_date=data.get('end_date')
        )
        
        return JsonResponse({
            'success': True,
            'data': results
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def generate_report(request):
    """
    Generate downloadable PDF report
    
    Request Body:
    {
        "analysis_data": { ... },  # Results from analyze_field
        "report_format": "pdf",     # pdf, docx, or json
        "include_maps": true,
        "include_charts": true
    }
    
    Returns:
        PDF/DOCX file download or JSON response
    """
    from .report_generator import AgrivisionReportGenerator
    try:
        data = json.loads(request.body)
        
        if 'analysis_data' not in data:
            return JsonResponse({
                'success': False,
                'error': 'Missing analysis_data'
            }, status=400)
        
        analysis_data = data['analysis_data']
        report_format = data.get('report_format', 'pdf')
        include_maps = data.get('include_maps', True)
        include_charts = data.get('include_charts', True)
        
        # Generate report
        report_generator = AgrivisionReportGenerator()
        
        if report_format == 'pdf':
            pdf_buffer = report_generator.generate_pdf_report(
                analysis_data,
                include_maps=include_maps,
                include_charts=include_charts
            )
            
            response = HttpResponse(pdf_buffer, content_type='application/pdf')
            filename = f"agrivision_report_{analysis_data['field_information']['name']}_{datetime.now().strftime('%Y%m%d')}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        elif report_format == 'docx':
            docx_buffer = report_generator.generate_docx_report(
                analysis_data,
                include_maps=include_maps,
                include_charts=include_charts
            )
            
            response = HttpResponse(
                docx_buffer,
                content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
            filename = f"agrivision_report_{analysis_data['field_information']['name']}_{datetime.now().strftime('%Y%m%d')}.docx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        elif report_format == 'json':
            response = JsonResponse({
                'success': True,
                'data': analysis_data
            })
            filename = f"agrivision_report_{analysis_data['field_information']['name']}_{datetime.now().strftime('%Y%m%d')}.json"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
            
        else:
            return JsonResponse({
                'success': False,
                'error': f'Unsupported format: {report_format}'
            }, status=400)
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_vegetation_indices(request):
    """
    Get vegetation indices only for quick analysis
    
    Request Body:
    {
        "field_coordinates": [[[lon, lat], ...]],
        "date": "2024-01-15"
    }
    
    Returns:
        JSON with vegetation indices
    """
    try:
        data = json.loads(request.body)
        
        analyzer = AgrivisionCompleteAnalyzer()
        aoi = analyzer.define_aoi(data['field_coordinates'])
        
        target_date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        start_date = target_date
        end_date = target_date
        
        # Get Sentinel-2 data
        s2_collection = analyzer.get_sentinel2_data(aoi, start_date, end_date)
        s2_image = s2_collection.first()
        
        if not s2_image:
            return JsonResponse({
                'success': False,
                'error': 'No satellite imagery available for this date'
            }, status=404)
        
        # Calculate indices
        s2_with_indices = analyzer.calculate_vegetation_indices(s2_image)
        
        # Extract values
        indices = s2_with_indices.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=aoi,
            scale=10,
            maxPixels=1e9
        ).getInfo()
        
        return JsonResponse({
            'success': True,
            'data': {
                'date': target_date,
                'indices': indices
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_yield_prediction(request):
    """
    Get yield prediction only
    
    Request Body:
    {
        "indices": { ... },
        "soil_data": { ... },
        "weather_data": { ... },
        "crop_type": "wheat",
        "growth_stage": "flowering"
    }
    
    Returns:
        JSON with yield prediction
    """
    try:
        data = json.loads(request.body)
        
        analyzer = AgrivisionCompleteAnalyzer()
        
        yield_prediction = analyzer.predict_yield(
            indices=data['indices'],
            soil_data=data['soil_data'],
            weather_data=data['weather_data'],
            crop_type=data['crop_type'],
            growth_stage=data['growth_stage']
        )
        
        return JsonResponse({
            'success': True,
            'data': yield_prediction
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def get_health_score(request):
    """
    Get crop health score only
    
    Request Body:
    {
        "indices": { ... },
        "soil_data": { ... },
        "weather_data": { ... }
    }
    
    Returns:
        JSON with health score and recommendations
    """
    try:
        data = json.loads(request.body)
        
        analyzer = AgrivisionCompleteAnalyzer()
        
        health_score = analyzer.calculate_crop_health_score(
            indices=data['indices'],
            soil_data=data['soil_data'],
            weather_data=data['weather_data']
        )
        
        return JsonResponse({
            'success': True,
            'data': health_score
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def analyze_temporal_trends(request):
    """
    Analyze temporal trends in vegetation indices
    
    Request Body:
    {
        "field_coordinates": [[[lon, lat], ...]],
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "index": "NDVI"
    }
    
    Returns:
        JSON with time series data and trend analysis
    """
    try:
        data = json.loads(request.body)
        
        analyzer = AgrivisionCompleteAnalyzer()
        aoi = analyzer.define_aoi(data['field_coordinates'])
        
        # Get image collection
        s2_collection = analyzer.get_sentinel2_data(
            aoi,
            data['start_date'],
            data['end_date']
        )
        
        # Calculate indices for all images
        def add_indices(image):
            return analyzer.calculate_vegetation_indices(image)
        
        s2_with_indices = s2_collection.map(add_indices)
        
        # Analyze trend
        index = data.get('index', 'NDVI')
        trends = analyzer.analyze_temporal_trend(s2_with_indices, aoi, index)
        
        return JsonResponse({
            'success': True,
            'data': trends
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def create_management_zones(request):
    """
    Create field management zones
    
    Request Body:
    {
        "field_coordinates": [[[lon, lat], ...]],
        "date": "2024-01-15",
        "num_zones": 5
    }
    
    Returns:
        JSON with zone information and statistics
    """
    try:
        data = json.loads(request.body)
        
        analyzer = AgrivisionCompleteAnalyzer()
        aoi = analyzer.define_aoi(data['field_coordinates'])
        
        target_date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # Get image
        s2_collection = analyzer.get_sentinel2_data(aoi, target_date, target_date)
        s2_image = s2_collection.first()
        
        # Calculate indices
        s2_with_indices = analyzer.calculate_vegetation_indices(s2_image)
        
        # Create zones
        num_zones = data.get('num_zones', 5)
        zones = analyzer.generate_field_zones(aoi, s2_with_indices, num_zones)
        
        return JsonResponse({
            'success': True,
            'data': zones
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


# Health check endpoint
@require_http_methods(["GET"])
def health_check(request):
    """
    Check if GEE is properly initialized
    """
    try:
        analyzer = AgrivisionCompleteAnalyzer()
        # Simple test
        test_point = ee.Geometry.Point([0, 0])
        test_point.getInfo()
        
        return JsonResponse({
            'success': True,
            'message': 'Agrivision API is operational',
            'gee_status': 'connected'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'gee_status': 'disconnected'
        }, status=500)


"""
agrivision/views_analysis.py

View for POST /api/analyze-crop/
==================================
Triggered from the "Analyze Crop" button in health.html.
Runs Pipeline 2 (GEE data collection) asynchronously via Celery
and immediately returns a job-id so the frontend can poll for status.

URL conf addition (urls.py):
    path("api/analyze-crop/",     views_analysis.analyze_crop,      name="analyze_crop"),
    path("api/analysis-status/<int:result_id>/",
                                  views_analysis.analysis_status,   name="analysis_status"),

Celery task is in tasks.py (see bottom of this file).
"""

import json
import logging

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf   import csrf_exempt   # remove if using session auth properly

from .models import Field, FieldActivity, AnalysisResult

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
#  POST /api/analyze-crop/
# ─────────────────────────────────────────────────────────────
@login_required
@require_POST
def analyze_crop(request):
    """
    Kicks off Pipeline 2 for a given field + activity.

    Expected JSON body:
        {
          "field_id":    <int>,
          "activity_id": <int>      # FieldActivity pk (the planting record)
        }

    Returns immediately with:
        {
          "status":    "queued",
          "result_id": <int>,       # AnalysisResult pk — poll this
          "message":   "Analysis started — check /api/analysis-status/<result_id>/"
        }
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"}, status=400)

    field_id    = body.get("field_id")
    activity_id = body.get("activity_id")

    if not field_id or not activity_id:
        return JsonResponse(
            {"status": "error", "message": "field_id and activity_id are required"},
            status=400,
        )

    # ── Validate ownership ──────────────────────────────────
    try:
        field = Field.objects.get(pk=field_id, owner=request.user)
    except Field.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Field not found"}, status=404)

    try:
        activity = FieldActivity.objects.get(pk=activity_id, field=field)
    except FieldActivity.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Activity not found"}, status=404)

    # ── Create or reset AnalysisResult row ──────────────────
    result, created = AnalysisResult.objects.update_or_create(
        field_id=field_id,
        activity_id=activity_id,
        defaults={"pipeline_status": "queued", "full_bundle": {}},
    )

    # ── Dispatch Celery task ─────────────────────────────────
    # If Celery is not yet configured, fall back to synchronous execution
    # (comment out the try/except once Celery is running in production)
    try:
        from .tasks import run_pipeline_2_task
        run_pipeline_2_task.delay(field_id, activity_id, result.pk)
    except Exception as exc:
        logger.warning("Celery not available — running synchronously: %s", exc)
        _run_synchronous(field_id, activity_id, result.pk)

    return JsonResponse({
        "status":    "queued",
        "result_id": result.pk,
        "message":   "Analysis started — poll /api/analysis-status/{}/".format(result.pk),
    })


# ─────────────────────────────────────────────────────────────
#  GET /api/analysis-status/<result_id>/
# ─────────────────────────────────────────────────────────────
@login_required
@require_GET
def analysis_status(request, result_id: int):
    """
    Poll this endpoint after calling /api/analyze-crop/.

    Returns:
        {
          "status":        "queued" | "running" | "done" | "error",
          "result_id":     <int>,

          // When status == "done":
          "ndvi_latest":       <float>,
          "ndre_latest":       <float>,
          "evi_latest":        <float>,
          "ndvi_auc":          <float>,
          "ndre_peak":         <float>,
          "scene_count":       <int>,
          "latest_scene_date": <"YYYY-MM-DD">,
          "total_rainfall_mm": <float>,
          "cumulative_gdd":    <float>,
          "heat_stress_frac":  <float>,
          "soc_gkg":           <float>,
          "soil_ph":           <float>,
          "stress_flags":      ["flag 1", "flag 2", ...],
          "scenes":            [{date, ndvi, ndre, evi, savi, gndvi}, ...],
          "chirps_windows":    [{window_start, mm}, ...],
        }
    """
    try:
        result = AnalysisResult.objects.select_related("field").get(
            pk=result_id,
            field__owner=request.user,
        )
    except AnalysisResult.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Result not found"}, status=404)

    if result.pipeline_status in ("queued", "running"):
        return JsonResponse({
            "status":    result.pipeline_status,
            "result_id": result.pk,
        })

    if result.pipeline_status == "error":
        return JsonResponse({
            "status":    "error",
            "result_id": result.pk,
            "message":   result.error_message or "Pipeline failed",
        })

    # ── Done — return structured response ────────────────────
    bundle   = result.full_bundle or {}
    sentinel = bundle.get("sentinel", {})
    chirps   = bundle.get("chirps", {})
    era5     = bundle.get("era5", {})
    soil     = bundle.get("soil", {})

    return JsonResponse({
        "status":            "done",
        "result_id":         result.pk,

        # Vegetation indices
        "ndvi_latest":       result.ndvi_latest,
        "ndre_latest":       result.ndre_latest,
        "evi_latest":        sentinel.get("evi_latest"),
        "savi_latest":       sentinel.get("savi_latest"),
        "gndvi_latest":      sentinel.get("gndvi_latest"),
        "ndvi_auc":          result.ndvi_auc,
        "ndre_peak":         result.ndre_peak,
        "scene_count":       result.scene_count,
        "latest_scene_date": result.latest_scene_date,

        # All individual scenes for NDVI trend chart
        "scenes":            sentinel.get("scenes", []),

        # Climate
        "total_rainfall_mm": result.total_rainfall_mm,
        "chirps_windows":    chirps.get("windows", []),
        "cumulative_gdd":    result.cumulative_gdd,
        "heat_stress_frac":  result.heat_stress_frac,
        "recent_tmax_c":     era5.get("recent_tmax_c"),
        "recent_tmin_c":     era5.get("recent_tmin_c"),

        # Soil
        "soc_gkg":           result.soc_gkg,
        "soil_ph":           result.soil_ph,
        "bulk_density":      soil.get("bulk_density"),
        "clay_pct":          soil.get("clay_pct"),
        "total_nitrogen":    soil.get("total_nitrogen"),

        # Advisory
        "stress_flags":      result.stress_flags or [],

        # Pipeline 3/4 hooks
        "ready_for_ml":      bundle.get("ready_for_ml", False),
    })


# ─────────────────────────────────────────────────────────────
#  SYNC FALLBACK (development / no Celery)
# ─────────────────────────────────────────────────────────────
def _run_synchronous(field_id: int, activity_id: int, result_id: int):
    """Run the pipeline in-process (blocking). For dev only."""
    from .gee_pipeline import run_pipeline_2
    from .models import AnalysisResult

    result = AnalysisResult.objects.get(pk=result_id)
    result.pipeline_status = "running"
    result.save(update_fields=["pipeline_status"])

    try:
        run_pipeline_2(field_id, activity_id)
        result.refresh_from_db()
        result.pipeline_status = "done"
        result.save(update_fields=["pipeline_status"])
    except Exception as exc:
        logger.exception("Synchronous pipeline failed: %s", exc)
        result.pipeline_status = "error"
        result.error_message   = str(exc)
        result.save(update_fields=["pipeline_status", "error_message"])


"""
agrivision_api_views.py
=======================
Two API endpoints consumed by the "Analyze Crop" button in the frontend.

  POST /api/analyze-crop/
      Body: { "field_id": 5, "activity_id": 12 }}
      → Creates / resets an AnalysisResult row }(status = "queued")
      → Spawns a background thread that runs th}e full GEE pipeline
      → Returns: { "status": "queued", "result_id": 42 }

  GET  /api/analysis-status/<result_id>/
      → Reads AnalysisResult and returns the flat dict the frontend
        JS function _renderAnalysisPanel() expects.

PLACEMENT:
    yourapp/agrivision_api_views.py

ADD TO urls.py:
    from .agrivision_api_views import AnalyzeCropView, AnalysisStatusView

    urlpatterns += [
        path('api/analyze-crop/',            AnalyzeCropView.as_view(),   name='analyze_crop'),
        path('api/analysis-status/<int:pk>/', AnalysisStatusView.as_view(), name='analysis_status'),
    ]

REQUIREMENTS:
    Same as agrivision_pipeline.py — earthengine-api, numpy, requests, joblib, pandas
    No Celery needed — uses stdlib threading.
"""



# ──────────────────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────────────────

def _app_label() -> str:
    """
    Prefer the configured environment label when it matches an installed app,
    but fall back to the real app label used by this project.
    """
    configured = os.environ.get('DJANGO_APP_LABEL')
    candidates = []
    if configured:
        candidates.append(configured)
    candidates.extend(['base', 'fields'])

    for label in candidates:
        if label and label in apps.app_configs:
            return label

    return 'base'


def _get_model(name: str):
    label = _app_label()
    try:
        return apps.get_model(label, name)
    except LookupError:
        for fallback in ['base', 'fields']:
            if fallback == label:
                continue
            try:
                return apps.get_model(fallback, name)
            except LookupError:
                continue
        raise
 
 
def _result_to_frontend(ar) -> Dict[str, Any]:
    """
    Build the frontend payload entirely from full_bundle (JSONField).
    No individual DB columns are read for data — only pipeline_status,
    pk, and error_message come from the row itself.
    This means no null-column mismatches regardless of model migrations.
    """
    bundle = ar.full_bundle or {}

    sat     = bundle.get('satellite', {})
    climate = bundle.get('climate', {})
    soil    = bundle.get('soil', {})
    sci     = bundle.get('scientific_indices', {})
    yields  = bundle.get('scientific_yield', {})
    flags   = bundle.get('stress_flags', [])

    scene_count  = sat.get('scene_count', 0) or 0
    ready_for_ml = scene_count >= 2
    scenes       = bundle.get('scenes', [])

    payload: Dict[str, Any] = {
        'status':    ar.pipeline_status,
        'result_id': ar.pk,

        # Sentinel-2
        'ndvi_latest':       sat.get('ndvi_grain_filling'),
        'ndre_latest':       sat.get('ndre_grain_filling'),
        'evi_latest':        sat.get('evi_grain_filling'),
        'scene_count':       scene_count,
        'latest_scene_date': sat.get('latest_scene_date'),
        'scenes':            scenes,

        # Climate
        'total_rainfall_mm': climate.get('total_season_rainfall_mm'),
        'cumulative_gdd':    climate.get('gdd'),
        'heat_stress_frac':  climate.get('heat_stress_frac'),
        'recent_tmax_c':     climate.get('recent_tmax_c'),

        # Soil
        'soc_gkg': soil.get('organic_carbon'),
        'soil_ph': soil.get('ph'),

        # Scientific indices
        'scientific_indices': sci,

        # Yield estimates
        'scientific_yield':    yields,
        'ml_yield_t_ha':       bundle.get('predicted_yield_t_ha'),
        'ai_agronomic_report': bundle.get('ai_agronomic_report'),
        'is_extrapolated':     bundle.get('is_extrapolated', False),

        # SAR
        'vh_latest': sat.get('vh'),
        'vv_latest': sat.get('vv'),
        'rsi':       sat.get('rsi'),

        # Rainfall breakdown by stage
        'rainfall_by_stage': bundle.get('rainfall_by_stage', {}),

        # Advisory
        'stress_flags': flags,
        'risk_level':   bundle.get('risk_level'),
        'ready_for_ml': ready_for_ml,
    }

    if ar.pipeline_status == 'error' and ar.error_message:
        payload['message'] = ar.error_message

    return payload


def _run_pipeline_in_background(result_id: int) -> None:
    """
    Runs the full AgriVision pipeline for one AnalysisResult record.
    Called in a daemon thread.
    Saves ONLY pipeline_status + full_bundle to the DB.
    Everything else lives inside full_bundle — no individual column mapping.
    """
   

    AnalysisResult = _get_model('AnalysisResult')

    try:
        ar = AnalysisResult.objects.select_related(
            'field', 'field__owner', 'activity', 'activity__crop'
        ).prefetch_related(
            'field__growth_stages',
            'field__weather_data',
        ).get(pk=result_id)
    except AnalysisResult.DoesNotExist:
        logger.error("AnalysisResult #%s not found in background thread", result_id)
        return

    field    = ar.field
    activity = ar.activity

    try:
        # mark running
        ar.pipeline_status = 'running'
        ar.error_message   = None
        ar.save(update_fields=['pipeline_status', 'error_message'])

        # ── resolve inputs ────────────────────────────────────────────────
        coords = polygon_to_coords(field.geometry)
        lons   = [c[0] for c in coords]
        lats   = [c[1] for c in coords]
        lat    = float(np.mean(lats))
        lon    = float(np.mean(lons))

        county    = (field.owner.location or 'Unknown').strip()
        crop_obj  = activity.crop
        crop_name = (crop_obj.name or 'maize').lower()

        # Growth stages
        db_stages_qs = (
            field.growth_stages
            .filter(crop=crop_obj)
            .order_by('start_date')
        )
        stages = stages_from_growth_stage_qs(db_stages_qs)
        if len(stages) < 3:
            stages = derive_growth_stages(
                activity.date.strftime('%Y-%m-%d'),
                crop_name,
                crop_obj.growing_season_days or None,
            )

        preloaded_soil    = soil_context_from_db(field)
        preloaded_weather = weather_from_db(field)

        use_gee = os.environ.get('AGRIVISION_DISABLE_GEE', '').lower() not in ('1', 'true', 'yes')

        # ── initialise analyzers ──────────────────────────────────────────
        analyzer = AgrivisionCompleteAnalyzer(
            openweather_api_key=os.environ.get('OPENWEATHER_API_KEY'),
            use_gee=use_gee,
        )
        ml_pipeline = AgrivisionProductionPipeline(
            ml_model_path=os.environ.get(
                'AGRIVISION_ML_MODEL_PATH',
                'agrivision_ULTIMATE_voting_ensemble.pkl',
            ),
            hf_token=os.environ.get('HUGGINGFACE_API_TOKEN', ''),
            use_gee=use_gee,
        )

        # Pipeline 1 — scientific indices
        scientific = analyzer.analyze_field(
            coords=coords,
            crop_type=crop_name,
            growth_stages=stages,
            lat=lat,
            lon=lon,
            preloaded_soil=preloaded_soil,
            preloaded_weather=preloaded_weather,
        )

        # Pipeline 2 — ML yield + HuggingFace report enriched with indices
        ml_result = ml_pipeline.run(
            year=activity.date.year,
            coords=coords,
            county=county,
            growth_stages=stages,
            soil_context=scientific.get('soil'),
            scientific=scientific,          # ← pass all indices to report generator
        )
        sci_idx = scientific.get('scientific_indices', {})
        flags   = []
        if scientific.get('risk_level') in ('High', 'Very High'):
            flags.append(f"Crop health risk: {scientific['risk_level']}")
        if sci_idx.get('wsi', 0) > 50:
            flags.append('Water stress detected (WSI > 50 %)')
        if sci_idx.get('vhi', 100) < 40:
            flags.append('Vegetation health below normal (VHI < 40 %)')
        if sci_idx.get('csi', 100) < 40:
            flags.append('Climate suitability below optimal (CSI < 40 %)')

        # Merge everything into one bundle
        combined = {
            **scientific,
            **ml_result,
            'stress_flags': flags,   # ← now defined
        }

        # ── recent_tmax_c from weather series ────────────────────────────
        weather_series = combined.get('_weather_tmax_series', [])
        if len(weather_series) >= 7:
            combined.setdefault('climate', {})['recent_tmax_c'] = round(
                float(np.mean(weather_series[-7:])), 1
            )

        # update stress_flags in combined after merge
        combined['stress_flags'] = flags

       

        

        # ── save ONLY status + full_bundle ────────────────────────────────
        ar.pipeline_status = 'done'
        ar.error_message   = None
        ar.full_bundle     = combined
        ar.save(update_fields=['pipeline_status', 'error_message', 'full_bundle'])

        logger.info(
            "AnalysisResult #%s done — risk=%s ml_yield=%s",
            result_id,
            combined.get('risk_level', 'N/A'),
            combined.get('predicted_yield_t_ha', 'N/A'),
        )

    except Exception as exc:
        logger.error(
            "Pipeline failed for AnalysisResult #%s: %s\n%s",
            result_id, exc, traceback.format_exc()
        )
        try:
            ar.pipeline_status = 'error'
            ar.error_message   = str(exc)[:500]
            ar.save(update_fields=['pipeline_status', 'error_message'])
        except Exception:
            pass



class AnalyzeCropView(LoginRequiredMixin, View):
    """
    Triggered by the "Analyze Crop" button.
 
    Request body (JSON):
        { "field_id": 5, "activity_id": 12 }
 
    Success response:
        { "status": "queued", "result_id": 42 }
 
    Error response:
        { "status": "error", "message": "..." }
 
    What it does:
    1. Validates field ownership (Field.owner == request.user)
    2. Validates the FieldActivity exists and belongs to that field
    3. Creates / resets the AnalysisResult row to status='queued'
    4. Spawns a daemon thread that runs _run_pipeline_in_background(result_id)
    5. Returns immediately with result_id so the frontend can start polling
    """
 
    http_method_names = ['post']
 
    def post(self, request, *args, **kwargs):
        # ── parse body ────────────────────────────────────────────────────
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'status': 'error', 'message': 'Invalid JSON body'}, status=400)
 
        field_id    = body.get('field_id')
        activity_id = body.get('activity_id')
 
        if not field_id or not activity_id:
            return JsonResponse(
                {'status': 'error', 'message': 'field_id and activity_id are required'},
                status=400,
            )
 
        # ── load models ───────────────────────────────────────────────────
        Field         = _get_model('Field')
        FieldActivity = _get_model('FieldActivity')
        AnalysisResult = _get_model('AnalysisResult')
 
        # ── validate field ownership ──────────────────────────────────────
        # Field.owner is a FK to CustomUser
        try:
            field = Field.objects.get(
                pk=field_id,
                owner=request.user,         # ← Field.owner = ForeignKey(CustomUser)
            )
        except Field.DoesNotExist:
            return JsonResponse(
                {'status': 'error', 'message': 'Field not found or access denied'},
                status=404,
            )
 
        # ── validate activity ─────────────────────────────────────────────
        # FieldActivity.field FK, activity_type='planting', crop must be set
        try:
            activity = FieldActivity.objects.select_related('crop').get(
                pk=activity_id,
                field=field,                 # ← FieldActivity.field FK
                activity_type='planting',    # ← FieldActivity.ACTIVITY_TYPES
                crop__isnull=False,          # ← Crop FK must exist
            )
        except FieldActivity.DoesNotExist:
            return JsonResponse(
                {
                    'status':  'error',
                    'message': (
                        'No planting activity found for this field. '
                        'Register a crop first.'
                    ),
                },
                status=404,
            )
 
        # ── prevent duplicate simultaneous runs ───────────────────────────
        existing = AnalysisResult.objects.filter(
            field=field,
            activity=activity,
            pipeline_status='running',       # ← AnalysisResult.pipeline_status
        ).first()
        if existing:
            return JsonResponse(
                {
                    'status':    'running',
                    'result_id': existing.pk,
                    'message':   'Analysis already running for this activity',
                }
            )
 
        # ── create / reset AnalysisResult ─────────────────────────────────
        # unique_together = ['field', 'activity']
        ar, _ = AnalysisResult.objects.update_or_create(
            field=field,                     # ← AnalysisResult.field FK
            activity=activity,               # ← AnalysisResult.activity FK
            defaults={
                'pipeline_status': 'queued', # ← AnalysisResult.pipeline_status
                'error_message':   None,     # ← AnalysisResult.error_message
                'full_bundle':     {},       # ← AnalysisResult.full_bundle (JSONField)
                'stress_flags':    [],       # ← AnalysisResult.stress_flags (JSONField)
                'scene_count':     0,        # ← AnalysisResult.scene_count
            },
        )
 
        # ── spawn background thread ───────────────────────────────────────
        t = threading.Thread(
            target=_run_pipeline_in_background,
            args=(ar.pk,),
            daemon=True,
            name=f'agrivision-pipeline-{ar.pk}',
        )
        t.start()
        logger.info(
            "Spawned pipeline thread for AnalysisResult #%s "
            "(field=%s, activity=%s, crop=%s)",
            ar.pk, field.pk, activity.pk, activity.crop.name,
        )
 
        return JsonResponse({'status': 'queued', 'result_id': ar.pk})
 
 
# ──────────────────────────────────────────────────────────────────────────────
# VIEW 2 — GET /api/analysis-status/<pk>/
# ──────────────────────────────────────────────────────────────────────────────
 
class AnalysisStatusView(LoginRequiredMixin, View):
    """
    Polled every 4 seconds by the frontend JS until status = 'done' | 'error'.
 
    URL parameter:
        pk  — AnalysisResult primary key (returned by AnalyzeCropView)
 
    Response shape (matches _renderAnalysisPanel JS function):
    {
        "status":             "done" | "running" | "queued" | "error",
        "result_id":          42,
        "ndvi_latest":        0.72,
        "ndre_latest":        null,
        "evi_latest":         0.55,
        "scene_count":        8,
        "latest_scene_date":  "2024-06-15",
        "scenes":             [{"date": "2024-06-15", "ndvi": 0.72}, ...],
        "total_rainfall_mm":  450.0,
        "cumulative_gdd":     1200.0,
        "heat_stress_frac":   0.05,
        "recent_tmax_c":      28.4,
        "soc_gkg":            22.5,
        "soil_ph":            6.2,
        "stress_flags":       ["Water stress detected (WSI > 50 %)"],
        "ready_for_ml":       true
    }
    """
 
    http_method_names = ['get']
 
    def get(self, request, pk: int, *args, **kwargs):
        AnalysisResult = _get_model('AnalysisResult')
 
        try:
            ar = AnalysisResult.objects.select_related(
                'field',
                'field__owner',
            ).get(
                pk=pk,
                field__owner=request.user,   # ← ownership check: Field.owner = CustomUser FK
            )
        except AnalysisResult.DoesNotExist:
            return JsonResponse(
                {'status': 'error', 'message': 'Result not found or access denied'},
                status=404,
            )
 
        # While queued / running, return a lightweight response so the
        # frontend doesn't try to render half-filled data.
        if ar.pipeline_status in ('queued', 'running'):
            return JsonResponse({
                'status':    ar.pipeline_status,
                'result_id': ar.pk,
            })
 
        # Done or error — return full payload
        payload = _result_to_frontend(ar)
        return JsonResponse(payload)