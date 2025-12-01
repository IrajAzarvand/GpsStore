from django.urls import path
from . import views

app_name = 'gps_devices'

urlpatterns = [
    # path('', views.index, name='index'),
    path('map/', views.map_v2, name='map_v2'),
]