from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Device
from django.contrib.auth import get_user_model
import json

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
        
        device_data.append({
            'id': device.id,
            'name': device.name,
            'imei': device.imei,
            'lat': float(latest_location.latitude) if latest_location else None,
            'lng': float(latest_location.longitude) if latest_location else None,
            'last_update': latest_location.created_at.isoformat() if latest_location else None,
            'status': device.status,
            'battery_level': latest_location.battery_level if latest_location else None,
            'speed': latest_location.speed if latest_location else 0,
            'heading': latest_location.heading if latest_location else 0,
            'signal_strength': latest_location.signal_strength if latest_location else None,
            'satellites': latest_location.satellites if latest_location else None,
            'driver_name': device.driver_name,
            'sim_card_number': device.sim_no,
            'model': device.model.model_name if device.model else None,
            'matched_geometry': latest_location.matched_geometry if latest_location else None,
        })
    
    context = {
        'access_token': access_token,
        'hierarchy': hierarchy,
        'device_data_json': json.dumps(device_data),
        'user': request.user,
    }
    
    return render(request, 'gps_devices/map_v2.html', context)


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
        devices_list.append({
            'id': device.id,
            'name': device.name,
            'imei': device.imei,
            'status': device.status,
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

