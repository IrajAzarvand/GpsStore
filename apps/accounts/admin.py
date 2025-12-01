from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserDevice

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_premium')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'is_premium')
    fieldsets = UserAdmin.fieldsets + (
        ('اطلاعات تکمیلی', {'fields': ('phone', 'address', 'is_subuser_of', 'subscription_start', 'subscription_end', 'is_premium')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('اطلاعات تکمیلی', {'fields': ('phone', 'address', 'is_subuser_of', 'is_premium')}),
    )

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device', 'is_owner', 'can_view', 'can_control', 'is_active')
    list_filter = ('is_owner', 'can_view', 'can_control', 'is_active')
    search_fields = ('user__username', 'device__name', 'device__imei')
