from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication URLs
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),

    # Password reset URLs
    path('password-reset/', views.CustomPasswordResetView.as_view(), name='password_reset'),
    path('password-reset/done/', views.CustomPasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset/complete/', views.CustomPasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # User panel URLs
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('profile/', views.ProfileView.as_view(), name='profile'),

    # Address management
    path('addresses/', views.AddressListView.as_view(), name='addresses'),
    path('addresses/add/', views.AddressCreateView.as_view(), name='address_add'),
    path('addresses/<int:pk>/edit/', views.AddressUpdateView.as_view(), name='address_edit'),
    path('addresses/<int:pk>/delete/', views.address_delete_view, name='address_delete'),

    # Customer and Sub-user panels
    path('customer-dashboard/', views.CustomerDashboardView.as_view(), name='customer_dashboard'),
    path('subuser-dashboard/', views.SubUserDashboardView.as_view(), name='subuser_dashboard'),
    path('subusers/add/', views.SubUserCreateView.as_view(), name='subuser_add'),
    path('subusers/<int:pk>/edit/', views.SubUserUpdateView.as_view(), name='subuser_edit'),
    path('subusers/<int:pk>/delete/', views.subuser_delete_view, name='subuser_delete'),
    path('assign-devices/', views.assign_devices_view, name='assign_devices'),
]