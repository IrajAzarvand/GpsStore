from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.admin.widgets import FilteredSelectMultiple
from django.db import transaction
from django.db.models import Q

from apps.gps_devices.models import Device
from .models import User, UserDevice, generate_unique_subuser_username


class AdminUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        owner = self.cleaned_data.get('is_subuser_of')
        if owner:
            return generate_unique_subuser_username(owner, username)
        return username


class AdminUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if self.instance and self.instance.pk:
            if username == (self.instance.username or ''):
                return username

        owner = self.cleaned_data.get('is_subuser_of') or getattr(self.instance, 'is_subuser_of', None)
        if owner:
            return generate_unique_subuser_username(owner, username)
        return username

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_premium')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'groups', 'is_premium')
    add_form = AdminUserCreationForm
    form = AdminUserChangeForm
    fieldsets = UserAdmin.fieldsets + (
        ('اطلاعات تکمیلی', {'fields': ('phone', 'address', 'is_subuser_of', 'subscription_start', 'subscription_end', 'is_premium')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('اطلاعات تکمیلی', {'fields': ('phone', 'address', 'is_subuser_of', 'is_premium')}),
    )


class UserDeviceAddForm(forms.ModelForm):
    devices = forms.ModelMultipleChoiceField(
        queryset=Device.objects.filter(
            Q(owner__isnull=True) | Q(owner__is_superuser=True) | Q(owner__is_staff=True),
            assigned_subuser__isnull=True,
        ).exclude(
            device_users__is_active=True,
            device_users__user__is_superuser=False,
            device_users__user__is_staff=False,
        ).distinct(),
        required=True,
        widget=FilteredSelectMultiple(verbose_name='Device', is_stacked=False),
    )

    class Meta:
        model = UserDevice
        fields = ('user', 'devices', 'is_owner', 'can_view', 'can_control', 'notes', 'expires_at', 'is_active')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = Device.objects.filter(
            Q(owner__isnull=True) | Q(owner__is_superuser=True) | Q(owner__is_staff=True),
            assigned_subuser__isnull=True,
        )
        qs = qs.exclude(
            device_users__is_active=True,
            device_users__user__is_superuser=False,
            device_users__user__is_staff=False,
        )
        self.fields['devices'].queryset = qs.distinct()


class UserDeviceChangeForm(forms.ModelForm):
    class Meta:
        model = UserDevice
        fields = ('user', 'device', 'assigned_by', 'is_owner', 'can_view', 'can_control', 'notes', 'expires_at', 'is_active')

@admin.register(UserDevice)
class UserDeviceAdmin(admin.ModelAdmin):
    list_display = ('user', 'device', 'is_owner', 'can_view', 'can_control', 'is_active')
    list_filter = ('is_owner', 'can_view', 'can_control', 'is_active')
    search_fields = ('user__username', 'device__name', 'device__imei')

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        ro.append('assigned_by')
        return ro

    def get_form(self, request, obj=None, change=False, **kwargs):
        if obj is None:
            kwargs['form'] = UserDeviceAddForm
        else:
            kwargs['form'] = UserDeviceChangeForm
        return super().get_form(request, obj, change=change, **kwargs)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'device' and getattr(getattr(request, 'resolver_match', None), 'url_name', '').endswith('_add'):
            qs = Device.objects.all()
            qs = qs.exclude(
                Q(assigned_subuser__isnull=False)
                | Q(
                    device_users__is_active=True,
                    device_users__user__is_superuser=False,
                    device_users__user__is_staff=False,
                )
                | (
                    Q(owner__isnull=False)
                    & Q(owner__is_superuser=False)
                    & Q(owner__is_staff=False)
                )
            )
            kwargs['queryset'] = qs.distinct()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not getattr(obj, 'assigned_by_id', None):
            obj.assigned_by = request.user

        devices = form.cleaned_data.get('devices') if hasattr(form, 'cleaned_data') else None

        if not change and devices is not None:
            devices = list(devices)
            if not devices:
                return

            with transaction.atomic():
                first_device = devices[0]
                row, _created = UserDevice.objects.update_or_create(
                    user=obj.user,
                    device=first_device,
                    defaults={
                        'assigned_by': request.user,
                        'is_owner': obj.is_owner,
                        'can_view': obj.can_view,
                        'can_control': obj.can_control,
                        'notes': obj.notes,
                        'expires_at': obj.expires_at,
                        'is_active': obj.is_active,
                    }
                )

                obj.pk = row.pk
                obj.device = row.device
                obj._state.adding = False

                self._sync_device_from_userdevice(request, row)

                for device in devices[1:]:
                    row, _created = UserDevice.objects.update_or_create(
                        user=obj.user,
                        device=device,
                        defaults={
                            'assigned_by': request.user,
                            'is_owner': obj.is_owner,
                            'can_view': obj.can_view,
                            'can_control': obj.can_control,
                            'notes': obj.notes,
                            'expires_at': obj.expires_at,
                            'is_active': obj.is_active,
                        }
                    )
                    self._sync_device_from_userdevice(request, row)
            return

        super().save_model(request, obj, form, change)
        self._sync_device_from_userdevice(request, obj)

    def _sync_device_from_userdevice(self, request, user_device: UserDevice):
        device = user_device.device
        user = user_device.user

        has_access = bool(user_device.is_active and (user_device.can_view or user_device.is_owner or user_device.can_control))

        if not has_access:
            if getattr(user, 'is_subuser_of_id', None):
                if device.assigned_subuser_id == user.id:
                    device.assigned_subuser = None
                    device.assigned_by = request.user
                    device.save(update_fields=['assigned_subuser', 'assigned_by', 'updated_at'])
            else:
                if device.owner_id == user.id:
                    device.owner = None
                    device.assigned_subuser = None
                    device.assigned_by = request.user
                    device.save(update_fields=['owner', 'assigned_subuser', 'assigned_by', 'updated_at'])
            return

        if getattr(user, 'is_subuser_of_id', None):
            device.owner_id = user.is_subuser_of_id
            device.assigned_subuser_id = user.id
        else:
            device.owner_id = user.id
            device.assigned_subuser_id = None

        device.assigned_by = request.user
        device.save(update_fields=['owner', 'assigned_subuser', 'assigned_by', 'updated_at'])

        UserDevice.objects.filter(device=device, is_active=True).exclude(id=user_device.id).update(is_active=False)
