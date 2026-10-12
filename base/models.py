from django.contrib.auth.models import User
from django.utils.timezone import now
from django.contrib.gis.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    email = models.CharField(max_length=255)
    address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.user.username



class Field(models.Model):
    name = models.CharField(max_length=255)
    geometry = models.PolygonField()  # Stores the polygon geometry
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.name

