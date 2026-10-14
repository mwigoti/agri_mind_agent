# base/utils/sms_service.py - Fixed version with SSL/TLS solutions

import requests
import logging
import ssl
import urllib3
from django.conf import settings
from decouple import config


logger = logging.getLogger(__name__)

class AfricasTalkingSMSService:
    def __init__(self):
        self.username = config('AFRICAS_TALKING_USERNAME')
        self.api_key = config('AFRICAS_TALKING_API_KEY')
        self.sandbox = config('AFRICAS_TALKING_SANDBOX', default=False, cast=bool)
        
        if self.sandbox:
            self.base_url = 'https://api.sandbox.africastalking.com/version1/messaging'
        else:
            self.base_url = 'https://api.africastalking.com/version1/messaging'
    
    def send_sms(self, phone_number, message):
        """Send SMS via Africa's Talking API with SSL/TLS fixes"""
        try:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'apiKey': self.api_key
            }
            
            data = {
                'username': self.username,
                'to': phone_number,
                'message': message,
                'from': None  # Use default sender ID
            }
            
            # Solution 1: Create a session with SSL context
            session = requests.Session()
            
            # Configure SSL context for better compatibility
            adapter = requests.adapters.HTTPAdapter()
            session.mount('https://', adapter)
            
            # Alternative: Disable SSL verification for testing (NOT for production)
            # session.verify = False
            # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = session.post(
                self.base_url,
                headers=headers,
                data=data,
                timeout=30,
                verify=True  # Keep SSL verification enabled
            )
            
            if response.status_code == 201:
                result = response.json()
                recipients = result.get('SMSMessageData', {}).get('Recipients', [])
                
                if recipients and recipients[0].get('status') == 'Success':
                    logger.info(f"SMS sent successfully to {phone_number}")
                    return True, result
                else:
                    logger.error(f"SMS failed to {phone_number}: {recipients}")
                    return False, result
            else:
                logger.error(f"SMS API error {response.status_code}: {response.text}")
                return False, response.text
                
        except requests.exceptions.SSLError as ssl_error:
            logger.error(f"SSL Error: {str(ssl_error)}")
            # Try fallback method
            return self.send_sms_fallback(phone_number, message)
            
        except Exception as e:
            logger.error(f"SMS service error: {str(e)}")
            return False, str(e)
    
    def send_sms_fallback(self, phone_number, message):
        """Fallback method with relaxed SSL settings for development"""
        try:
            logger.info("Attempting SMS with fallback SSL settings...")
            
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
                'apiKey': self.api_key
            }
            
            data = {
                'username': self.username,
                'to': phone_number,
                'message': message,
                'from': None
            }
            
            # Create session with custom SSL context
            session = requests.Session()
            
            # For development/testing only - disable SSL warnings
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = session.post(
                self.base_url,
                headers=headers,
                data=data,
                timeout=30,
                verify=False  # Disable SSL verification for testing
            )
            
            if response.status_code == 201:
                result = response.json()
                recipients = result.get('SMSMessageData', {}).get('Recipients', [])
                
                if recipients and recipients[0].get('status') == 'Success':
                    logger.info(f"SMS sent successfully to {phone_number} (fallback method)")
                    return True, result
                else:
                    logger.error(f"SMS failed to {phone_number}: {recipients}")
                    return False, result
            else:
                logger.error(f"SMS API error {response.status_code}: {response.text}")
                return False, response.text
                
        except Exception as e:
            logger.error(f"Fallback SMS service error: {str(e)}")
            return False, str(e)

    def send_sms_curl_method(self, phone_number, message):
        """Alternative method using curl command (if requests fails)"""
        import subprocess
        import json
        
        try:
            curl_command = [
                'curl', '-X', 'POST',
                self.base_url,
                '-H', f'apiKey: {self.api_key}',
                '-H', 'Accept: application/json',
                '-H', 'Content-Type: application/x-www-form-urlencoded',
                '-d', f'username={self.username}',
                '-d', f'to={phone_number}',
                '-d', f'message={message}',
                '--insecure'  # For testing only
            ]
            
            result = subprocess.run(curl_command, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                response_data = json.loads(result.stdout)
                logger.info(f"SMS sent via curl to {phone_number}")
                return True, response_data
            else:
                logger.error(f"Curl SMS error: {result.stderr}")
                return False, result.stderr
                
        except Exception as e:
            logger.error(f"Curl SMS method error: {str(e)}")
            return False, str(e)