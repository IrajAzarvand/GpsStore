import re

from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_subuser_of = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='subusers'
    )
    subscription_start = models.DateTimeField(null=True, blank=True)
    subscription_end = models.DateTimeField(null=True, blank=True)
    is_premium = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'

    def __str__(self):
        return self.username


def generate_unique_subuser_username(owner, requested_username: str) -> str:
    max_length = User._meta.get_field('username').max_length
    def normalize_username_part(value: str) -> str:
        v = (value or '').strip()
        v = re.sub(r"\s+", "_", v)
        v = re.sub(r"[^\w.@+-]+", "_", v, flags=re.UNICODE)
        v = v.strip('_')
        return v

    base = normalize_username_part(requested_username)
    prefix = normalize_username_part((getattr(owner, 'username', '') or '').strip()) or f"u{getattr(owner, 'id', '')}"
    sep = '__'

    candidate = f"{prefix}{sep}{base}" if base else f"{prefix}{sep}subuser"

    if len(candidate) > max_length:
        keep = max_length - len(prefix) - len(sep)
        if keep < 1:
            prefix = f"u{getattr(owner, 'id', '')}"
            keep = max_length - len(prefix) - len(sep)
        base_trunc = (base or 'subuser')[:max(1, keep)]
        candidate = f"{prefix}{sep}{base_trunc}"

    if not User.objects.filter(username=candidate).exists():
        return candidate

    i = 2
    while True:
        suffix = f"_{i}"
        trimmed = candidate
        if len(trimmed) + len(suffix) > max_length:
            trimmed = trimmed[:max_length - len(suffix)]
        final = f"{trimmed}{suffix}"
        if not User.objects.filter(username=final).exists():
            return final
        i += 1


class UserDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_devices')
    device = models.ForeignKey('gps_devices.Device', on_delete=models.CASCADE, related_name='device_users')
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='assigned_devices'
    )
    is_owner = models.BooleanField(default=False)
    can_view = models.BooleanField(default=True)
    can_control = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'دسترسی کاربر به دستگاه'
        verbose_name_plural = 'دسترسی‌های کاربران به دستگاه‌ها'
        unique_together = ['user', 'device']

    def __str__(self):
        return f"{self.user.username} - {self.device.name}"
