from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.models import User  # Assuming you're using the default User model
from .models import UserProfile  # Import your UserProfile model
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
import json
from math import sqrt

from django.core.mail import send_mail, BadHeaderError


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

@ensure_csrf_cookie
@require_http_methods(["POST"])
def calculate_field_center(request):
    try:
        data = json.loads(request.body)
        coordinates = data.get('coordinates', [])
        
        if not coordinates or len(coordinates) < 3:
            return JsonResponse({'error': 'At least three points are required'}, status=400)
        
        # Calculate center
        x_coords = [point[0] for point in coordinates]
        y_coords = [point[1] for point in coordinates]
        
        center_x = sum(x_coords) / len(coordinates)
        center_y = sum(y_coords) / len(coordinates)
        
        # Calculate approximate area using the shoelace formula
        area = calculate_area(coordinates)
        
        # Convert area from square meters to hectares
        area_hectares = abs(area) / 10000  # 1 hectare = 10000 square meters
        
        return JsonResponse({
            'center': {
                'lng': center_x,
                'lat': center_y
            },
            'area': area_hectares,
            'num_points': len(coordinates)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def calculate_area(coordinates):
    """
    Calculate area using the shoelace formula (Gauss's area formula)
    """
    n = len(coordinates)
    area = 0.0
    
    for i in range(n):
        j = (i + 1) % n
        area += coordinates[i][0] * coordinates[j][1]
        area -= coordinates[j][0] * coordinates[i][1]
        area=area/2.0
    
    return render('area.html', 'area:area')