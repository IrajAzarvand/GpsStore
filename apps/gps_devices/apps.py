from django.apps import AppConfig


class GpsDevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.gps_devices'
    verbose_name = 'دستگاه‌های GPS'

    def ready(self):
        import apps.gps_devices.signals
