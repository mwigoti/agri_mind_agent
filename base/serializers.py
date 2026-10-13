from rest_framework_gis.serializers import GeoFeatureModelSerializer
from .models import Field

class FieldGeoJSONSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Field
        fields = ('id', 'name', 'geometry', 'created_at') 
        geo_field = 'geometry'  