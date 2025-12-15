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
import re

User = get_user_model()

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
            'address': clean_and_format_address(latest_location.address) if latest_location else None,
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
            created_at__range=(start_datetime, end_datetime)
        ).order_by('created_at')

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
            shamsi_dt = jdatetime.datetime.fromgregorian(datetime=loc.created_at)
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
        if request.user.is_staff or request.user.is_superuser:
            device = Device.objects.filter(id=device_id, status='active').first()
        else:
            user_ids = get_all_subuser_ids(request.user)
            device = Device.objects.filter(id=device_id, owner_id__in=user_ids, status='active').first()
        
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
            created_at__range=(start_datetime, end_datetime),
            is_valid=True
        ).order_by('created_at')
        
        # آماده‌سازی داده‌ها برای پاسخ
        report_data = []
        total_distance = 0
        max_speed = 0
        
        prev_loc = None
        for loc in locations:
            # تبدیل تاریخ به شمسی
            shamsi_dt = jdatetime.datetime.fromgregorian(datetime=loc.created_at)
            
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