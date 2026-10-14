from rest_framework import serializers
from .models import Task, TaskCategory, TaskTemplate, ComplianceRecord

class TaskCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskCategory
        fields = '__all__'

class TaskSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    field_name = serializers.CharField(source='field.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.get_full_name', read_only=True)
    
    class Meta:
        model = Task
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at', 'created_by']

class TaskCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating tasks with weather awareness"""
    
    class Meta:
        model = Task
        exclude = ['created_by']
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

class TaskTemplateSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = TaskTemplate
        fields = '__all__'
        read_only_fields = ['created_by', 'created_at']

class ComplianceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplianceRecord
        fields = '__all__'
