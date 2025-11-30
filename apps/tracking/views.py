from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
import json

from rest_framework_simplejwt.tokens import AccessToken
from apps.gps_devices.models import Device
from .models import LocationData, Geofence, Alert


@login_required
def tracking_dashboard(request):
    """
    Main tracking dashboard showing all user's devices
    """
    devices = Device.objects.filter(user=request.user).select_related('device_type')
    active_alerts = Alert.objects.filter(
        device__user=request.user,
        is_resolved=False
    ).select_related('device').order_by('-created_at')[:5]

    # Generate JWT access token for WebSocket authentication
    access_token = AccessToken.for_user(request.user)

    # Prepare device data for JavaScript
    device_data = []
    for device in devices:
        # Get latest location data for speed and heading
        latest_loc = LocationData.objects.filter(device=device).order_by('-timestamp').first()
        
        device_data.append({
            'imei': device.imei or device.device_id,
            'lat': float(device.last_location_lat) if device.last_location_lat else None,
            'lng': float(device.last_location_lng) if device.last_location_lng else None,
            'last_update': device.last_location_time.isoformat() if device.last_location_time else None,
            'battery_level': device.battery_level,
            'speed': float(latest_loc.speed) if latest_loc and latest_loc.speed else 0,
            'heading': float(latest_loc.heading) if latest_loc and latest_loc.heading else 0,
        })

    context = {
        'devices': devices,
        'active_alerts': active_alerts,
        'total_devices': devices.count(),
        'active_devices': devices.filter(status='active').count(),
        'access_token': str(access_token),
        'device_data_json': device_data,
    }
    return render(request, 'gps_devices/map_v2.html', context)


@login_required
def device_tracking(request, device_id):
    """
    Detailed tracking view for a specific device
    """
    device = get_object_or_404(Device, id=device_id, user=request.user)

    # Get recent location data (last 24 hours)
    recent_locations = LocationData.objects.filter(
        device=device,
        timestamp__gte=timezone.now() - timezone.timedelta(hours=24)
    ).order_by('-timestamp')[:100]

    # Get geofences for this device
    geofences = Geofence.objects.filter(user=request.user)

    # Get recent alerts
    recent_alerts = Alert.objects.filter(
        device=device
    ).order_by('-created_at')[:10]

    context = {
        'device': device,
        'recent_locations': recent_locations,
        'geofences': geofences,
        'recent_alerts': recent_alerts,
        'location_count': recent_locations.count(),
    }
    return render(request, 'tracking/device_tracking.html', context)


@login_required
@require_POST
def update_device_location(request, device_id):
    """
    API endpoint to update device location (for GPS devices)
    """
    device = get_object_or_404(Device, id=device_id)

    try:
        data = json.loads(request.body)

        location_data = LocationData.objects.create(
            device=device,
            latitude=data['latitude'],
            longitude=data['longitude'],
            altitude=data.get('altitude'),
            speed=data.get('speed'),
            heading=data.get('heading'),
            accuracy=data.get('accuracy'),
            battery_level=data.get('battery_level'),
            signal_strength=data.get('signal_strength'),
            raw_data=data.get('raw_data', {}),
            timestamp=data.get('timestamp'),
        )

        # Update device last location
        device.update_location(
            location_data.latitude,
            location_data.longitude,
            location_data.timestamp
        )

        # Check geofence alerts
        check_geofence_alerts(device, location_data.latitude, location_data.longitude)

        return JsonResponse({'status': 'success', 'location_id': location_data.id})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@login_required
def get_device_locations(request, device_id):
    """
    API endpoint to get device location history
    """
    device = get_object_or_404(Device, id=device_id, user=request.user)

    # Parse query parameters
    hours = int(request.GET.get('hours', 24))
    limit = int(request.GET.get('limit', 100))

    locations = LocationData.objects.filter(
        device=device,
        timestamp__gte=timezone.now() - timezone.timedelta(hours=hours)
    ).order_by('-timestamp')[:limit]

    location_data = [{
        'id': loc.id,
        'latitude': float(loc.latitude),
        'longitude': float(loc.longitude),
        'timestamp': loc.timestamp.isoformat(),
        'speed': float(loc.speed) if loc.speed else None,
        'battery_level': loc.battery_level,
        'address': loc.address,
    } for loc in locations]

    return JsonResponse({
        'device_id': device.id,
        'device_name': device.name,
        'locations': location_data
    })


@login_required
def geofence_list(request):
    """
    List all geofences for the user
    """
    geofences = Geofence.objects.filter(user=request.user).order_by('-created_at')

    context = {
        'geofences': geofences,
    }
    return render(request, 'tracking/geofence_list.html', context)


@login_required
def geofence_create(request):
    """
    Create a new geofence
    """
    if request.method == 'POST':
        # Handle form submission
        pass

    return render(request, 'tracking/geofence_form.html')


@login_required
def geofence_detail(request, geofence_id):
    """
    View geofence details
    """
    geofence = get_object_or_404(Geofence, id=geofence_id, user=request.user)

    context = {
        'geofence': geofence,
    }
    return render(request, 'tracking/geofence_detail.html', context)


@login_required
def alert_list(request):
    """
    List all alerts for the user
    """
    alerts = Alert.objects.filter(
        device__user=request.user
    ).select_related('device').order_by('-created_at')

    # Pagination
    paginator = Paginator(alerts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'alerts': page_obj,
        'unread_count': alerts.filter(is_read=False).count(),
    }
    return render(request, 'tracking/alert_list.html', context)


@login_required
@require_POST
def mark_alert_read(request, alert_id):
    """
    Mark an alert as read
    """
    alert = get_object_or_404(Alert, id=alert_id, device__user=request.user)
    alert.is_read = True
    alert.save()

    return JsonResponse({'status': 'success'})


@login_required
@require_POST
def resolve_alert(request, alert_id):
    """
    Resolve an alert
    """
    alert = get_object_or_404(Alert, id=alert_id, device__user=request.user)
    alert.resolve()

    return JsonResponse({'status': 'success'})


def check_geofence_alerts(device, lat, lng):
    """
    Check if device location triggers any geofence alerts
    """
    geofences = Geofence.objects.filter(user=device.user, is_active=True)

    for geofence in geofences:
        is_inside = geofence.contains_point(lat, lng)

        # Check for enter/exit alerts
        if geofence.alert_on_enter and is_inside:
            # Check if device was previously outside
            last_location = LocationData.objects.filter(
                device=device
            ).exclude(id=LocationData.objects.filter(device=device).order_by('-timestamp').first().id if LocationData.objects.filter(device=device).exists() else None).order_by('-timestamp').first()

            if last_location and not geofence.contains_point(last_location.latitude, last_location.longitude):
                Alert.objects.create(
                    device=device,
                    alert_type='geofence_enter',
                    message=f"دستگاه وارد منطقه {geofence.name} شد",
                    location_data=LocationData.objects.filter(device=device).order_by('-timestamp').first(),
                )

        elif geofence.alert_on_exit and not is_inside:
            # Check if device was previously inside
            last_location = LocationData.objects.filter(
                device=device
            ).exclude(id=LocationData.objects.filter(device=device).order_by('-timestamp').first().id if LocationData.objects.filter(device=device).exists() else None).order_by('-timestamp').first()

            if last_location and geofence.contains_point(last_location.latitude, last_location.longitude):
                Alert.objects.create(
                    device=device,
                    alert_type='geofence_exit',
                    message=f"دستگاه از منطقه {geofence.name} خارج شد",
                    location_data=LocationData.objects.filter(device=device).order_by('-timestamp').first(),
                )


@login_required
def real_time_tracking(request, device_id):
    """
    Real-time tracking view with WebSocket support
    """
    device = get_object_or_404(Device, id=device_id, user=request.user)

    recent_locations = LocationData.objects.filter(
        device=device,
        timestamp__gte=timezone.now() - timezone.timedelta(hours=1)
    ).order_by('timestamp')

    locations_data = [{
        'latitude': float(loc.latitude),
        'longitude': float(loc.longitude),
        'speed': float(loc.speed) if loc.speed else None,
        'timestamp': loc.timestamp.isoformat(),
        'battery_level': loc.battery_level,
    } for loc in recent_locations]

    context = {
        'device': device,
        'initial_locations': json.dumps(locations_data),
    }
    return render(request, 'tracking/real_time_tracking.html', context)
