import threading
import requests

from django.utils.deprecation import MiddlewareMixin

def fetch_location_and_update(user, ip):
    try:
        response = requests.get(f'https://ipapi.co/{ip}/json/')
        data = response.json()
        location = data.get('city') or data.get('region') or data.get('country_name')
        
        if location and (not user.location or user.location.lower() != location.lower()):
            user.location = location
            user.save(update_fields=['location'])
            
    except Exception as e:
        print(f"[Location Middleware] failed to fetch location: {e}")
        
class LocationAutoUpdateMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.user.is_authenticated:
            ip = get_client_ip(request)
            thread = threading.Thread(target=fetch_location_and_update, args=(request.user, ip))
            thread.start()

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    if ip in ('127.0.0.1', '::1'):
        
        ip = '102.128.64.123'     
    return ip

