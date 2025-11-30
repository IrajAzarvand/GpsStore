from django.urls import path
from . import views

app_name = 'tracking'

urlpatterns = [
    # Main tracking dashboard
    path('', views.tracking_dashboard, name='tracking_dashboard'),

    # Device-specific tracking
    path('device/<int:device_id>/', views.device_tracking, name='device_tracking'),
    path('device/<int:device_id>/real-time/', views.real_time_tracking, name='real_time_tracking'),

    # API endpoints for location data
    path('api/device/<int:device_id>/location/', views.update_device_location, name='update_device_location'),
    path('api/device/<int:device_id>/locations/', views.get_device_locations, name='get_device_locations'),

    # Geofence management
    path('geofences/', views.geofence_list, name='geofence_list'),
    path('geofences/create/', views.geofence_create, name='geofence_create'),
    path('geofences/<int:geofence_id>/', views.geofence_detail, name='geofence_detail'),

    # Alert management
    path('alerts/', views.alert_list, name='alert_list'),
    path('api/alerts/<int:alert_id>/read/', views.mark_alert_read, name='mark_alert_read'),
    path('api/alerts/<int:alert_id>/resolve/', views.resolve_alert, name='resolve_alert'),
]