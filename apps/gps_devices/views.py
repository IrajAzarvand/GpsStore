from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import reverse
from django.utils import timezone
from django.db.models import Q
from apps.gps_devices.models import RawGPSData, Protocol, Device
from apps.gps_devices.forms import DeviceForm
from apps.tracking.models import LocationData
from datetime import datetime
import logging
from django.core.serializers.json import DjangoJSONEncoder
import json
import re
from HQ_Decoder import HQFullDecoder

logger = logging.getLogger(__name__)

def parse_gps_data(data):
    """
    Parse GPS data using HQ_Decoder.decode_packet(raw_data)
    Returns parsed data dict or None if invalid
    """
    try:
        logger.debug(f"Starting parse_gps_data for data: {data[:100]}...")
        decoder = HQFullDecoder()
        decoded = decoder.decode(data)
        logger.debug(f"Decoded result: {decoded}")

        if "error" in decoded:
            logger.warning(f'Decoding error: {decoded["error"]}')
            return None

        packet_type = decoded.get("type")
        if packet_type != "V1":
            logger.warning(f'Unsupported packet type: {packet_type}')
            return None

        # Extract fields from decoded dict
        device_id = decoded.get('imei')
        latitude = decoded.get('latitude')
        longitude = decoded.get('longitude')
        logger.debug(f"Extracted lat={latitude}, lng={longitude}, device_id={device_id}")

        # Validate coordinates
        if latitude is not None and not (-90 <= latitude <= 90):
            logger.warning(f'Invalid latitude: {latitude}')
            latitude = None
        if longitude is not None and not (-180 <= longitude <= 180):
            logger.warning(f'Invalid longitude: {longitude}')
            longitude = None

        speed = decoded.get('speed_kph', 0)
        heading = decoded.get('angle', 0)
        timestamp_str = decoded.get('timestamp')
        if timestamp_str:
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                timestamp = timestamp.replace(tzinfo=datetime.timezone.utc)
            except ValueError as e:
                logger.warning(f'Invalid timestamp: {e}')
                return None
        else:
            logger.warning('Missing timestamp')
            return None

        validity = 'A' if decoded.get('gps_valid') else 'V'
        status = decoded.get('flags_raw', '')
        # For V1 packets, voltage and temperature are not present (fields are MCC/MNC)
        voltage = None
        temperature = None
        odometer = None  # Not parsed in decoder for V1

        # Handle unknown sections - decoder doesn't provide extra parts, so empty
        unknown_sections = {}

        parsed = {
            'device_id': device_id,
            'latitude': latitude,
            'longitude': longitude,
            'speed': speed,
            'heading': heading,
            'timestamp': timestamp,
            'validity': validity,
            'status': status,
            'voltage': voltage,
            'temperature': temperature,
            'odometer': odometer,
            'raw_data': data,
            'unknown_sections': unknown_sections
        }
        logger.debug(f"Parsed data successfully: {parsed}")
        return parsed

    except Exception as e:
        logger.error(f'Error parsing GPS data: {e}', exc_info=True)
        return None

@staff_member_required
@login_required
def register_device(request, raw_data_id):
    logger.info(f"Starting register_device for raw_data_id: {raw_data_id}")
    logger.info("Test log: Logging is working in register_device view")
    raw_data = get_object_or_404(RawGPSData, id=raw_data_id)
    logger.info(f"Retrieved raw_data: {raw_data.id}, raw_data: {raw_data.raw_data}")

    if not raw_data.is_unregistered_attempt:
        logger.warning(f"Raw data {raw_data_id} is not from unregistered device")
        messages.error(request, 'This raw data is not from an unregistered device.')
        return redirect('admin:gps_devices_rawgpsdata_changelist')

    try:
        logger.info(f"Parsing GPS data for raw_data_id: {raw_data_id}")
        parsed_data = parse_gps_data(raw_data.raw_data)
        logger.info(f"Parsed data result: {parsed_data}")
        if not parsed_data:
            logger.warning(f"Failed to parse GPS data, attempting fallback extraction")
            # Try to extract IMEI with regex
            imei_match = re.search(r'\b\d{15}\b', raw_data.raw_data)
            imei = imei_match.group(0) if imei_match else None

            # Extract device_id from raw data: strip *, split by ,, take second field
            stripped = raw_data.raw_data.strip('*')
            parts = stripped.split(',')
            extracted_device_id = parts[1] if len(parts) > 1 else None

            # Prioritize IMEI, then extracted device_id
            if imei:
                device_id = imei
                logger.info(f"Extracted IMEI: {imei}")
            elif extracted_device_id:
                device_id = extracted_device_id
                logger.info(f"Extracted device_id: {extracted_device_id}")
            else:
                logger.error(f"Could not extract IMEI or device_id from raw_data: {raw_data.raw_data}")
                messages.error(request, 'Failed to parse GPS data and could not extract IMEI or device_id.')
                return redirect('admin:gps_devices_rawgpsdata_changelist')

            # Create fallback parsed_data with defaults
            parsed_data = {
                'device_id': device_id,
                'latitude': None,
                'longitude': None,
                'speed': 0,
                'heading': 0,
                'timestamp': timezone.now(),
                'validity': 'V',
                'status': '',
                'voltage': None,
                'temperature': None,
                'odometer': None,
                'raw_data': raw_data.raw_data,
                'unknown_sections': {}
            }
            logger.info(f"Created fallback parsed_data: {parsed_data}")
    except Exception as e:
        logger.error(f"Error during GPS data parsing and fallback: {e}", exc_info=True)
        messages.error(request, 'Failed to parse GPS data.')
        return redirect('admin:gps_devices_rawgpsdata_changelist')

    try:
        if request.method == 'POST':
            logger.info(f"Processing POST request for device registration, POST data: {request.POST}")
            form = DeviceForm(request.POST)
            logger.info(f"Form created, checking validity")
            if form.is_valid():
                logger.info(f"Form is valid, attempting to save device")
                device = form.save()
                logger.info(f"Device saved successfully: {device.id} with IMEI={device.imei}, device_id={device.device_id}")
                # Process pending data
                logger.info(f"Calling process_pending_data with device_id: {parsed_data['device_id']}")
                process_pending_data(device, parsed_data['device_id'])
                logger.info(f"Pending data processed successfully for device {device.id}")
                messages.success(request, f'Device {device.name} registered successfully and pending data processed.')
                return redirect('admin:gps_devices_device_changelist')
            else:
                logger.warning(f"Form is invalid: {form.errors}")
                logger.info(f"Form non_field_errors: {form.non_field_errors()}")
        else:
            logger.info(f"Rendering GET request form")
            # Pre-fill form
            initial = {
                'device_id': parsed_data['device_id'],
                'model': 'GT06',  # Default model, can be changed
                'name': f'Device {parsed_data["device_id"]}',
            }
            form = DeviceForm(initial=initial)
            logger.info(f"Form initialized with initial data: {initial}")

        logger.info(f"Rendering template with parsed_data keys: {list(parsed_data.keys())}")
        return render(request, 'admin/gps_devices/device/register_device.html', {
            'form': form,
            'raw_data': raw_data,
            'parsed_data': parsed_data,
        })
    except Exception as e:
        logger.error(f"Error in register_device view: {e}", exc_info=True)
        messages.error(request, 'An error occurred during device registration.')
        return redirect('admin:gps_devices_rawgpsdata_changelist')

def process_pending_data(device, device_id):
    """
    Process all pending raw data for the given device_id
    """
    logger.info(f"Starting process_pending_data for device {device_id}")
    pending_data = RawGPSData.objects.filter(
        device__isnull=True,
        error_message__icontains=f'Unregistered device {device_id}',
        processed=False
    )
    logger.info(f"Found {pending_data.count()} pending data entries for device {device_id}")

    for raw in pending_data:
        logger.info(f"Processing raw data id: {raw.id}, raw_data: {raw.raw_data}")
        parsed = parse_gps_data(raw.raw_data)
        logger.info(f"Parsed data for raw {raw.id}: {parsed}")
        if parsed and parsed['device_id'] == device_id:
            logger.info(f"Device ID matches, checking coordinates for raw {raw.id}")
            # Validate coordinates
            lat = parsed.get('latitude')
            lng = parsed.get('longitude')
            if lat is not None and lng is not None:
                if not (-90 <= lat <= 90):
                    logger.warning(f"Invalid latitude {lat} for raw {raw.id}, skipping LocationData creation")
                    lat = None
                if not (-180 <= lng <= 180):
                    logger.warning(f"Invalid longitude {lng} for raw {raw.id}, skipping LocationData creation")
                    lng = None
            if lat is not None and lng is not None:
                try:
                    logger.info(f"Creating LocationData for raw {raw.id} with lat={lat}, lng={lng}")
                    # Save to LocationData
                    location_data = LocationData.objects.create(
                        device=device,
                        latitude=lat,
                        longitude=lng,
                        speed=parsed['speed'],
                        heading=parsed['heading'],
                        timestamp=parsed['timestamp'],
                        battery_level=parsed['voltage'],
                        raw_data={
                            'device_id': parsed['device_id'],
                            'validity': parsed['validity'],
                            'status': parsed['status'],
                            'temperature': parsed['temperature'],
                            'odometer': parsed['odometer'],
                            'protocol': raw.protocol.protocol_type if raw.protocol else 'unknown',
                            'ip_address': raw.ip_address
                        }
                    )
                    logger.info(f"LocationData created successfully: {location_data.id}")

                    # Update device last location
                    logger.info(f"Updating device location for device {device.id} with lat={lat}, lng={lng}")
                    device.update_location(lat, lng, parsed['timestamp'])
                    logger.info(f'Device location updated for device {device.device_id}')
                except Exception as e:
                    logger.error(f"Error creating LocationData for raw {raw.id}: {e}", exc_info=True)
            else:
                logger.warning(f"Skipping LocationData creation for raw {raw.id}: coordinates out of range or None lat={lat}, lng={lng}")

            # Update unknown sections and mark raw data as processed regardless
            raw.unknown_sections = parsed['unknown_sections']
            raw.device = device
            raw.mark_processed()
            logger.info(f"Marked raw data {raw.id} as processed")
        else:
            logger.warning(f"Skipping raw {raw.id}: parsed={bool(parsed)}, device_id match={parsed['device_id'] == device_id if parsed else 'N/A'}")

@csrf_exempt
@require_POST
def receive_gps_data(request):
    try:
        # Get raw GPS data from request body
        raw_data = request.body.decode('utf-8', errors='ignore').strip()
        if not raw_data:
            return JsonResponse({'error': 'No data provided'}, status=400)

        ip_address = request.META.get('REMOTE_ADDR')

        # Get or create HTTP protocol
        protocol, created = Protocol.objects.get_or_create(
            name='HTTP GPS Data',
            defaults={
                'protocol_type': 'http',
                'description': 'Protocol for GPS data received via HTTP POST',
            }
        )

        # Parse data to extract unknown sections
        parsed = parse_gps_data(raw_data)
        unknown_sections = parsed['unknown_sections'] if parsed else {}

        # Save raw data
        raw_gps_data = RawGPSData.objects.create(
            device=None,  # No device associated yet
            protocol=protocol,
            raw_data=raw_data,
            ip_address=ip_address,
            unknown_sections=unknown_sections,
            error_message='',
        )

        logger.info(f'Saved HTTP GPS data: {raw_gps_data.id} from {ip_address}')
        return JsonResponse({'status': 'success', 'id': raw_gps_data.id})

    except Exception as e:
        logger.error(f'Error saving HTTP GPS data: {e}')
        return JsonResponse({'error': 'Internal server error'}, status=500)


@staff_member_required
@login_required
def device_map(request):
    """
    View for displaying devices on a map
    """
    logger.info("Test log: device_map view accessed")
    from apps.accounts.models import SubUser
    from datetime import timedelta

    # Build hierarchy for sidebar
    hierarchy = []
    
    try:
        # Case 1: SubUser (Normal User)
        subuser = SubUser.objects.get(username=request.user.username)
        
        # Get assigned devices
        assigned_devices = subuser.assigned_devices.filter(status='active').exclude(expires_at__lt=timezone.now())
        
        # Calculate device stats for this user
        online_threshold = timezone.now() - timedelta(minutes=10)
        total_count = assigned_devices.count()
        active_count = assigned_devices.exclude(Q(last_location_lat__isnull=True) | Q(last_location_lng__isnull=True)).count()
        online_count = assigned_devices.filter(last_location_time__gte=online_threshold).count()
        
        hierarchy.append({
            'name': f"{subuser.username} (You)",
            'role': 'Sub User',
            'initials': subuser.username[:2].upper(),
            'is_main': True,
            'devices': assigned_devices,
            'total_devices': total_count,
            'active_devices': active_count,
            'online_devices': online_count
        })
        
        all_devices = assigned_devices

    except SubUser.DoesNotExist:
        # Case 2: Customer (Admin) or Superuser
        try:
            customer = request.user.customer
            
            # 1. Main User (Customer) and their direct devices (not assigned to subusers? or just all unassigned?)
            # For simplicity, let's show all devices owned by customer under "Main User" if they are not assigned to subusers,
            # OR just show a "Direct Devices" node.
            # Let's follow the plan: Main User -> SubUsers -> Devices
            
            # Get all devices for customer
            customer_devices = Device.objects.filter(customer=customer, status='active').exclude(expires_at__lt=timezone.now())
            all_devices = customer_devices
            
            # Get all subusers for customer
            subusers = customer.sub_users.all()
            
            # Find devices assigned to ANY subuser
            assigned_device_ids = set()
            for su in subusers:
                assigned_device_ids.update(su.assigned_devices.values_list('id', flat=True))
            
            # Direct devices (not assigned to any subuser)
            direct_devices = customer_devices.exclude(id__in=assigned_device_ids)
            
            # Calculate device stats for main user
            online_threshold = timezone.now() - timedelta(minutes=10)
            total_count = direct_devices.count()
            active_count = direct_devices.exclude(Q(last_location_lat__isnull=True) | Q(last_location_lng__isnull=True)).count()
            online_count = direct_devices.filter(last_location_time__gte=online_threshold).count()
            
            # Add Main User node
            hierarchy.append({
                'name': f"{customer.first_name} {customer.last_name}",
                'role': 'Administrator',
                'initials': 'AD',
                'is_main': True,
                'devices': direct_devices,
                'total_devices': total_count,
                'active_devices': active_count,
                'online_devices': online_count
            })
            
            # Add SubUser nodes
            for su in subusers:
                su_devices = su.assigned_devices.filter(status='active').exclude(expires_at__lt=timezone.now())
                
                # Calculate device stats for each subuser
                su_total = su_devices.count()
                su_active = su_devices.exclude(Q(last_location_lat__isnull=True) | Q(last_location_lng__isnull=True)).count()
                su_online = su_devices.filter(last_location_time__gte=online_threshold).count()
                
                hierarchy.append({
                    'name': su.username,
                    'role': 'Sub User',
                    'initials': su.username[:2].upper(),
                    'is_main': False,
                    'devices': su_devices,
                    'total_devices': su_total,
                    'active_devices': su_active,
                    'online_devices': su_online
                })
                
        except AttributeError:
            # Superuser or user without customer profile
            all_devices = Device.objects.filter(status='active').exclude(expires_at__lt=timezone.now())
            
            # Calculate device stats for superuser
            online_threshold = timezone.now() - timedelta(minutes=10)
            total_count = all_devices.count()
            active_count = all_devices.exclude(Q(last_location_lat__isnull=True) | Q(last_location_lng__isnull=True)).count()
            online_count = all_devices.filter(last_location_time__gte=online_threshold).count()
            
            hierarchy.append({
                'name': request.user.username,
                'role': 'Super Admin',
                'initials': 'SA',
                'is_main': True,
                'devices': all_devices,
                'total_devices': total_count,
                'active_devices': active_count,
                'online_devices': online_count
            })

    # Get devices WITH GPS (for map display)
    devices_with_gps = all_devices.exclude(
        Q(last_location_lat__isnull=True) | Q(last_location_lng__isnull=True)
    )

    # Calculate statistics
    total_devices = all_devices.count()
    devices_with_gps_count = devices_with_gps.count()
    
    # Online = devices that sent data in last 10 minutes
    online_threshold = timezone.now() - timedelta(minutes=10)
    online_devices = all_devices.filter(last_location_time__gte=online_threshold).count()
    
    # Moving = speed > 5
    # We need to check latest location for speed. This is expensive for many devices.
    # Approximate by checking if last_location_time is recent AND speed in device model (if we stored it)
    # or just query LocationData.
    # For now, let's just count based on a simple assumption or leave it as is if we had it.
    # The previous code didn't calculate 'moving', 'alert'. Let's add basic counts.
    moving_devices = 0
    alert_devices = 0
    
    # Prepare device data for template (only devices with GPS for map)
    device_data = []
    for device in devices_with_gps:
        # Get latest location data for speed and heading
        latest_location = device.location_data.order_by('-timestamp').first()
        
        speed = latest_location.speed if latest_location else 0
        if speed > 5:
            moving_devices += 1
            
        # Simple alert logic (e.g. SOS or overspeed) - placeholder
        if device.status == 'alert':
            alert_devices += 1
        
        device_data.append({
            'id': device.id,
            'name': device.name,
            'imei': device.imei,
            'device_id': device.device_id,
            'lat': float(device.last_location_lat) if device.last_location_lat else None,
            'lng': float(device.last_location_lng) if device.last_location_lng else None,
            'last_update': device.last_location_time.isoformat() if device.last_location_time else None,
            'status': device.status,
            'battery_level': device.battery_level if device.battery_level else (latest_location.battery_level if latest_location else None),
            'speed': speed,
            'heading': latest_location.heading if latest_location else 0,
            'vehicle_type': device.vehicle_type,
            'driver_name': device.driver_name,
            'sim_card_number': device.sim_card_number,
            'model': device.model,
            'expires_at': device.expires_at.isoformat() if device.expires_at else None,
            'device_type': device.device_type.name if device.device_type else None,
        })

    # Generate JWT access token for WebSocket authentication
    from rest_framework_simplejwt.tokens import AccessToken
    access_token = AccessToken.for_user(request.user)

    context = {
        'hierarchy': hierarchy,
        'devices': devices_with_gps,
        'device_data_json': json.dumps(device_data, cls=DjangoJSONEncoder),
        'access_token': str(access_token),
        'total_devices': total_devices,
        'online_devices': online_devices,
        'moving_devices': moving_devices,
        'alert_devices': alert_devices,
        'gps_devices': devices_with_gps_count,
    }

    return render(request, 'gps_devices/map_v2.html', context)


@login_required
def device_markers_api(request):
    """
    API endpoint for device marker data
    """
    from apps.accounts.models import SubUser

    # Check if user is a sub-user
    try:
        subuser = SubUser.objects.get(username=request.user.username)
        # Sub-user: show only assigned devices with active subscriptions
        devices = subuser.assigned_devices.filter(
            status='active'
        ).exclude(
            Q(last_location_lat__isnull=True) | Q(last_location_lng__isnull=True)
        ).exclude(expires_at__lt=timezone.now())
    except SubUser.DoesNotExist:
        # Regular customer or admin
        try:
            customer = request.user.customer
            devices = Device.objects.filter(
                customer=customer,
                status='active'
            ).exclude(
                Q(last_location_lat__isnull=True) | Q(last_location_lng__isnull=True)
            ).exclude(expires_at__lt=timezone.now())
        except AttributeError:
            # Admin: show all active devices
            devices = Device.objects.filter(status='active').exclude(
                Q(last_location_lat__isnull=True) | Q(last_location_lng__isnull=True)
            ).exclude(expires_at__lt=timezone.now())

    markers = []
    for device in devices:
        # Get latest location data for speed and heading
        latest_location = device.location_data.order_by('-timestamp').first()
        
        markers.append({
            'id': device.id,
            'name': device.name,
            'imei': device.imei,
            'device_id': device.device_id,
            'lat': float(device.last_location_lat),
            'lng': float(device.last_location_lng),
            'last_update': device.last_location_time.isoformat() if device.last_location_time else None,
            'status': device.status,
            'battery_level': device.battery_level if device.battery_level else (latest_location.battery_level if latest_location else None),
            'speed': latest_location.speed if latest_location else 0,
            'heading': latest_location.heading if latest_location else 0,
            'vehicle_type': device.vehicle_type,
            'driver_name': device.driver_name,
            'device_type': device.device_type.name if device.device_type else None,
            'sim_card_number': device.sim_card_number,
            'model': device.model,
            'expires_at': device.expires_at.isoformat() if device.expires_at else None,
        })

    return JsonResponse({'markers': markers})
