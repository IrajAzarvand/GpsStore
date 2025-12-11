from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Device, LocationData
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core import serializers
from django.conf import settings
from datetime import datetime, timedelta
import json
import jdatetime

User = get_user_model()

@login_required
def map_v2(request):
    """
    نمایش نقشه با دستگاه‌های فعال
    """
    # Generate JWT token for WebSocket authentication
    refresh = RefreshToken.for_user(request.user)
    access_token = str(refresh.access_token)

    # Build hierarchical structure
    hierarchy = []

    if request.user.is_staff or request.user.is_superuser:
        # Admin sees all users and their devices
        # Get all root users (users without parent)
        root_users = User.objects.filter(is_subuser_of__isnull=True, is_active=True)

        for user in root_users:
            hierarchy.append(build_user_tree(user, is_admin=True))
    else:
        # Regular user sees only themselves and their subusers
        hierarchy.append(build_user_tree(request.user, is_admin=False))

    # Collect all devices for JSON data
    if request.user.is_staff or request.user.is_superuser:
        devices = Device.objects.filter(status='active').select_related('model')
    else:
        # Get devices for current user and all subusers
        user_ids = get_all_subuser_ids(request.user)
        devices = Device.objects.filter(
            owner_id__in=user_ids,
            status='active'
        ).select_related('model')

    # Serialize device data for JavaScript
    device_data = []
    for device in devices:
        # Get the latest location for this device
        latest_location = device.locations.first()

        # Determine status based on latest location
        status = determine_device_status(latest_location)

        device_data.append({
            'id': device.id,
            'name': device.name,
            'imei': device.imei,
            'lat': float(latest_location.latitude) if latest_location else None,
            'lng': float(latest_location.longitude) if latest_location else None,
            'last_update': latest_location.created_at.isoformat() if latest_location else None,
            'status': status,
            'battery_level': latest_location.battery_level if latest_location else None,
            'speed': latest_location.speed if latest_location else 0,
            'heading': latest_location.heading if latest_location else 0,
            'signal_strength': latest_location.signal_strength if latest_location else None,
            'satellites': latest_location.satellites if latest_location else None,
            'driver_name': device.driver_name,
            'sim_card_number': device.sim_no,
            'model': device.model.model_name if device.model else None,
            'matched_geometry': latest_location.matched_geometry if latest_location else None,
            'mcc': latest_location.mcc if latest_location else None,
            'mnc': latest_location.mnc if latest_location else None,
            'lac': latest_location.lac if latest_location else None,
            'cid': latest_location.cid if latest_location else None,
        })

    context = {
        'access_token': access_token,
        'hierarchy': hierarchy,
        'device_data_json': json.dumps(device_data),
        'user': request.user,
        'show_sidebar': True,
        'NESHAN_MAP_API_KEY': settings.NESHAN_MAP_API_KEY,
        'NESHAN_SERVICE_API_KEY': settings.NESHAN_SERVICE_API_KEY,
    }

    return render(request, 'gps_devices/map_v2.html', context)


@login_required
def report(request):
    """
    نمایش صفحه گزارش دستگاه‌ها
    """
    # Build user tree
    user_tree = build_user_tree(request.user)

    # Get active devices
    if request.user.is_staff or request.user.is_superuser:
        devices = Device.objects.filter(status='active').select_related('model')
    else:
        user_ids = get_all_subuser_ids(request.user)
        devices = Device.objects.filter(owner_id__in=user_ids, status='active').select_related('model')

    devices_json = serializers.serialize('json', devices)

    
    context = {
        'user_tree': user_tree,
        'devices': devices,
        'device_data_json': devices_json,
        'user': request.user,
        'show_sidebar': False,
        'NESHAN_MAP_API_KEY': settings.NESHAN_MAP_API_KEY,
        'NESHAN_SERVICE_API_KEY': settings.NESHAN_SERVICE_API_KEY,
    }

    if request.method == 'POST':
        selected_devices = request.POST.getlist('devices')
        start_date = request.POST.get('start_date')
        start_time = request.POST.get('start_time')
        end_date = request.POST.get('end_date')
        end_time = request.POST.get('end_time')

        # Parse Shamsi dates and times, convert to Gregorian
        start_jdt = jdatetime.datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
        end_jdt = jdatetime.datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
        start_datetime = timezone.make_aware(start_jdt.togregorian())
        end_datetime = timezone.make_aware(end_jdt.togregorian())

        # Query LocationData
        report_data = LocationData.objects.filter(
            device_id__in=selected_devices,
            created_at__range=(start_datetime, end_datetime)
        ).order_by('created_at')

        # Prepare report data with Shamsi timestamps
        report_list = []
        for loc in report_data:
            shamsi_dt = jdatetime.datetime.fromgregorian(datetime=loc.created_at)
            report_list.append({
                'shamsi_timestamp': shamsi_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'speed': loc.speed,
                'direction': loc.heading,
            })
        context['report_data'] = report_list

    return render(request, 'gps_devices/report.html', context)





def determine_device_status(latest_location):
    """Determine device status based on latest location data"""
    if latest_location:
        if latest_location.is_alarm:
            return 'alert'
        elif latest_location.speed > 0:
            return 'moving'
        elif latest_location.packet_type == 'HB':
            return 'idle'
        else:
            return 'parked'
    else:
        return 'offline'
    
    
def build_user_tree(user, is_admin=False):
    """
    Build hierarchical tree structure for a user and their devices
    """
    # Get user's devices
    user_devices = Device.objects.filter(
        owner=user, 
        status='active'
    ).select_related('model')
    
    # Get device data with latest location
    devices_list = []
    for device in user_devices:
        latest_location = device.locations.first()
        # Determine status based on latest location
        status = determine_device_status(latest_location)
        
        devices_list.append({
            'id': device.id,
            'name': device.name,
            'imei': device.imei,
            'status': status,
            'speed': latest_location.speed if latest_location else 0,
        })
    
    # Count statistics
    total_devices = user_devices.count()
    active_devices = total_devices  # All are active due to filter
    online_devices = sum(1 for d in devices_list if d.get('speed', 0) > 0)
    
    user_node = {
        'id': user.id,
        'name': user.get_full_name() or user.username,
        'username': user.username,
        'role': 'مدیر' if user.is_staff or user.is_superuser else 'کاربر',
        'is_main': True,
        'total_devices': total_devices,
        'active_devices': active_devices,
        'online_devices': online_devices,
        'devices': devices_list,
        'children': []
    }
    
    # Get subusers recursively
    subusers = user.subusers.filter(is_active=True)
    for subuser in subusers:
        user_node['children'].append(build_user_tree(subuser, is_admin))
    
    return user_node


def get_all_subuser_ids(user):
    """
    Get IDs of user and all their subusers recursively
    """
    user_ids = [user.id]
    
    subusers = user.subusers.filter(is_active=True)
    for subuser in subusers:
        user_ids.extend(get_all_subuser_ids(subuser))
    
    return user_ids

