import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class SMSService:
    """SMS service orchestrator"""
    
    def __init__(self):
        self.providers = {
            'twilio': TwilioClient(),
            'africas_talking': AfricasTalkingClient(),
        }
        self.default_provider = 'africas_talking'  # Better for African markets
    
    def send_sms(self, to, message, provider=None):
        """Send SMS using specified or default provider"""
        if provider is None:
            provider = self.default_provider
        
        try:
            client = self.providers[provider]
            return client.send_sms(to, message)
        except Exception as e:
            logger.error(f"SMS sending failed with {provider}: {e}")
            # Try fallback provider
            fallback = 'twilio' if provider == 'africas_talking' else 'africas_talking'
            try:
                fallback_client = self.providers[fallback]
                return fallback_client.send_sms(to, message)
            except Exception as fallback_error:
                logger.error(f"Fallback SMS also failed: {fallback_error}")
                return {'success': False, 'error': str(fallback_error)}
    
    def send_whatsapp(self, to, message, provider=None):
        """Send WhatsApp message"""
        if provider is None:
            provider = self.default_provider
        
        try:
            client = self.providers[provider]
            if hasattr(client, 'send_whatsapp'):
                return client.send_whatsapp(to, message)
            else:
                return {'success': False, 'error': 'WhatsApp not supported by provider'}
        except Exception as e:
            logger.error(f"WhatsApp sending failed: {e}")
            return {'success': False, 'error': str(e)}

class TwilioClient:
    """Twilio SMS/WhatsApp client"""
    
    def __init__(self):
        self.account_sid = settings.SMS_API_SETTINGS['TWILIO']['ACCOUNT_SID']
        self.auth_token = settings.SMS_API_SETTINGS['TWILIO']['AUTH_TOKEN']
        self.base_url = "https://api.twilio.com/2010-04-01"
    
    def send_sms(self, to, message, from_number=None):
        """Send SMS via Twilio"""
        if not from_number:
            from_number = getattr(settings, 'TWILIO_FROM_NUMBER', '+1234567890')
        
        url = f"{self.base_url}/Accounts/{self.account_sid}/Messages.json"
        
        data = {
            'From': from_number,
            'To': to,
            'Body': message
        }
        
        try:
            response = requests.post(
                url,
                data=data,
                auth=(self.account_sid, self.auth_token),
                timeout=30
            )
            
            if response.status_code == 201:
                response_data = response.json()
                return {
                    'success': True,
                    'message_id': response_data['sid'],
                    'status': response_data['status']
                }
            else:
                return {
                    'success': False,
                    'error': f"Twilio error: {response.status_code} - {response.text}"
                }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def send_whatsapp(self, to, message):
        """Send WhatsApp message via Twilio"""
        return self.send_sms(
            to=f"whatsapp:{to}",
            message=message,
            from_number="whatsapp:+14155238886"  # Twilio Sandbox number
        )

class AfricasTalkingClient:
    """Africa's Talking SMS client"""
    
    def __init__(self):
        self.username = settings.SMS_API_SETTINGS['AFRICAS_TALKING']['USERNAME']
        self.api_key = settings.SMS_API_SETTINGS['AFRICAS_TALKING']['API_KEY']
        self.base_url = "https://api.africastalking.com/version1"
    
    def send_sms(self, to, message, sender_id=None):
        """Send SMS via Africa's Talking"""
        if not sender_id:
            sender_id = getattr(settings, 'AFRICAS_TALKING_SENDER_ID', 'AgriVision')
        
        url = f"{self.base_url}/messaging"
        
        headers = {
            'ApiKey': self.api_key,
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        data = {
            'username': self.username,
            'to': to,
            'message': message,
            'from': sender_id
        }
        
        try:
            response = requests.post(url, data=data, headers=headers, timeout=30)
            
            if response.status_code == 201:
                response_data = response.json()
                if response_data['SMSMessageData']['Recipients']:
                    recipient = response_data['SMSMessageData']['Recipients'][0]
                    return {
                        'success': recipient['status'] == 'Success',
                        'message_id': recipient.get('messageId', ''),
                        'cost': recipient.get('cost', ''),
                        'status': recipient['status']
                    }
            
            return {
                'success': False,
                'error': f"Africa's Talking error: {response.status_code} - {response.text}"
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}