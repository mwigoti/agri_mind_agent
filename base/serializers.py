from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework import serializers
from .models import Field

class FieldGeoJSONSerializer(GeoFeatureModelSerializer):
    owner = serializers.ReadOnlyField(source='owner.username')
    
    class Meta:
        model = Field
        geo_field = 'geometry'
        fields = ('id', 'name', 'owner', 'created_at', 'geometry')