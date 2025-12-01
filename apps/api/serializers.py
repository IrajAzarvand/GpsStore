from rest_framework import serializers
from apps.accounts.models import User, UserDevice
from apps.gps_devices.models import State, Model, Device, LocationData, DeviceState, RawGpsData
from apps.api.models import ApiKey

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'phone', 'date_joined')
        read_only_fields = ('id', 'date_joined')
class StateSerializer(serializers.ModelSerializer):
    """Serializer for State model"""
    class Meta:
        model = State
        fields = '__all__'
class ModelSerializer(serializers.ModelSerializer):
    """Serializer for Device Model"""
    class Meta:
        model = Model
        fields = '__all__'
class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for Device model"""
    owner = UserSerializer(read_only=True)
    model = ModelSerializer(read_only=True)
    
    class Meta:
        model = Device
        fields = '__all__'
class LocationDataSerializer(serializers.ModelSerializer):
    """Serializer for LocationData model"""
    device = DeviceSerializer(read_only=True)
    
    class Meta:
        model = LocationData
        fields = '__all__'
class DeviceStateSerializer(serializers.ModelSerializer):
    """Serializer for DeviceState model"""
    device = DeviceSerializer(read_only=True)
    state = StateSerializer(read_only=True)
    location_data = LocationDataSerializer(read_only=True)
    
    class Meta:
        model = DeviceState
        fields = '__all__'
class RawGpsDataSerializer(serializers.ModelSerializer):
    """Serializer for RawGpsData model"""
    class Meta:
        model = RawGpsData
        fields = '__all__'
class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer for UserDevice model"""
    user = UserSerializer(read_only=True)
    device = DeviceSerializer(read_only=True)
    
    class Meta:
        model = UserDevice
        fields = '__all__'
class ApiKeySerializer(serializers.ModelSerializer):
    """Serializer for ApiKey model"""
    class Meta:
        model = ApiKey
        fields = '__all__'
        extra_kwargs = {'api_key': {'write_only': True}}
    """Serializer for PaymentRecord model"""
    subscription = SubscriptionSerializer(read_only=True)

    class Meta:
        model = PaymentRecord
        fields = '__all__'