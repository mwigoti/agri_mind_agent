from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
import json
from django.utils.decorators import method_decorator
from django.contrib.gis.geos import GEOSGeometry
import logging
import stripe.error
from .models import *
from django.core.mail import send_mail, BadHeaderError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.gis.geos import Polygon
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator  # Add this import
from django.contrib.auth import get_user_model
from django.contrib.auth import logout
from .analysis import IntegratedSoilAnalyzer

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
            area = data.get('area', 0.0)  # Get area from frontend
            owner = request.user

            if not coordinates or len(coordinates) < 3:
                return Response({"error": "At least 3 points are required"})
            
            # Close the polygon by repeating first coordinate
            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])

            # Create polygon 
            polygon = Polygon(coordinates)

            # Save to database with the calculated area
            field = Field.objects.create(
                owner=owner, 
                name=name, 
                geometry=polygon,
                area=area  # Save the area from frontend
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
    try:
        huggingface_token = settings.HUGGINGFACE_TOKEN
        analyzer = IntegratedSoilAnalyzer()
        result = analyzer.analyze_combined_data(id, huggingface_token)

        # Ensure 'analysis' exists
        if "analysis" not in result:
            result["analysis"] = "No analysis available."

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':  # If AJAX request
            return JsonResponse({"success": True, "result": result})

        return render(request, 'analysis.html', {"result": result, "id": id})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)

        
def load(request):
    return render(request, 'load.html')


def res(request):
    return render(request, 'result.html')

# views.py
import requests











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
        
        
def vra_page(request):
    return render(request, 'vra_analysis.html')
