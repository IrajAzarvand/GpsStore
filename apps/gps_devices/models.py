from django.db import models
from django.conf import settings

class State(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Model(models.Model):
    PROTOCOL_CHOICES = [
        ('TCP', 'TCP'),
        ('UDP', 'UDP'),
        ('HTTP', 'HTTP'),
        ('MQTT', 'MQTT'),
    ]
    
    model_name = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=100)
    protocol_type = models.CharField(max_length=20, choices=PROTOCOL_CHOICES)
    default_config = models.JSONField(default=dict, blank=True)
    image_url = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.manufacturer} {self.model_name}"


class Device(models.Model):
    STATUS_CHOICES = [
        ('active', 'فعال'),
        ('inactive', 'غیرفعال'),
        ('maintenance', 'در تعمیر'),
    ]
    
    imei = models.CharField(max_length=20, unique=True)
    sim_no = models.CharField(max_length=20, blank=True, null=True)
    model = models.ForeignKey(Model, on_delete=models.PROTECT, related_name='devices')
    driver_name = models.CharField(max_length=100, blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_devices')
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    consecutive_count = models.JSONField(default=dict, blank=True, help_text='Tracks consecutive occurrences of packet types/states')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.imei})"


class LocationData(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='locations')
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # زمان اعلام شده توسط دستگاه (Device Time)
    timestamp = models.DateTimeField(null=True, blank=True, db_index=True, help_text='زمان واقعی گزارش شده توسط دستگاه')

    
    # فیلدهای Map Matching
    original_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, help_text='مختصات اصلی دریافتی از GPS')
    original_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, help_text='مختصات اصلی دریافتی از GPS')
    is_map_matched = models.BooleanField(default=False, help_text='آیا این نقطه Map Match شده است؟')
    matched_geometry = models.TextField(blank=True, null=True, help_text='Encoded Polyline دریافتی از API نشان')
    
    speed = models.FloatField(default=0)
    heading = models.FloatField(default=0)
    altitude = models.FloatField(default=0)
    accuracy = models.FloatField(default=0)
    satellites = models.IntegerField(default=0, null=True)
    battery_level = models.IntegerField(default=0, null=True, blank=True)
    signal_strength = models.IntegerField(default=0, null=True)
    gsm_operator = models.CharField(max_length=50, blank=True, null=True)
    mcc = models.IntegerField(null=True, default=None)
    mnc = models.IntegerField(null=True, default=None)
    lac = models.IntegerField(null=True, default=None)
    cid = models.IntegerField(null=True, default=None)
    packet_type = models.CharField(max_length=20, blank=True, null=True, help_text='Type of packet (V1, HB, SOS, etc.)')
    location_source = models.CharField(max_length=20, default='GPS', help_text='Source of location data (GPS, LBS, etc.)')
    is_alarm = models.BooleanField(default=False, help_text='True if this location is an alarm/SOS')
    alarm_type = models.CharField(max_length=50, null=True, blank=True, help_text='Type of alarm (SOS, Overspeed, etc.)')
    raw_data = models.TextField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_valid = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'موقعیت مکانی'
        verbose_name_plural = 'موقعیت‌های مکانی'

    def __str__(self):
        return f"{self.device.name} - {self.created_at}"


class DeviceState(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='states')
    state = models.ForeignKey(State, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
    location_data = models.ForeignKey(LocationData, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'وضعیت دستگاه'
        verbose_name_plural = 'وضعیت‌های دستگاه'

    def __str__(self):
        return f"{self.device.name} - {self.state.name} - {self.timestamp}"


class RawGpsData(models.Model):
    STATUS_CHOICES = [
        ('pending', 'در انتظار'),
        ('processed', 'پردازش شده'),
        ('rejected', 'رد شده'),
        ('blocked', 'مسدود شده'),
    ]
    
    raw_data = models.TextField()
    ip_address = models.GenericIPAddressField()
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name='raw_data')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'داده خام GPS'
        verbose_name_plural = 'داده‌های خام GPS'


    def __str__(self):
        return f"{self.ip_address} - {self.status} - {self.created_at}"

class MaliciousPattern(models.Model):
    """
    الگوهای مخرب شناسایی شده برای فیلتر کردن داده‌های ناخواسته
    """
    pattern = models.TextField(unique=True, help_text="الگوی مخرب (می‌تواند متن یا hex باشد)")
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="آدرس IP مخرب (اختیاری)")
    pattern_type = models.CharField(
        max_length=20,
        choices=[
            ('exact', 'تطابق دقیق'),
            ('startswith', 'شروع با'),
            ('contains', 'شامل'),
            ('regex', 'عبارت منظم')
        ],
        default='contains',
        help_text="نوع تطابق"
    )
    description = models.CharField(max_length=255, blank=True, help_text="توضیحات الگو")
    is_active = models.BooleanField(default=True, help_text="فعال/غیرفعال")
    created_at = models.DateTimeField(auto_now_add=True)
    hit_count = models.IntegerField(default=0, help_text="تعداد دفعات تشخیص")
    last_hit = models.DateTimeField(null=True, blank=True, help_text="آخرین بار تشخیص")

    class Meta:
        db_table = 'malicious_patterns'
        verbose_name = 'الگوی مخرب'
        verbose_name_plural = 'الگوهای مخرب'
        ordering = ['-created_at']
        unique_together = [['pattern', 'ip_address']]  # ترکیب pattern + IP باید یکتا باشد

    def __str__(self):
        return f"{self.pattern_type}: {self.pattern[:50]}"