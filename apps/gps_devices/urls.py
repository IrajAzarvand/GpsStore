from django.urls import path
from . import views
app_name = 'gps_devices'
urlpatterns = [
    path('map/', views.map_v2, name='device_map'),
    path('report/', views.report, name='report'),
    path('api/report/', views.get_device_report, name='get_device_report'),
    path('api/markers/', views.api_markers, name='api_markers'),
    path('api/map-match/', views.map_match_points, name='map_match_points'),
    path('api/assign-device-owner/', views.assign_device_owner, name='api_assign_device_owner'),
    path('api/assign-device-subuser/', views.assign_device_subuser, name='api_assign_device_subuser'),
]