from django.contrib import admin
from .models import State, Model, Device, LocationData, DeviceState, RawGpsData

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(Model)
class ModelAdmin(admin.ModelAdmin):
    list_display = ('manufacturer', 'model_name', 'protocol_type')
    list_filter = ('protocol_type',)
    search_fields = ('manufacturer', 'model_name')

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'imei', 'model', 'owner', 'status', 'created_at')
    list_filter = ('status', 'model')
    search_fields = ('name', 'imei', 'owner__username')

@admin.register(LocationData)
class LocationDataAdmin(admin.ModelAdmin):
    list_display = ('device', 'latitude', 'longitude', 'speed', 'is_alarm', 'alarm_type', 'created_at')
    list_filter = ('created_at', 'is_valid', 'is_alarm', 'alarm_type')
    search_fields = ('device__name', 'device__imei')
    readonly_fields = ('created_at',)

@admin.register(DeviceState)
class DeviceStateAdmin(admin.ModelAdmin):
    list_display = ('device', 'state', 'timestamp')
    list_filter = ('state', 'timestamp')
    search_fields = ('device__name',)

@admin.register(RawGpsData)
class RawGpsDataAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('ip_address', 'raw_data')
    readonly_fields = ('created_at',)

