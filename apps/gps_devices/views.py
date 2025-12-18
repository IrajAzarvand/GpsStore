from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken
from .models import Device, LocationData, get_visible_devices_queryset
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core import serializers
from django.conf import settings

from django.views.decorators.csrf import csrf_protect
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache

from datetime import datetime, timedelta

import json
import jdatetime
import re

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from apps.gps_devices.services import MapMatchingService
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()


def _ws_broadcast_device_assignment(*, device_id, owner_id, assigned_subuser_id, old_owner_id=None, old_assigned_subuser_id=None, action=None):
    try:
        channel_layer = get_channel_layer()
        payload = {
            'device_id': device_id,
            'owner_id': owner_id,
            'assigned_subuser_id': assigned_subuser_id,
            'old_owner_id': old_owner_id,
            'old_assigned_subuser_id': old_assigned_subuser_id,
            'action': action,
        }

        group_names = {'admins_group'}
        for uid in (owner_id, assigned_subuser_id, old_owner_id, old_assigned_subuser_id):
            if uid:
                group_names.add(f'user_group_{uid}')

        for group_name in group_names:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    'type': 'device_assignment',
                    'data': payload,
                }
            )
    except Exception:
        pass


def clean_and_format_address(addr):
    """
    Cleans and reformats an existing address string.
    Assumes original format is: Specific -> General (Nominatim default)
    Target format: General -> Specific (Province - City - Road)
    """
    if not addr: return None
    
    # Remove 'Iran' variants
    addr = addr.replace('ایران', '').replace('Iran', '')
    
    # Split by comma or Persian comma
    parts = re.split(r'[,،]', addr)
    
    cleaned_parts = []
    for p in parts:
        p = p.strip()
        if not p: continue
        
        # Filter postal codes (digits and dashes, length > 4)
        if re.match(r'^[\d\-]+$', p) and len(p) > 4:
            continue
            
        cleaned_parts.append(p)
    
    # Reverse to get Province first (General -> Specific)
    cleaned_parts.reverse()
    
    return " - ".join(cleaned_parts)


@never_cache
@login_required
def map_v2(request):
    """
    نمایش نقشه با دستگاه‌های فعال
    """
    # Generate JWT token for WebSocket authentication
    refresh = RefreshToken.for_user(request.user)
    access_token = str(refresh.access_token)

    get_token(request)

    # Build hierarchical structure
    hierarchy = []

    if request.user.is_staff or request.user.is_superuser:
        # Admin sees all users and their devices
        # Get all root users (users without parent)
        root_users = User.objects.filter(is_subuser_of__isnull=True, is_active=True)

        for user in root_users:
            hierarchy.append(build_user_tree(user, is_admin=True))

        unowned_devices_node = build_unowned_devices_node()
        if unowned_devices_node:
            hierarchy.append(unowned_devices_node)
    else:
        # Regular user sees only themselves and their subusers
        hierarchy.append(build_user_tree(request.user, is_admin=False))

    # Collect all devices for JSON data
    devices = get_visible_devices_queryset(request.user, only_active=True)

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
            'address': clean_and_format_address(latest_location.address) if latest_location else None,
        })

    is_admin_user = bool(getattr(request.user, 'is_staff', False) or getattr(request.user, 'is_superuser', False))
    is_subuser = bool(getattr(request.user, 'is_subuser_of_id', None))

    root_users_json = json.dumps([
        {'id': u.id, 'username': u.username, 'name': u.get_full_name() or u.username}
        for u in User.objects.filter(is_subuser_of__isnull=True, is_active=True)
    ]) if is_admin_user else json.dumps([])

    subusers_json = json.dumps([
        {'id': u.id, 'username': u.username, 'name': u.get_full_name() or u.username}
        for u in User.objects.filter(is_subuser_of=request.user, is_active=True)
    ]) if (not is_admin_user and not is_subuser) else json.dumps([])

    context = {
        'access_token': access_token,
        'hierarchy': hierarchy,
        'device_data_json': json.dumps(device_data),
        'user': request.user,
        'show_sidebar': True,
        'NESHAN_MAP_API_KEY': settings.NESHAN_MAP_API_KEY,
        'is_admin_user': is_admin_user,
        'can_assign_in_tree': bool(is_admin_user or not is_subuser),
        'root_users_json': root_users_json,
        'subusers_json': subusers_json,
    }

    return render(request, 'gps_devices/map_v2.html', context)


@login_required
@require_POST
@csrf_protect
def assign_device_owner(request):
    if not (getattr(request.user, 'is_staff', False) or getattr(request.user, 'is_superuser', False)):
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    device_id = request.POST.get('device_id')
    owner_id = request.POST.get('owner_id')
    new_username = request.POST.get('new_username')
    new_password = request.POST.get('new_password')
    new_first_name = request.POST.get('new_first_name', '')
    new_last_name = request.POST.get('new_last_name', '')

    if not device_id:
        return JsonResponse({'ok': False, 'error': 'device_id_required'}, status=400)

    device = Device.objects.filter(id=device_id).first()
    if not device:
        return JsonResponse({'ok': False, 'error': 'device_not_found'}, status=404)

    old_owner_id = device.owner_id
    old_assigned_subuser_id = device.assigned_subuser_id

    owner = None
    if owner_id:
        owner = User.objects.filter(id=owner_id, is_subuser_of__isnull=True, is_active=True).first()
        if not owner:
            return JsonResponse({'ok': False, 'error': 'owner_not_found'}, status=404)
    else:
        if not (new_username and new_password):
            return JsonResponse({'ok': False, 'error': 'owner_id_or_new_user_required'}, status=400)

        if User.objects.filter(username=new_username).exists():
            return JsonResponse({'ok': False, 'error': 'username_exists'}, status=400)

        owner = User.objects.create_user(
            username=new_username,
            password=new_password,
            first_name=new_first_name,
            last_name=new_last_name,
            is_active=True,
        )

    Device.objects.filter(id=device.id).update(owner=owner, assigned_subuser=None)

    _ws_broadcast_device_assignment(
        device_id=device.id,
        owner_id=owner.id if owner else None,
        assigned_subuser_id=None,
        old_owner_id=old_owner_id,
        old_assigned_subuser_id=old_assigned_subuser_id,
        action='owner_changed',
    )
    return JsonResponse({'ok': True, 'device_id': device.id, 'owner_id': owner.id})


@login_required
@require_POST
@csrf_protect
def assign_device_subuser(request):
    if getattr(request.user, 'is_subuser_of_id', None):
        return JsonResponse({'ok': False, 'error': 'forbidden'}, status=403)

    device_id = request.POST.get('device_id')
    subuser_id = request.POST.get('subuser_id')

    if not device_id:
        return JsonResponse({'ok': False, 'error': 'device_id_required'}, status=400)

    device = Device.objects.filter(id=device_id, owner=request.user).first()
    if not device:
        return JsonResponse({'ok': False, 'error': 'device_not_found_or_forbidden'}, status=404)

    old_assigned_subuser_id = device.assigned_subuser_id

    if not subuser_id:
        Device.objects.filter(id=device.id).update(assigned_subuser=None)

        _ws_broadcast_device_assignment(
            device_id=device.id,
            owner_id=request.user.id,
            assigned_subuser_id=None,
            old_owner_id=request.user.id,
            old_assigned_subuser_id=old_assigned_subuser_id,
            action='unassigned_subuser',
        )
        return JsonResponse({'ok': True, 'device_id': device.id, 'subuser_id': None})

    subuser = User.objects.filter(id=subuser_id, is_subuser_of=request.user, is_active=True).first()
    if not subuser:
        return JsonResponse({'ok': False, 'error': 'subuser_not_found'}, status=404)

    Device.objects.filter(id=device.id).update(assigned_subuser=subuser)

    _ws_broadcast_device_assignment(
        device_id=device.id,
        owner_id=request.user.id,
        assigned_subuser_id=subuser.id,
        old_owner_id=request.user.id,
        old_assigned_subuser_id=old_assigned_subuser_id,
        action='assigned_subuser',
    )
    return JsonResponse({'ok': True, 'device_id': device.id, 'subuser_id': subuser.id})


@never_cache
@login_required
def report(request):
    """
    نمایش صفحه گزارش دستگاه‌ها
    """
    # Build user tree
    user_tree = build_user_tree(request.user)

    # Get active devices
    devices = get_visible_devices_queryset(request.user, only_active=True)

    devices_json = serializers.serialize('json', devices)

    
    context = {
        'user_tree': user_tree,
        'devices': devices,
        'device_data_json': devices_json,
        'user': request.user,
        'show_sidebar': False,
        'NESHAN_MAP_API_KEY': settings.NESHAN_MAP_API_KEY,
    }

    if request.method == 'POST':
        selected_devices = request.POST.getlist('devices')
        start_date = request.POST.get('start_date')
        start_time = request.POST.get('start_time')
        end_date = request.POST.get('end_date')
        end_time = request.POST.get('end_time')

        # Validate all required fields
        if not selected_devices:
            context['error'] = 'لطفاً یک دستگاه انتخاب کنید'
            return render(request, 'gps_devices/report.html', context)
        
        # Security Check: Ensure user has access to these devices
        allowed_device_ids = set(d.id for d in devices)
        # Filter out any device IDs not in the allowed list (Anti-hack)
        valid_selected_devices = [d_id for d_id in selected_devices if int(d_id) in allowed_device_ids]
        
        if not valid_selected_devices:
            context['error'] = 'شما دسترسی به دستگاه انتخاب شده را ندارید'
            return render(request, 'gps_devices/report.html', context)
            
        selected_devices = valid_selected_devices
        
        if not start_date or not start_time:
            context['error'] = 'لطفاً تاریخ و ساعت شروع را وارد کنید'
            return render(request, 'gps_devices/report.html', context)
        
        if not end_date or not end_time:
            context['error'] = 'لطفاً تاریخ و ساعت پایان را وارد کنید'
            return render(request, 'gps_devices/report.html', context)

        try:
            # Parse Shamsi dates and times, convert to Gregorian
            start_jdt = jdatetime.datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            end_jdt = jdatetime.datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
            start_datetime = timezone.make_aware(start_jdt.togregorian())
            end_datetime = timezone.make_aware(end_jdt.togregorian())
        except ValueError as e:
            context['error'] = f'فرمت تاریخ یا زمان نامعتبر است: {str(e)}'
            return render(request, 'gps_devices/report.html', context)

        # Query LocationData
        report_qs = LocationData.objects.filter(
            device_id__in=selected_devices,
            timestamp__range=(start_datetime, end_datetime)
        ).order_by('timestamp')

        # Process data into daily groups with stats
        from collections import defaultdict
        from geopy.distance import geodesic

        daily_groups = defaultdict(lambda: {
            'points': [],
            'stats': {
                'max_speed': 0,
                'total_speed': 0,
                'count': 0,
                'distance': 0.0,
                'move_count': 0,
                'stop_count': 0
            }
        })

        last_point = None
        
        for loc in report_qs:
            # convert to local time first to ensure Iran time
            event_time = loc.timestamp or loc.created_at
            local_event_time = timezone.localtime(event_time)
            shamsi_dt = jdatetime.datetime.fromgregorian(datetime=local_event_time)
            date_str = shamsi_dt.strftime('%Y-%m-%d')
            time_str = shamsi_dt.strftime('%H:%M:%S')
            
            # Status
            status = determine_device_status(loc)
            
            # Point Data
            point_data = {
                'shamsi_timestamp': shamsi_dt.strftime('%Y-%m-%d %H:%M:%S'),
                'shamsi_date': date_str,
                'shamsi_time': time_str,
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'speed': loc.speed,
                'direction': loc.heading,
                'altitude': loc.altitude,
                'satellites': loc.satellites,
                'battery': loc.battery_level,
                'signal': loc.signal_strength,
                'status': status,
                'address': clean_and_format_address(loc.address) if loc.address else 'آدرس نامشخص',
                'matched_geometry': loc.matched_geometry, # Add matched geometry
                'raw_timestamp': loc.created_at.timestamp()
            }
            
            group = daily_groups[date_str]
            group['points'].append(point_data)
            
            # Update Stats
            group['stats']['max_speed'] = max(group['stats']['max_speed'], loc.speed)
            group['stats']['total_speed'] += loc.speed
            group['stats']['count'] += 1
            if status == 'moving':
                group['stats']['move_count'] += 1
            else:
                group['stats']['stop_count'] += 1
                
            # Distance Calculation
            if last_point:
                # Only add distance if same day (optional, but usually sequential)
                dist = geodesic((last_point.latitude, last_point.longitude), (loc.latitude, loc.longitude)).kilometers
                # Filter noise: ignore very small movements if speed is 0
                if dist > 0.005: # > 5 meters
                    group['stats']['distance'] += dist
            
            last_point = loc

        # Finalize Groups
        final_report_data = []
        # Sort by date
        sorted_dates = sorted(daily_groups.keys())
        
        for date in sorted_dates:
            group = daily_groups[date]
            count = group['stats']['count']
            avg_speed = group['stats']['total_speed'] / count if count > 0 else 0
            
            final_report_data.append({
                'date': date,
                'stats': {
                    'max_speed': round(group['stats']['max_speed'], 1),
                    'avg_speed': round(avg_speed, 1),
                    'distance': round(group['stats']['distance'], 2),
                    'total_points': count,
                    'move_percent': round((group['stats']['move_count'] / count * 100), 0) if count > 0 else 0
                },
                'points': group['points']
            })

        context['report_data'] = final_report_data # This is now a list of daily objects

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
    if getattr(user, 'is_subuser_of_id', None):
        user_devices = Device.objects.filter(
            assigned_subuser=user,
            status='active'
        ).select_related('model')
    else:
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

def build_unowned_devices_node():
    unowned_devices = Device.objects.filter(owner__isnull=True, status='active').select_related('model')

    if not unowned_devices.exists():
        return None

    devices_list = []
    for device in unowned_devices:
        latest_location = device.locations.first()
        status = determine_device_status(latest_location)

        devices_list.append({
            'id': device.id,
            'name': device.name,
            'imei': device.imei,
            'status': status,
            'speed': latest_location.speed if latest_location else 0,
        })

    total_devices = unowned_devices.count()
    online_devices = sum(1 for d in devices_list if d.get('speed', 0) > 0)

    return {
        'id': 'unowned',
        'name': 'دستگاه‌های بدون مالک',
        'username': '',
        'role': 'سیستمی',
        'is_main': True,
        'total_devices': total_devices,
        'active_devices': total_devices,
        'online_devices': online_devices,
        'devices': devices_list,
        'children': [],
    }

def get_all_subuser_ids(user):
    """
    Get IDs of user and all their subusers recursively
    """
    user_ids = [user.id]
    
    subusers = user.subusers.filter(is_active=True)
    for subuser in subusers:
        user_ids.extend(get_all_subuser_ids(subuser))
    
    return user_ids

@never_cache
@login_required
def get_device_report(request):
    """
    API endpoint برای دریافت گزارش دستگاه به صورت JSON
    """
    from django.http import JsonResponse
    
    if request.method != 'POST':
        return JsonResponse({'error': 'فقط متد POST مجاز است'}, status=405)
    
    try:
        # دریافت پارامترها از request
        device_id = request.POST.get('device_id')
        start_date = request.POST.get('start_date')  # فرمت: YYYY/MM/DD
        start_time = request.POST.get('start_time')  # فرمت: HH:mm
        end_date = request.POST.get('end_date')
        end_time = request.POST.get('end_time')
        
        # بررسی پارامترهای ضروری
        if not all([device_id, start_date, start_time, end_date, end_time]):
            return JsonResponse({'error': 'تمام فیلدها الزامی هستند'}, status=400)
        
        # بررسی دسترسی کاربر به دستگاه
        devices_qs = get_visible_devices_queryset(request.user, only_active=True)
        device = devices_qs.filter(id=device_id).first()
        
        if not device:
            return JsonResponse({'error': 'دستگاه یافت نشد یا دسترسی ندارید'}, status=404)
        
        # تبدیل تاریخ شمسی به میلادی
        try:
            start_jdt = jdatetime.datetime.strptime(f"{start_date} {start_time}", "%Y/%m/%d %H:%M")
            end_jdt = jdatetime.datetime.strptime(f"{end_date} {end_time}", "%Y/%m/%d %H:%M")
            start_datetime = timezone.make_aware(start_jdt.togregorian())
            end_datetime = timezone.make_aware(end_jdt.togregorian())
        except ValueError as e:
            return JsonResponse({'error': f'فرمت تاریخ یا زمان نامعتبر است: {str(e)}'}, status=400)
        
        # دریافت داده‌های موقعیت
        locations = LocationData.objects.filter(
            device_id=device_id,
            timestamp__range=(start_datetime, end_datetime),
            is_valid=True
        ).order_by('timestamp')
        
        # آماده‌سازی داده‌ها برای پاسخ
        report_data = []
        total_distance = 0
        max_speed = 0
        
        prev_loc = None
        for loc in locations:
            # تبدیل تاریخ به شمسی
            event_time = loc.timestamp or loc.created_at
            local_event_time = timezone.localtime(event_time)
            shamsi_dt = jdatetime.datetime.fromgregorian(datetime=local_event_time)            
            
            # محاسبه فاصله از نقطه قبلی (تقریبی)
            if prev_loc and loc.latitude and loc.longitude and prev_loc.latitude and prev_loc.longitude:
                from math import radians, sin, cos, sqrt, atan2
                
                lat1, lon1 = float(prev_loc.latitude), float(prev_loc.longitude)
                lat2, lon2 = float(loc.latitude), float(loc.longitude)
                
                # فرمول Haversine
                R = 6371000  # شعاع زمین به متر
                dlat = radians(lat2 - lat1)
                dlon = radians(lon2 - lon1)
                a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                c = 2 * atan2(sqrt(a), sqrt(1-a))
                distance = R * c
                total_distance += distance
            
            if loc.speed > max_speed:
                max_speed = loc.speed
            
            report_data.append({
                'timestamp': shamsi_dt.strftime('%Y/%m/%d %H:%M:%S'),
                'latitude': float(loc.latitude) if loc.latitude else None,
                'longitude': float(loc.longitude) if loc.longitude else None,
                'speed': loc.speed,
                'heading': loc.heading,
                'altitude': loc.altitude,
                'satellites': loc.satellites,
                'battery_level': loc.battery_level,
                'signal_strength': loc.signal_strength,
                'address': loc.address,
                'matched_geometry': loc.matched_geometry,
            })
            
            prev_loc = loc
        
        # محاسبه آمار کلی
        duration_seconds = (end_datetime - start_datetime).total_seconds()
        duration_hours = duration_seconds / 3600
        avg_speed = (total_distance / duration_seconds * 3.6) if duration_seconds > 0 else 0  # km/h
        
        response_data = {
            'device': {
                'id': device.id,
                'name': device.name,
                'imei': device.imei,
                'model': str(device.model),
            },
            'period': {
                'start': jdatetime.datetime.fromgregorian(datetime=start_datetime).strftime('%Y/%m/%d %H:%M'),
                'end': jdatetime.datetime.fromgregorian(datetime=end_datetime).strftime('%Y/%m/%d %H:%M'),
                'duration_hours': round(duration_hours, 2),
            },
            'statistics': {
                'total_points': len(report_data),
                'total_distance_km': round(total_distance / 1000, 2),
                'max_speed_kmh': round(max_speed, 2),
                'avg_speed_kmh': round(avg_speed, 2),
            },
            'locations': report_data,
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        return JsonResponse({'error': f'خطا در پردازش درخواست: {str(e)}'}, status=500)


@login_required
@require_POST
def map_match_points(request):
    """Server-side map-matching endpoint used by report playback.

    Expects JSON body:
        {"points": [{"lat": 35.7, "lng": 51.3}, ...]}

    Returns:
        {"snappedPoints": [...], "geometry": "..."}
    """
    try:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except Exception:
            return JsonResponse({'error': 'بدنه درخواست نامعتبر است (JSON).'}, status=400)

        points_in = payload.get('points')
        if not isinstance(points_in, list) or len(points_in) < 2:
            return JsonResponse({'error': 'حداقل 2 نقطه برای map-matching لازم است.'}, status=400)

        # Hard cap to protect service/API
        max_points = 200
        if len(points_in) > max_points:
            points_in = points_in[:max_points]

        points = []
        for p in points_in:
            if not isinstance(p, dict):
                continue
            lat = p.get('lat')
            lng = p.get('lng')
            if lat is None or lng is None:
                continue
            try:
                lat_f = float(lat)
                lng_f = float(lng)
            except (TypeError, ValueError):
                continue
            points.append((lat_f, lng_f))

        if len(points) < 2:
            return JsonResponse({'error': 'نقاط معتبر کافی نیست.'}, status=400)

        service = MapMatchingService()
        result = service.match_points(points, use_cache=True)
        if not result:
            return JsonResponse({'error': 'map-matching ناموفق بود.'}, status=502)

        return JsonResponse({
            'snappedPoints': result.get('snappedPoints', []),
            'geometry': result.get('geometry'),
        })

    except Exception as e:
        return JsonResponse({'error': f'خطا در map-matching: {str(e)}'}, status=500)