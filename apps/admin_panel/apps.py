from django.apps import AppConfig


class AdminPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.admin_panel'
    app_name = 'admin_panel'
    verbose_name = 'پنل مدیریت'

