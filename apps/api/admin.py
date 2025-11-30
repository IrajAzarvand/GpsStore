from django.contrib import admin
from .models import APIKey, APILog, DeviceToken, Webhook


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'key_type', 'is_active', 'last_used_at', 'created_at')
    list_filter = ('key_type', 'is_active', 'created_at')
    search_fields = ('user__username', 'name', 'api_key')
    readonly_fields = ('api_key', 'api_secret', 'created_at', 'last_used_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'key_type', 'is_active')
        }),
        ('API Credentials', {
            'fields': ('api_key', 'api_secret'),
            'classes': ('collapse',)
        }),
        ('Permissions', {
            'fields': ('can_read_devices', 'can_write_devices', 'can_read_tracking', 'can_write_tracking', 'can_manage_geofences')
        }),
        ('Rate Limiting', {
            'fields': ('rate_limit_per_hour', 'rate_limit_per_day')
        }),
        ('Expiration', {
            'fields': ('expires_at',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_used_at'),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # API keys should be generated programmatically
        return False


@admin.register(APILog)
class APILogAdmin(admin.ModelAdmin):
    list_display = ('method', 'endpoint', 'status_code', 'ip_address', 'duration_ms', 'created_at')
    list_filter = ('method', 'status_code', 'log_type', 'created_at')
    search_fields = ('endpoint', 'ip_address', 'api_key__api_key')
    readonly_fields = ('created_at', 'request_data', 'response_data')

    fieldsets = (
        ('Request Information', {
            'fields': ('api_key', 'user', 'method', 'endpoint', 'ip_address', 'user_agent')
        }),
        ('Response Information', {
            'fields': ('status_code', 'response_size', 'duration_ms', 'log_type')
        }),
        ('Data', {
            'fields': ('message', 'request_data', 'response_data'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )

    def has_add_permission(self, request):
        # API logs are created automatically
        return False


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'device_id', 'token_type', 'is_active', 'last_used_at', 'created_at')
    list_filter = ('token_type', 'is_active', 'created_at')
    search_fields = ('user__username', 'device_id', 'device_model')
    readonly_fields = ('created_at', 'updated_at', 'last_used_at')

    fieldsets = (
        ('Device Information', {
            'fields': ('user', 'device_id', 'token_type', 'is_active')
        }),
        ('Token', {
            'fields': ('token',),
            'classes': ('collapse',)
        }),
        ('Device Details', {
            'fields': ('device_model', 'os_version', 'app_version')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'last_used_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Webhook)
class WebhookAdmin(admin.ModelAdmin):
    list_display = ('user', 'name', 'webhook_type', 'url', 'is_active', 'last_triggered_at', 'created_at')
    list_filter = ('webhook_type', 'is_active', 'created_at')
    search_fields = ('user__username', 'name', 'url')
    readonly_fields = ('created_at', 'last_triggered_at')

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'name', 'webhook_type', 'is_active')
        }),
        ('Configuration', {
            'fields': ('url', 'secret', 'headers', 'retry_count', 'timeout_seconds')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'last_triggered_at'),
            'classes': ('collapse',)
        }),
    )
