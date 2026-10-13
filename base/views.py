from pyproj import Transformer
from django.views.decorators.http import require_GET
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
import json
from .models import *
from django.core.mail import send_mail, BadHeaderError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.gis.geos import Polygon
from django.core.serializers import serialize
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt, csrf_protect, requires_csrf_token, ensure_csrf_cookie
from django.utils.decorators import method_decorator  # Add this import
from django.views import View
from django.contrib.gis.geos import Point
from django.contrib.gis.db.models.functions import Transform


# Create your views here.
def home(request):
    return render(request, 'index.html')


def register(request):
    return render(request, 'register.html')

def login(request):
    return render(request, 'register.html')

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

def map(request):
    return render(request, 'map.html')

def weather(request):
    return render(request, 'weather.html')

def upgrade(request):
    return render(request, 'upgrade.html')

def signin(request):
    return render(request, 'signin.html')

def pricing(request):
    return render(request, 'pricing.html')

class SaveFieldView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            name = data.get('name', 'Unnamed Field')
            coordinates = data.get('coordinates')

            if not coordinates or len(coordinates) < 3:
                return Response({"error": "At least 3 points are required"})
            
            # close the polygon by repeating first

            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])

            # create polygon 

            polygon = Polygon(coordinates)

            #save to database
            field=Field.objects.create(name=name, geometry=polygon)

            serializer= FieldGeoJSONSerializer(field)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

           
# Retrieve fields as geojson from db

from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import Field
from .serializers import FieldGeoJSONSerializer

@api_view(['GET'])
def get_fields_geojson(request):
    fields = Field.objects.all()  # Query all fields
    serializer = FieldGeoJSONSerializer(fields, many=True)  # Serialize data
    return Response(serializer.data) 
@method_decorator(csrf_exempt, name='dispatch')
class DeleteFieldView(APIView):
    def delete(self, request, id):
        field = get_object_or_404(Field, id=id)
        field.delete()
        return Response({'message': 'Field deleted successfully'}, status=status.HTTP_200_OK)


@require_GET
def get_field_center(request, id):
    try:
        # Fetch the field by ID
        field = Field.objects.get(pk=id)
        
        # Create a transformer from UTM Zone 37S to WGS84
        transformer = Transformer.from_crs(
            "EPSG:3857",  # UTM Zone 37S (WGS 84)
            "EPSG:4326",   # WGS84 lat/lon
            always_xy=True  # Ensure x, y order
        )
        
        # Get the centroid of the geometry
        center = field.geometry.centroid
        
        # Transform the coordinates
        lon, lat = transformer.transform(center.x, center.y)
        
        return JsonResponse({
            "id": field.id,
            "name": field.name,
            "latitude": lat,
            "longitude": lon,
        })
    
    except Field.DoesNotExist:
        return JsonResponse({
            "error": f"Field with ID {id} not found"
        }, status=404)
    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=500)