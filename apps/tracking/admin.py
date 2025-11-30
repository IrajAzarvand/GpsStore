from django.contrib import admin
from .models import LocationData, Geofence, Alert


@admin.register(LocationData)
class LocationDataAdmin(admin.ModelAdmin):
    list_display = ('device', 'latitude', 'longitude', 'timestamp', 'received_at', 'battery_level')
    list_filter = ('timestamp', 'received_at', 'device__device_type')
    search_fields = ('device__name', 'device__imei', 'device__device_id', 'address')
    readonly_fields = ('received_at',)

    fieldsets = (
        ('Device & Location', {
            'fields': ('device', 'latitude', 'longitude', 'altitude')
        }),
        ('Movement Data', {
            'fields': ('speed', 'heading', 'accuracy')
        }),
        ('Device Status', {
            'fields': ('battery_level', 'signal_strength')
        }),
        ('Additional Data', {
            'fields': ('raw_data', 'address'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('timestamp', 'received_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # Location data should be created automatically, not manually
        return False


@admin.register(Geofence)
class GeofenceAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'shape', 'is_active', 'alert_on_enter', 'alert_on_exit', 'created_at')
    list_filter = ('shape', 'is_active', 'alert_on_enter', 'alert_on_exit', 'created_at')
    search_fields = ('name', 'user__username', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'description', 'shape', 'is_active')
        }),
        ('Circle Settings', {
            'fields': ('center_lat', 'center_lng', 'radius'),
            'classes': ('collapse',)
        }),
        ('Polygon Settings', {
            'fields': ('polygon_points',),
            'classes': ('collapse',)
        }),
        ('Alert Settings', {
            'fields': ('alert_on_enter', 'alert_on_exit')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('device', 'alert_type', 'severity', 'is_read', 'is_resolved', 'created_at')
    list_filter = ('alert_type', 'severity', 'is_read', 'is_resolved', 'created_at')
    search_fields = ('device__name', 'device__imei', 'device__device_id', 'message')
    readonly_fields = ('created_at', 'resolved_at')

    fieldsets = (
        ('Alert Information', {
            'fields': ('device', 'alert_type', 'message', 'severity')
        }),
        ('Location & Status', {
            'fields': ('location_data', 'is_read', 'is_resolved', 'resolved_at')
        }),
        ('Notifications', {
            'fields': ('email_sent', 'sms_sent', 'push_sent'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    actions = ['mark_as_read', 'mark_as_resolved']

    def mark_as_read(self, request, queryset):
        queryset.update(is_read=True)
        self.message_user(request, f"{queryset.count()} alert(s) marked as read.")
    mark_as_read.short_description = "Mark selected alerts as read"

    def mark_as_resolved(self, request, queryset):
        for alert in queryset.filter(is_resolved=False):
            alert.resolve()
        self.message_user(request, f"{queryset.count()} alert(s) marked as resolved.")
    mark_as_resolved.short_description = "Mark selected alerts as resolved"
