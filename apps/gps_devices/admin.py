from django.contrib import admin
from .models import State, Model, Device, LocationData, DeviceState, RawGpsData, MaliciousPattern

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
    list_display = ('get_device_name', 'get_device_imei', 'state', 'timestamp')
    list_filter = ('state', 'timestamp', 'device')
    search_fields = ('device__name', 'device__imei')

    @admin.display(ordering='device__name', description='Device Name')
    def get_device_name(self, obj):
        return obj.device.name

    @admin.display(ordering='device__imei', description='IMEI')
    def get_device_imei(self, obj):
        return obj.device.imei

@admin.register(RawGpsData)
class RawGpsDataAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'device', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('ip_address', 'raw_data')
    readonly_fields = ('created_at',)
    actions = ['mark_as_malicious_pattern']
    
    def mark_as_malicious_pattern(self, request, queryset):
        """
        اضافه کردن داده‌های انتخاب شده به الگوهای مخرب
        """
        from apps.gps_devices.models import MaliciousPattern
        
        added_count = 0
        skipped_count = 0
        
        for raw_data in queryset:
            # بررسی اینکه آیا این الگو قبلاً وجود دارد
            if not MaliciousPattern.objects.filter(pattern=raw_data.raw_data).exists():
                MaliciousPattern.objects.create(
                    pattern=raw_data.raw_data,
                    pattern_type='contains',  # می‌توانید به 'contains' یا 'startswith' تغییر دهید
                    description=f'Added from RawGpsData - IP: {raw_data.ip_address}',
                    is_active=True
                )
                added_count += 1
            else:
                skipped_count += 1
        
        # نمایش پیام به کاربر
        if added_count > 0:
            self.message_user(
                request,
                f'{added_count} الگوی مخرب با موفقیت اضافه شد.'
            )
        if skipped_count > 0:
            self.message_user(
                request,
                f'{skipped_count} الگو قبلاً وجود داشت و نادیده گرفته شد.',
                level='WARNING'
            )
    
    mark_as_malicious_pattern.short_description = "افزودن به الگوهای مخرب"


@admin.register(MaliciousPattern)
class MaliciousPatternAdmin(admin.ModelAdmin):
    list_display = ('pattern_type', 'pattern_preview', 'description', 'is_active', 'hit_count', 'last_hit', 'created_at')
    list_filter = ('pattern_type', 'is_active', 'created_at')
    search_fields = ('pattern', 'description')
    readonly_fields = ('hit_count', 'last_hit', 'created_at')
    
    def pattern_preview(self, obj):
        return obj.pattern[:100] + '...' if len(obj.pattern) > 100 else obj.pattern
    pattern_preview.short_description = 'الگو'
