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


def check_analysis_engine(request):
    try:
        response = requests.post("http://127.0.0.1:8001/health", timeout=5)
        return JsonResponse(response.json())
    except Exception as e:
        return JsonResponse({"error": str(e)})
# Add this to your views.py



logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class VRAAnalysisView(APIView):
    """
    View to initiate VRA analysis for a specific field
    Sends field geometry to Rust analysis engine
    """
    
    def post(self, request, field_id):
        try:
            # Get the field from database
            field = get_object_or_404(Field, id=field_id, owner=request.user)
            
            # Prepare field data for Rust engine
            field_data = self.prepare_field_data(field)
            
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
                    "analysis_data": rust_response.get('data')
                }, status=status.HTTP_200_OK)
            else:
                return Response({
                    "success": False,
                    "error": rust_response.get('error', 'Analysis engine error')
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Field.DoesNotExist:
            return Response({
                "success": False,
                "error": "Field not found or access denied"
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"VRA Analysis error for field {field_id}: {str(e)}")
            return Response({
                "success": False,
                "error": f"Analysis failed: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def prepare_field_data(self, field):
        """
        Prepare field data in the format expected by Rust engine
        """
        # Convert Django geometry to GeoJSON
        geometry_geojson = json.loads(field.geometry.geojson)
        
        return {
            "id": field.id,
            "name": field.name,
            "area": float(field.area),
            "geometry": geometry_geojson
        }
    
    def send_to_rust_engine(self, field_data):
        """
        Send field data to Rust analysis engine
        """
        rust_url = "http://127.0.0.1:8001/generate-vra-maps"
        
        try:
            # Send as array since Rust expects Vec<Field>
            payload = [field_data]
            
            response = requests.post(
                rust_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=300  # 5 minutes timeout for satellite data processing
            )
            
            response.raise_for_status()
            return {
                "success": True,
                "data": response.json()
            }
            
        except requests.exceptions.Timeout:
            return {
                "success": False,
                "error": "Analysis engine timeout - satellite data processing took too long"
            }
        except requests.exceptions.ConnectionError:
            return {
                "success": False,
                "error": "Cannot connect to analysis engine. Please ensure the service is running."
            }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error": f"Request error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }
    
    def store_analysis_results(self, field, analysis_data):
        """
        Store analysis results in database if needed
        You can extend this to save results to a separate model
        """
        # Optional: Create a VRAAnalysis model to store results
        # For now, we'll just log the completion
        logger.info(f"VRA analysis completed for field {field.id} - {field.name}")
        
        # You could save to a VRAAnalysis model here:
        # VRAAnalysis.objects.create(
        #     field=field,
        #     analysis_data=analysis_data,
        #     created_at=timezone.now()
        # )

@login_required(login_url="login")
def vra_analysis_page(request, field_id):
    """
    Render the VRA analysis page for a specific field
    """
    try:
        field = get_object_or_404(Field, id=field_id, owner=request.user)
        
        context = {
            'field': field,
            'field_id': field_id,
            'field_name': field.name,
            'field_area': field.area,
        }
        
        return render(request, 'vra_analysis.html', context)
        
    except Field.DoesNotExist:
        messages.error(request, 'Field not found or access denied')
        return redirect('map')

def check_vra_engine_status(request):
    """
    Check if the VRA analysis engine is running
    """
    try:
        response = requests.post(
            "http://127.0.0.1:8001/health", 
            timeout=5,
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            return JsonResponse({
                "status": "online",
                "service": "VRA Analysis Engine",
                "message": "Service is running and ready"
            })
        else:
            return JsonResponse({
                "status": "error",
                "message": f"Service returned status {response.status_code}"
            })
            
    except requests.exceptions.ConnectionError:
        return JsonResponse({
            "status": "offline",
            "message": "VRA Analysis Engine is not running"
        })
    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": f"Error checking service: {str(e)}"
        })


