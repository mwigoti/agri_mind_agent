from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _

from django.utils.timezone import now
from django.contrib.gis.db import models








class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
    
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractUser):
    
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    registered_via_ussd = models.BooleanField(default=False)
    ussd_registration_date = models.DateTimeField(null=True, blank=True)

    
    objects = CustomUserManager()

    def __str__(self):
        return self.email

class Field(models.Model):
    owner=models.ForeignKey(CustomUser, on_delete=models.CASCADE, default=True)
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    geometry = models.PolygonField(srid=4326, geography=True)
 
    created_at = models.DateTimeField(default=now)
    area = models.FloatField(default=0.0)

    def __str__(self):
        return self.name

class USSDSession(models.Model):
    session_id = models.CharField(max_length=100, unique=True)
    phone_number = models.CharField(max_length=15)
    current_step = models.CharField(max_length=50, default='start')
    data = models.JSONField(default=dict)  # Store temporary registration data
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Session {self.session_id} - {self.phone_number}"

    class Meta:
        db_table = 'ussd_sessions'