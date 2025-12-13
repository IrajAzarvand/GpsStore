from django.urls import path
from . import views

urlpatterns = [
    path('backups/', views.BackupRestoreView.as_view(), name='backup_restore'),
]