from django.contrib import admin
from django.contrib.admin.sites import AlreadyRegistered
from django.apps import apps

# Get all models
models = apps.get_models()

# Register each model
for model in models:
    try:
        admin.site.register(model)
    except AlreadyRegistered:
        pass
