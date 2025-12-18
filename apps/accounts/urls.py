from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('customer/', views.customer_dashboard, name='customer_dashboard'),
    path('subuser/dashboard/', views.subuser_dashboard, name='subuser_dashboard'),
    path('subuser/add/', views.subuser_add, name='subuser_add'),
    path('subuser/<int:pk>/edit/', views.subuser_edit, name='subuser_edit'),
    path('subuser/<int:pk>/delete/', views.subuser_delete, name='subuser_delete'),
    path('subuser/assign-devices/', views.assign_devices, name='assign_devices'),
    path('api/subuser/create/', views.api_subuser_create, name='api_subuser_create'),
]