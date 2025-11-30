from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.gps_devices.models import Device


class LocationData(models.Model):
    """
    GPS location data points from devices
    """
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='location_data')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    altitude = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, help_text="Altitude in meters")
    speed = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Speed in km/h")
    heading = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Heading in degrees")
    accuracy = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True, help_text="GPS accuracy in meters")

    # Device status
    battery_level = models.PositiveIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])
    signal_strength = models.PositiveIntegerField(null=True, blank=True, validators=[MaxValueValidator(100)])

    # Additional data
    raw_data = models.JSONField(default=dict, help_text="Raw GPS data from device")
    address = models.CharField(max_length=255, blank=True, help_text="Reverse geocoded address")

    timestamp = models.DateTimeField(help_text="When the location was recorded")
    received_at = models.DateTimeField(auto_now_add=True, help_text="When data was received by server")

    def __str__(self):
        return f"{self.device.name} at ({self.latitude}, {self.longitude})"

    class Meta:
        verbose_name = 'Location Data'
        verbose_name_plural = 'Location Data'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device', '-timestamp']),
            models.Index(fields=['latitude', 'longitude']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['device', 'timestamp']),
        ]


class Geofence(models.Model):
    """
    Geographical boundaries for alerts
    """
    SHAPE_CHOICES = [
        ('circle', 'Circle'),
        ('polygon', 'Polygon'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='geofences')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    shape = models.CharField(max_length=10, choices=SHAPE_CHOICES, default='circle')

    # For circle geofences
    center_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    center_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    radius = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, help_text="Radius in meters")

    # For polygon geofences (stored as JSON)
    polygon_points = models.JSONField(default=list, help_text="List of [lat, lng] points for polygon")

    # Alert settings
    alert_on_enter = models.BooleanField(default=True)
    alert_on_exit = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.shape})"

    def contains_point(self, lat, lng):
        """Check if a point is inside this geofence"""
        if self.shape == 'circle':
            return self._point_in_circle(lat, lng)
        elif self.shape == 'polygon':
            return self._point_in_polygon(lat, lng)
        return False

    def _point_in_circle(self, lat, lng):
        """Check if point is inside circle"""
        if not all([self.center_lat, self.center_lng, self.radius]):
            return False

        # Haversine formula for distance calculation
        import math
        R = 6371000  # Earth radius in meters

        lat1, lng1 = math.radians(float(self.center_lat)), math.radians(float(self.center_lng))
        lat2, lng2 = math.radians(float(lat)), math.radians(float(lng))

        dlat = lat2 - lat1
        dlng = lng2 - lng1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        distance = R * c

        return distance <= float(self.radius)

    def _point_in_polygon(self, lat, lng):
        """Check if point is inside polygon using ray casting algorithm"""
        if not self.polygon_points:
            return False

        # Ray casting algorithm
        n = len(self.polygon_points)
        inside = False

        p1x, p1y = self.polygon_points[0]
        for i in range(1, n + 1):
            p2x, p2y = self.polygon_points[i % n]
            if lat > min(p1y, p2y):
                if lat <= max(p1y, p2y):
                    if lng <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (lat - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or lng <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    class Meta:
        verbose_name = 'Geofence'
        verbose_name_plural = 'Geofences'
        ordering = ['-created_at']


class Alert(models.Model):
    """
    Alerts triggered by GPS events
    """
    ALERT_TYPES = [
        ('geofence_enter', 'ورود به منطقه محدود'),
        ('geofence_exit', 'خروج از منطقه محدود'),
        ('low_battery', 'باتری کم'),
        ('device_offline', 'دستگاه آفلاین'),
        ('sos_button', 'دکمه SOS'),
        ('speed_limit', 'تجاوز از سرعت مجاز'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    location_data = models.ForeignKey(LocationData, on_delete=models.SET_NULL, null=True, blank=True)

    # Alert metadata
    severity = models.CharField(max_length=10, choices=[('low', 'کم'), ('medium', 'متوسط'), ('high', 'زیاد'), ('critical', 'بحرانی')], default='medium')
    is_read = models.BooleanField(default=False)
    is_resolved = models.BooleanField(default=False)

    # Notification settings
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    push_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.device.name}: {self.get_alert_type_display()}"

    def resolve(self):
        """Mark alert as resolved"""
        from django.utils import timezone
        self.is_resolved = True
        self.resolved_at = timezone.now()
        self.save()

    class Meta:
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['device', '-created_at']),
            models.Index(fields=['is_read', 'is_resolved']),
            models.Index(fields=['alert_type']),
            models.Index(fields=['severity']),
        ]
