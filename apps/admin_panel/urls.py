from django.urls import path

from . import views

urlpatterns = [
    path('backup/', views.backup_view, name='backup'),
    path('restore/', views.restore_view, name='restore'),
    path('logs/', views.logs_view, name='logs'),
]