from django.urls import path
from . import views

app_name = 'gps_devices'

urlpatterns = [
    path('receive/', views.receive_gps_data, name='receive_gps_data'),
    path('register-device/<int:raw_data_id>/', views.register_device, name='register_device'),
    path('map/', views.device_map, name='device_map'),
    path('api/devices/', views.device_markers_api, name='gps_devices_api'),
    path('api/markers/', views.device_markers_api, name='device_markers_api'),
]