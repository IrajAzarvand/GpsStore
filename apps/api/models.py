from django.db import models


class ApiKey(models.Model):
    api_key = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    rate_limit_per_minute = models.IntegerField(default=60)
    allowed_ips = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'کلید API'
        verbose_name_plural = 'کلیدهای API'

    def __str__(self):
        return f"{self.api_key[:20]}... - {self.description or 'بدون توضیح'}"
