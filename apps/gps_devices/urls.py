from django.urls import path
from . import views
app_name = 'gps_devices'
urlpatterns = [
    path('map/', views.map_v2, name='map_v2'),
    path('report/', views.report, name='report'),
    path('api/report/', views.get_device_report, name='get_device_report'),
]