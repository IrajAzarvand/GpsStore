from django.db import models
from django.contrib.auth.models import User


class Log(models.Model):
    """
    System logs for debugging
    """
    LOG_LEVELS = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]

    level = models.CharField(max_length=10, choices=LOG_LEVELS, default='INFO')
    message = models.TextField()
    module = models.CharField(max_length=100, blank=True)
    function = models.CharField(max_length=100, blank=True)
    line_number = models.BigIntegerField(null=True, blank=True)
    process_id = models.BigIntegerField(null=True, blank=True)
    thread_id = models.BigIntegerField(null=True, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.level} {self.created_at} {self.module}: {self.message[:50]}"

    class Meta:
        verbose_name = 'Admin User Notification'
        verbose_name_plural = 'Admin User Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['level']),
            models.Index(fields=['module']),
        ]


class AdminNotification(models.Model):
    """
    Notifications for admin users
    """
    NOTIFICATION_TYPES = [
        ('order', 'سفارش جدید'),
        ('payment', 'پرداخت'),
        ('device', 'دستگاه'),
        ('alert', 'هشدار'),
        ('system', 'سیستم'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='admin_notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='system')
    is_read = models.BooleanField(default=False)
    action_url = models.URLField(blank=True, null=True)
    metadata = models.JSONField(default=dict, help_text="Additional data for the notification")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.user.username}"

    def mark_as_read(self):
        """Mark notification as read"""
        self.is_read = True
        self.save()

    class Meta:
        verbose_name = 'Admin Notification'
        verbose_name_plural = 'Admin Notifications'
        ordering = ['-created_at']


class SystemSetting(models.Model):
    """
    System-wide settings
    """
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    is_public = models.BooleanField(default=False, help_text="Can be accessed via API")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.key

    class Meta:
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'
        ordering = ['key']
