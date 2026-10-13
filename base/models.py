from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from django.contrib.gis.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver

class CustomUser(AbstractUser):
    email = models.EmailField(_('email address'), unique=True)
    is_email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True, db_index=True)

    def __str__(self):
        return self.email

@receiver(pre_save, sender=CustomUser)
def add_verification_token(sender, instance, **kwargs):
    if not instance.verification_token:
        instance.verification_token = get_random_string(64)


class Field(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    geometry = models.PolygonField(srid=3857, geography=False)  
    created_at = models.DateTimeField(default=now)

    def __str__(self):
        return self.name

