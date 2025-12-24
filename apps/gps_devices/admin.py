from django.contrib import admin
from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import path, reverse
from django.utils.html import format_html
from django.db import transaction

from apps.accounts.models import UserDevice
from .models import State, Model, Device, LocationData, DeviceState, RawGpsData, MaliciousPattern
from .decoders.HQ_Decoder import HQFullDecoder

import logging

logger = logging.getLogger(__name__)

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(Model)
class ModelAdmin(admin.ModelAdmin):
    list_display = ('manufacturer', 'model_name', 'protocol_type')
    list_filter = ('protocol_type',)
    search_fields = ('manufacturer', 'model_name')

@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ('name', 'imei', 'model', 'owner', 'assigned_subuser', 'assigned_by', 'expires_at', 'status', 'created_at')
    list_filter = ('status', 'model')
    search_fields = ('name', 'imei', 'owner__username', 'assigned_subuser__username', 'assigned_by__username')
    readonly_fields = ('assigned_by',)
    
    def save_model(self, request, obj, form, change):
        # Set assigned_by to the current user if it's not set or if it's a new device
        if not obj.assigned_by_id:
            obj.assigned_by = request.user

        with transaction.atomic():
            super().save_model(request, obj, form, change)
            self._sync_userdevice_from_device(request, obj)

    def _sync_userdevice_from_device(self, request, device: Device):
        if device.owner_id is None:
            UserDevice.objects.filter(device=device, is_active=True).update(is_active=False)
            return

        keep_ids = []

        owner_row, _ = UserDevice.objects.update_or_create(
            user_id=device.owner_id,
            device=device,
            defaults={
                'assigned_by': request.user,
                'is_owner': True,
                'can_view': True,
                'can_control': True,
                'is_active': True,
            },
        )
        keep_ids.append(owner_row.id)

        if device.assigned_subuser_id:
            sub_row, _ = UserDevice.objects.update_or_create(
                user_id=device.assigned_subuser_id,
                device=device,
                defaults={
                    'assigned_by': request.user,
                    'is_owner': False,
                    'can_view': True,
                    'can_control': False,
                    'is_active': True,
                },
            )
            keep_ids.append(sub_row.id)

        UserDevice.objects.filter(device=device, is_active=True).exclude(id__in=keep_ids).update(is_active=False)

@admin.register(LocationData)
class LocationDataAdmin(admin.ModelAdmin):
    list_display = ('device', 'latitude', 'longitude', 'speed', 'heading', 'is_alarm', 'alarm_type', 'created_at')
    list_filter = ('created_at', 'is_valid', 'is_alarm', 'alarm_type')
    search_fields = ('device__name', 'device__imei')
    readonly_fields = ('created_at',)

@admin.register(DeviceState)
class DeviceStateAdmin(admin.ModelAdmin):
    list_display = ('get_device_name', 'get_device_imei', 'state', 'timestamp')
    list_filter = ('state', 'timestamp', 'device')
    search_fields = ('device__name', 'device__imei')

    @admin.display(ordering='device__name', description='Device Name')
    def get_device_name(self, obj):
        return obj.device.name

    @admin.display(ordering='device__imei', description='IMEI')
    def get_device_imei(self, obj):
        return obj.device.imei

@admin.register(RawGpsData)
class RawGpsDataAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'device', 'status', 'created_at', 'register_device_link')
    list_filter = ('status', 'created_at')
    search_fields = ('ip_address', 'raw_data')
    readonly_fields = ('created_at',)
    actions = ['mark_as_malicious_pattern']

    def register_device_link(self, obj):
        if obj.device_id:
            return '-'
        url = reverse('admin:gps_devices_rawgpsdata_register_device', args=[obj.pk])
        return format_html('<a class="btn btn-primary" href="{}">Register Device</a>', url)

    register_device_link.short_description = 'Register Device'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:raw_id>/register-device/',
                self.admin_site.admin_view(self.register_device_view),
                name='gps_devices_rawgpsdata_register_device',
            ),
        ]
        return custom_urls + urls

    class RegisterDeviceForm(forms.Form):
        imei = forms.CharField(label='IMEI', disabled=True, required=False)
        name = forms.CharField(label='Name', required=True)
        model = forms.ModelChoiceField(label='Model', queryset=Model.objects.all(), required=True)

    def _decode_rawgps(self, raw_packet: str):
        decoder = HQFullDecoder()
        decoded = decoder.decode(raw_packet)

        device_id = decoded.get('imei') or decoded.get('device_id')
        parsed = {
            'device_id': device_id,
            'latitude': decoded.get('latitude'),
            'longitude': decoded.get('longitude'),
            'speed': decoded.get('speed'),
            'timestamp': decoded.get('timestamp'),
        }

        voltage_v = decoded.get('voltage_v')
        if voltage_v is not None:
            parsed['voltage'] = voltage_v

        temperature = decoded.get('temperature')
        if temperature is not None:
            parsed['temperature'] = temperature

        return parsed

    def register_device_view(self, request, raw_id):
        raw_obj = get_object_or_404(RawGpsData, pk=raw_id)

        parsed_data = {}
        try:
            parsed_data = self._decode_rawgps(raw_obj.raw_data)
        except Exception as e:
            messages.error(request, f'Failed to decode raw gps: {e}')

        imei = parsed_data.get('device_id')
        if imei:
            existing = Device.objects.filter(imei=imei).first()
            if existing and raw_obj.device_id != existing.id:
                raw_obj.device = existing
                raw_obj.save(update_fields=['device', 'updated_at'])
                messages.info(request, 'Device already exists; linked to raw record.')
                return redirect('admin:gps_devices_rawgpsdata_changelist')

        if request.method == 'POST':
            form = self.RegisterDeviceForm(request.POST)
            if form.is_valid():
                if not imei:
                    messages.error(request, 'IMEI not found in decoded packet.')
                else:
                    device, created = Device.objects.get_or_create(
                        imei=imei,
                        defaults={
                            'name': form.cleaned_data['name'],
                            'model': form.cleaned_data['model'],
                            'status': 'active',
                        },
                    )

                    if not created:
                        device.name = form.cleaned_data['name']
                        device.model = form.cleaned_data['model']
                        device.save(update_fields=['name', 'model', 'updated_at'])

                    raw_obj.device = device
                    raw_obj.save(update_fields=['device', 'updated_at'])
                    messages.success(request, 'Device registered successfully.')
                    return redirect('admin:gps_devices_rawgpsdata_changelist')
        else:
            initial_name = None
            if imei:
                initial_name = f'Device {imei}'
            form = self.RegisterDeviceForm(initial={'imei': imei, 'name': initial_name})

        context = {
            **self.admin_site.each_context(request),
            'title': 'Register Device',
            'form': form,
            'parsed_data': parsed_data,
            'raw_data': raw_obj,
        }
        return render(request, 'admin/gps_devices/device/register_device.html', context)

    def mark_as_malicious_pattern(self, request, queryset):
        """
        اضافه کردن داده‌های انتخاب شده به الگوهای مخرب و حذف موارد مشابه
        """
        from apps.gps_devices.models import MaliciousPattern

        added_count = 0
        deleted_count = 0

        for raw_data in queryset:
            ip = raw_data.ip_address
            pattern_text = raw_data.raw_data

            # Check if pattern already exists
            if MaliciousPattern.objects.filter(pattern=pattern_text).exists():
                # Delete all RawGpsData records with this IP
                deleted, _ = RawGpsData.objects.filter(ip_address=ip).delete()
                deleted_count += deleted
            else:
                # Add the pattern
                MaliciousPattern.objects.create(
                    pattern=pattern_text,
                    ip_address=ip,
                    pattern_type='contains',
                    description=f'Added from RawGpsData - IP: {ip}',
                    is_active=True
                )
                added_count += 1

        # نمایش پیام به کاربر
        if added_count > 0:
            self.message_user(
                request,
                f'{added_count} الگوی مخرب اضافه شد.'
            )
        if deleted_count > 0:
            self.message_user(
                request,
                f'{deleted_count} رکورد مشابه حذف شد زیرا الگو وجود داشت.',
                level='INFO'
            )


    mark_as_malicious_pattern.short_description = "افزودن به الگوهای مخرب و حذف موارد مشابه"


@admin.register(MaliciousPattern)
class MaliciousPatternAdmin(admin.ModelAdmin):
    list_display = ('pattern_type', 'ip_address', 'pattern_preview', 'description', 'is_active', 'hit_count', 'last_hit', 'created_at')
    list_filter = ('pattern_type', 'is_active', 'created_at', 'ip_address')
    search_fields = ('pattern', 'description', 'ip_address')
    readonly_fields = ('hit_count', 'last_hit', 'created_at')
    
    def pattern_preview(self, obj):
        return obj.pattern[:100] + '...' if len(obj.pattern) > 100 else obj.pattern
    pattern_preview.short_description = 'الگو'