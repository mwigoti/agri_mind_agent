from __future__ import print_function

import os
import africastalking
from decouple import config


class SMS:
    def __init__(self):
        self.username = config("AFRICAS_TALKING_USERNAME", default="sandbox")
        self.api_key = config("AFRICAS_TALKING_API_KEY", default="")

        # Initialize the SDK
        africastalking.initialize(self.username, self.api_key)

        # Get the SMS service
        self.sms = africastalking.SMS

    def send(self, recipients=None, message=None):
        recipients = recipients or [os.getenv("TEST_RECIPIENT_PHONE", "+254700000000")]
        message = message or "AgriVision SMS Diagnostic Test"
        sender = config("AFRICAS_TALKING_SENDER_ID", default="AFRICASTKNG")

        try:
            response = self.sms.send(message, recipients, sender)
            print("Response:", response)
            return response
        except Exception as e:
            print("Encountered an error while sending: %s" % str(e))
            return None


if __name__ == "__main__":
    SMS().send()

