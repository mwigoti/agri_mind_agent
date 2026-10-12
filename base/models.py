from django.contrib.auth.models import User
from django.db import models

from django.contrib.gis.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.user.username


from django.db import models
from django.utils.timezone import now
from django.utils.timezone import datetime

class Field(models.Model):
    name = models.CharField(max_length=255)
    geometry = models.JSONField(default=dict)

    def save(self, *args, **kwargs):
        # Ensure datetime objects are serialized
        if isinstance(self.geometry, dict):
            for key, value in self.geometry.items():
                if isinstance(value, datetime):
                    self.geometry[key] = value.isoformat()
        super().save(*args, **kwargs)

