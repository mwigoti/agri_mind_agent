from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.contrib.gis.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.contrib.gis.db import models 

class CustomUser(AbstractUser):
    name = models.CharField(max_length=200, blank=True, null=True)  # Name is optional
    email = models.EmailField(unique=True, null=False)  # Email is required and unique
    
    USERNAME_FIELD = 'email'  # Use email as the unique identifier for authentication
    REQUIRED_FIELDS = ['username']  # Additional fields required when creating a superuser

    def __str__(self):
        return self.email


class Field(models.Model):
    
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    geometry = models.PolygonField(srid=3857, geography=False)  
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.name

