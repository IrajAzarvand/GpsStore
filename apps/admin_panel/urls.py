from django.urls import path
from . import views

urlpatterns = [
    path('', views.BackupRestoreView.as_view(), name='backup_restore'),
    path('devices/assign-owner/', views.AssignDeviceOwnerView.as_view(), name='admin_assign_device_owner'),
]