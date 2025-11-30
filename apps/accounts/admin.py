from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Address


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    verbose_name = 'Address'
    verbose_name_plural = 'Addresses'


class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline, AddressInline)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_phone_number')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'profile__is_verified')

    def get_phone_number(self, obj):
        return obj.profile.phone_number if hasattr(obj, 'profile') else '-'
    get_phone_number.short_description = 'Phone Number'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone_number', 'is_verified', 'created_at')
    list_filter = ('is_verified', 'created_at')
    search_fields = ('user__username', 'user__email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'address_type', 'city', 'is_default', 'created_at')
    list_filter = ('address_type', 'is_default', 'city', 'country')
    search_fields = ('user__username', 'street_address', 'city', 'postal_code')


# Unregister the default User admin and register our custom one
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
