from django.contrib.auth.models import User
from django.utils.timezone import now
from django.contrib.gis.db import models

# UserProfile Model - Removed the redundant email field
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.user.username



class Field(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    geometry = models.PolygonField(srid=3857, geography=False)  
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.name

