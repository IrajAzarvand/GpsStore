from rest_framework import viewsets, permissions
from apps.gps_devices.models import Device, LocationData, get_visible_devices_queryset
from apps.accounts.models import User, UserDevice
from apps.api.models import ApiKey
from .serializers import (
    DeviceSerializer, LocationDataSerializer,
    UserSerializer, UserDeviceSerializer, ApiKeySerializer
)

class DeviceViewSet(viewsets.ModelViewSet):
    """ViewSet for Device model"""
    queryset = Device.objects.all()
    serializer_class = DeviceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        return get_visible_devices_queryset(user, only_active=False)

class LocationDataViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for LocationData model"""
    queryset = LocationData.objects.all()
    serializer_class = LocationDataSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return LocationData.objects.all()
        user_devices = get_visible_devices_queryset(user, only_active=False)
        return LocationData.objects.filter(device__in=user_devices)