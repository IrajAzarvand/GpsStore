from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator


class APIKey(models.Model):
    """
    API keys for mobile applications and third-party integrations
    """
    KEY_TYPES = [
        ('mobile_android', 'اپ اندروید'),
        ('mobile_ios', 'اپ iOS'),
        ('web_app', 'اپلیکیشن وب'),
        ('third_party', 'Third Party'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_keys')
    name = models.CharField(max_length=100, help_text="Descriptive name for the API key")
    key_type = models.CharField(max_length=20, choices=KEY_TYPES, default='mobile_android')

    # API Key
    api_key = models.CharField(max_length=64, unique=True)
    api_secret = models.CharField(max_length=128, blank=True, help_text="For HMAC authentication")

    # Permissions
    can_read_devices = models.BooleanField(default=True)
    can_write_devices = models.BooleanField(default=False)
    can_read_tracking = models.BooleanField(default=True)
    can_write_tracking = models.BooleanField(default=False)
    can_manage_geofences = models.BooleanField(default=False)

    # Rate limiting
    rate_limit_per_hour = models.PositiveIntegerField(default=1000)
    rate_limit_per_day = models.PositiveIntegerField(default=10000)

    # Status
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.name} ({self.key_type})"

    def is_expired(self):
        """Check if API key has expired"""
        from django.utils import timezone
        return self.expires_at and timezone.now() > self.expires_at

    def can_access(self, permission):
        """Check if API key has specific permission"""
        permission_map = {
            'read_devices': self.can_read_devices,
            'write_devices': self.can_write_devices,
            'read_tracking': self.can_read_tracking,
            'write_tracking': self.can_write_tracking,
            'manage_geofences': self.can_manage_geofences,
        }
        return permission_map.get(permission, False)

    class Meta:
        verbose_name = 'API Key'
        verbose_name_plural = 'API Keys'
        ordering = ['-created_at']


class APILog(models.Model):
    """
    Logs for API requests and responses
    """
    LOG_TYPES = [
        ('request', 'درخواست'),
        ('response', 'پاسخ'),
        ('error', 'خطا'),
    ]

    api_key = models.ForeignKey(APIKey, on_delete=models.CASCADE, related_name='logs', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_logs', null=True, blank=True)

    # Request details
    method = models.CharField(max_length=10)
    endpoint = models.CharField(max_length=500)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)

    # Response details
    status_code = models.PositiveIntegerField()
    response_size = models.PositiveIntegerField(default=0, help_text="Response size in bytes")

    # Timing
    duration_ms = models.PositiveIntegerField(help_text="Request duration in milliseconds")

    # Log type and message
    log_type = models.CharField(max_length=10, choices=LOG_TYPES, default='request')
    message = models.TextField(blank=True)

    # Additional data
    request_data = models.JSONField(default=dict, help_text="Request payload (sanitized)")
    response_data = models.JSONField(default=dict, help_text="Response data (sanitized)")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.method} {self.endpoint} - {self.status_code}"

    class Meta:
        verbose_name = 'API Log'
        verbose_name_plural = 'API Logs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['api_key', '-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['endpoint', 'status_code']),
            models.Index(fields=['created_at']),
        ]


class DeviceToken(models.Model):
    """
    Push notification tokens for mobile devices
    """
    TOKEN_TYPES = [
        ('fcm', 'Firebase Cloud Messaging'),
        ('apns', 'Apple Push Notification Service'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    device_id = models.CharField(max_length=255, unique=True, help_text="Unique device identifier")
    token_type = models.CharField(max_length=10, choices=TOKEN_TYPES)
    token = models.TextField(help_text="Push notification token")

    # Device info
    device_model = models.CharField(max_length=100, blank=True)
    os_version = models.CharField(max_length=50, blank=True)
    app_version = models.CharField(max_length=20, blank=True)

    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.device_id}"

    class Meta:
        verbose_name = 'Device Token'
        verbose_name_plural = 'Device Tokens'
        ordering = ['-created_at']


class Webhook(models.Model):
    """
    Webhooks for real-time notifications
    """
    WEBHOOK_TYPES = [
        ('location_update', 'به‌روزرسانی موقعیت'),
        ('geofence_alert', 'هشدار منطقه محدود'),
        ('device_status', 'وضعیت دستگاه'),
        ('subscription_update', 'به‌روزرسانی اشتراک'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='webhooks')
    name = models.CharField(max_length=100)
    webhook_type = models.CharField(max_length=20, choices=WEBHOOK_TYPES)

    # Webhook configuration
    url = models.URLField(help_text="Webhook endpoint URL")
    secret = models.CharField(max_length=128, help_text="Webhook secret for HMAC verification")

    # Headers (JSON)
    headers = models.JSONField(default=dict, help_text="Custom headers to send with webhook")

    # Events to trigger
    is_active = models.BooleanField(default=True)
    retry_count = models.PositiveIntegerField(default=3)
    timeout_seconds = models.PositiveIntegerField(default=30)

    created_at = models.DateTimeField(auto_now_add=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    class Meta:
        verbose_name = 'Webhook'
        verbose_name_plural = 'Webhooks'
        ordering = ['-created_at']
