from django.core.management.base import BaseCommand
from base.utils.sms_service import AfricasTalkingSMSService

class Command(BaseCommand):
    help = 'Test SMS functionality'

    def add_arguments(self, parser):
        parser.add_argument('phone_number', type=str, help='Phone number to send SMS to')
        parser.add_argument('message', type=str, help='Message to send')

    def handle(self, *args, **options):
        sms_service = AfricasTalkingSMSService()
        phone_number = options['phone_number']
        message = options['message']
        
        self.stdout.write(f"Sending SMS to {phone_number}...")
        
        success, result = sms_service.send_sms(phone_number, message)
        
        if success:
            self.stdout.write(
                self.style.SUCCESS(f'SMS sent successfully to {phone_number}')
            )
        else:
            self.stdout.write(
                self.style.ERROR(f'SMS failed: {result}')
            )