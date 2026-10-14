from __future__ import print_function

import africastalking

class SMS:
    def __init__(self):
        # Set your app credentials
        self.username = "henrymwoha02@gmail.com"  # Change to your production username if not in sandbox
        self.api_key = "atsk_6db09cd774ee1ec6be727befbd993cefa5e876a6cf3d7c14bb439116ede60bf3ea8034fb"  # Replace with your new API key

        # Initialize the SDK
        africastalking.initialize(self.username, self.api_key)

        # Get the SMS service
        self.sms = africastalking.SMS

    def send(self):
        # Set the numbers you want to send to in international format
        recipients = ["+254107914415"]

        # Set your message
        message = "I'm a lumberjack and it's ok, I sleep all night and I work all day"

        # Set your shortCode or senderId (optional)
        sender = "AFRICASTKNG"  # Use your approved sender ID or short code

        try:
            # That's it, hit send and we'll take care of the rest.
            response = self.sms.send(message, recipients, sender)
            print(response)
        except Exception as e:
            print('Encountered an error while sending: %s' % str(e))

if __name__ == '__main__':
    SMS().send()
