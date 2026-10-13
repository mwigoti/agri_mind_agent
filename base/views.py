
from django.shortcuts import render, redirect
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
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


from django.shortcuts import render, redirect
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
    return render(request, 'upgrade.html')


def pricing(request):
    return render(request, 'pricing.html')


class SaveFieldView(APIView):
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            name = data.get('name', 'Unnamed Field')
            coordinates = data.get('coordinates')
            owner=request.user

            if not coordinates or len(coordinates) < 3:
                return Response({"error": "At least 3 points are required"})
            
            # close the polygon by repeating first

            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])

            # create polygon 

            polygon = Polygon(coordinates)

            #save to database
            field=Field.objects.create(owner=owner,name=name, geometry=polygon)

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
    fields = Field.objects.filter(owner=request.user)  # Query all fields
    serializer = FieldGeoJSONSerializer(fields, many=True)  # Serialize data
    return Response(serializer.data) 
@method_decorator(csrf_exempt, name='dispatch')
class DeleteFieldView(APIView):
    def delete(self, request, id):
        field = get_object_or_404(Field, id=id)
        field.delete()
        return Response({'message': 'Field deleted successfully'}, status=status.HTTP_200_OK)


def analyze_field_view(request, id):
    try:
        huggingface_token = settings.HUGGINGFACE_TOKEN
        analyzer = IntegratedSoilAnalyzer()

        result = analyzer.analyze_combined_data(id, huggingface_token)

        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({
            "success": False,
            "error": str(e)

        }, status=500)
    
def load(request):
    return render(request, 'load.html')


def res(request):
    return render(request, 'result.html')