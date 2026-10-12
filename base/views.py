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
from .models import *

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

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

@csrf_exempt
def save_field(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        name = data.get('name')
        polygon = data.get('polygon')
        
        if not name or not polygon:
            return JsonResponse({'success': False, 'error': 'Name or polygon is missing'}, status=400)
        
        # Save to the database (assuming `Field` model is already created)
        try:
            field = Field.objects.create(name=name, geometry=polygon)
            return JsonResponse({'success': True, 'field_id': field.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=405)
