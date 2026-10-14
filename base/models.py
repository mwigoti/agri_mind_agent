from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _

from django.utils.timezone import now
from django.contrib.gis.db import models



from django.db import models
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
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    objects = CustomUserManager()

    def __str__(self):
        return self.email

class Field(models.Model):
    owner=models.ForeignKey(CustomUser, on_delete=models.CASCADE, default=True)
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    geometry = models.PolygonField(srid=3857, geography=False)  
    created_at = models.DateTimeField(default=now)
    area = models.FloatField(default=0.0)

    def __str__(self):
        return self.name

