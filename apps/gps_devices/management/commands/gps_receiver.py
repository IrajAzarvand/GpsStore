import socket
import threading
import logging
import re
import hashlib
import json
import sys
import os
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone as django_timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from apps.gps_devices.models import RawGpsData, Device, LocationData
from django.db import connections, close_old_connections
from django.contrib.auth import get_user_model
User = get_user_model()
# Add project root to path for importing Decoders
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))
from HQ_Decoder import HQFullDecoder
from GT06_Decoder import GT06Decoder
from JT808_Decoder import JT808Decoder
from apps.gps_devices.models import DeviceState, State

try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    mqtt = None

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Start GPS data receiver on port 5000'

    def handle(self, *args, **options):
        self.stdout.write('Starting GPS receiver on port 5000...')
        logger.info('GPS receiver command started successfully')
        try:
            server = GPSReceiver()
            server.start()
        except Exception as e:
            logger.error(f'Failed to start GPS receiver: {e}')
            self.stdout.write('Failed to start GPS receiver')

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    # Convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])

    # Haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371000 # Radius of earth in meters
    return c * r
    
class GPSReceiver:
    def __init__(self, host='0.0.0.0', port=5000, mqtt_broker='localhost', mqtt_port=1883):
        self.host = host
        self.port = port
        self.tcp_socket = None
        self.udp_socket = None
        self.mqtt_client = None
        self.mqtt_broker = mqtt_broker
        self.mqtt_port = mqtt_port
        self.rate_limit_cache = {}  # For security: track IP addresses
        self.hq_decoder = HQFullDecoder()
        self.gt06_decoder = GT06Decoder()
        self.jt808_decoder = JT808Decoder()
        # Limit max threads to prevent resource exhaustion
        self.thread_pool = ThreadPoolExecutor(max_workers=20, thread_name_prefix="GPS_Worker")

    def start(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_socket.bind((self.host, self.port))
        self.tcp_socket.listen(5)

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind((self.host, self.port))
        # Set timeout for UDP socket to allow periodic cleanup
        self.udp_socket.settimeout(5.0)

        logger.info(f'GPS receiver listening on {self.host}:{self.port} for TCP and UDP')

        tcp_thread = threading.Thread(target=self.tcp_listen)
        udp_thread = threading.Thread(target=self.udp_listen)
        mqtt_thread = threading.Thread(target=self.mqtt_listen)

        tcp_thread.start()
        udp_thread.start()
        mqtt_thread.start()

        try:
            tcp_thread.join()
            udp_thread.join()
            mqtt_thread.join()
        except KeyboardInterrupt:
            logger.info('Shutting down GPS receiver')
        finally:
            self.thread_pool.shutdown(wait=False)
            if self.tcp_socket:
                self.tcp_socket.close()
            if self.udp_socket:
                self.udp_socket.close()
            if self.mqtt_client:
                self.mqtt_client.disconnect()

    def tcp_listen(self):
        try:
            while True:
                try:
                    client_socket, address = self.tcp_socket.accept()
                    logger.info(f'TCP connection from {address}')
                    # Set timeout for client socket to prevent hanging connections
                    client_socket.settimeout(10.0)
                    
                    # Submit task to thread pool instead of creating new thread
                    self.thread_pool.submit(self.handle_client, client_socket, address)
                except OSError:
                    # Socket closed or error
                    break
        except Exception as e:
            logger.error(f'TCP listen error: {e}')

    def handle_client(self, client_socket, address):
        try:
            # Ensure we start with clean connections in this thread
            close_old_connections()
            
            try:
                # Receive raw bytes
                data = client_socket.recv(1024)
                if data:
                    print("RAW TCP DATA:", data.hex())

                    logger.info(f'Received TCP data from {address}: {data.hex()}')
                    
                    # Define callback for sending response
                    def send_response(response_data):
                        try:
                            client_socket.send(response_data)
                            logger.info(f'Sent response to {address}: {response_data.hex()}')
                        except Exception as e:
                            logger.error(f'Error sending response to {address}: {e}')

                    self.process_gps_data(data, address[0], 'tcp', reply_callback=send_response)
                    
            except socket.timeout:
                logger.warning(f'TCP connection timed out from {address}')
            except Exception as e:
                logger.error(f'Error reading from TCP client {address}: {e}')
        except Exception as e:
            logger.error(f'Error handling TCP client {address}: {e}')
        finally:
            try:
                client_socket.close()
            except Exception:
                pass
            # Explicitly close DB connection for this thread to prevent leaks
            connections.close_all()

    def udp_listen(self):
        try:
            while True:
                try:
                    # Ensure old connections are closed before blocking on recv
                    connections.close_all()
                    
                    data, addr = self.udp_socket.recvfrom(1024)
                    if data:
                        logger.info(f'Received UDP data from {addr}: {data.hex()}')
                        
                        # Define callback for sending response
                        def send_response(response_data):
                            try:
                                self.udp_socket.sendto(response_data, addr)
                                logger.info(f'Sent UDP response to {addr}: {response_data.hex()}')
                            except Exception as e:
                                logger.error(f'Error sending UDP response to {addr}: {e}')
                                
                        self.process_gps_data(data, addr[0], 'udp', reply_callback=send_response)
                except socket.timeout:
                    # Timeout allows loop to continue and clean up connections
                    continue
                except OSError:
                    break
        except Exception as e:
            logger.error(f'UDP listen error: {e}')

    def mqtt_listen(self):
        if not MQTT_AVAILABLE:
            logger.warning('MQTT library not available, skipping MQTT listener')
            return

        def on_connect(client, userdata, flags, rc):
            logger.info(f'Connected to MQTT broker with result code {rc}')
            client.subscribe('gps/data')

        def on_message(client, userdata, msg):
            # Ensure old connections are closed before processing
            connections.close_all()
            
            # MQTT payload is bytes
            data = msg.payload
            if data:
                logger.info(f'Received MQTT data on topic {msg.topic}: {data.hex()}')
                self.process_gps_data(data, None, 'mqtt')
            
            # Clean up after processing
            connections.close_all()

        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_message = on_message

        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_forever()
        except Exception as e:
            logger.error(f'MQTT connection error: {e}')


    def increment_consecutive_count(self, device, key, threshold=3):
        """
        Increment counter for given key, reset others.
        Returns True if threshold reached, False otherwise.
        """
        if not device.consecutive_count:
            device.consecutive_count = {}
        
        # Reset all other keys
        for k in list(device.consecutive_count.keys()):
            if k != key:
                device.consecutive_count[k] = 0
        
        # Increment target key
        device.consecutive_count[key] = device.consecutive_count.get(key, 0) + 1
        
        return device.consecutive_count[key] >= threshold


    def process_parsed_packet(self, device, parsed_data, ip_address, decoder_type, raw_data_hex, reply_callback=None):
        """Process a single parsed packet (V1, V0, SOS, V2, HB, JT808)"""
        packet_type = parsed_data.get('packet_type') or parsed_data.get('type')
        
        if packet_type == 'V0':
            # V0 (LBS Only) Packet
            logger.info(f'V0 (LBS) packet received for device {device.imei}')
            
            # Check if we have resolved coordinates
            if parsed_data.get('latitude') is not None and parsed_data.get('longitude') is not None:
                current_lat = float(parsed_data['latitude'])
                current_lon = float(parsed_data['longitude'])
                
                # Create LocationData with source='LBS'
                location_data = LocationData.objects.create(
                    device=device,
                    latitude=current_lat,
                    longitude=current_lon,
                    original_latitude=current_lat,
                    original_longitude=current_lon,
                    speed=0,
                    heading=0,
                    accuracy=parsed_data.get('accuracy_m') or 0,
                    location_source='LBS',
                    raw_data={
                        'protocol': decoder_type,
                        'ip_address': ip_address,
                        'raw_hex': raw_data_hex,
                        'packet_type': 'V0',
                        'mcc': parsed_data.get('mcc'),
                        'mnc': parsed_data.get('mnc'),
                        'lac': parsed_data.get('lac'),
                        'cid': parsed_data.get('cid'),
                        'resolved_via': parsed_data.get('location_resolved_via')
                    }
                )
                logger.info(f'Saved LBS LocationData for device {device.imei} (Source: {parsed_data.get("location_resolved_via")})')
                
                # Reset HB counter when other packet types received
                self.increment_consecutive_count(device, 'v0')
                device.save()

                # Broadcast update
                self.broadcast_device_update(device, speed=0, heading=0, location_data=location_data)
                
                # Delete RawGpsData
                RawGpsData.objects.filter(
                    ip_address=ip_address,
                    raw_data=raw_data_hex
                ).delete()
                logger.info(f'Deleted RawGpsData for V0 packet from {device.imei}')
            else:
                logger.warning(f'V0 packet from {device.imei} could not be resolved to coordinates. Keeping RawGpsData.')


        elif packet_type == 'SOS':
            # SOS Packet - Emergency Alarm
            logger.info(f'SOS packet received for device {device.imei}')
            
            if parsed_data.get('gps_valid'):
                current_speed = float(parsed_data.get('speed_kph') or parsed_data.get('speed', 0))
                current_lat = float(parsed_data['latitude'])
                current_lon = float(parsed_data['longitude'])
                
                location_data = LocationData.objects.create(
                    device=device,
                    latitude=current_lat,
                    longitude=current_lon,
                    original_latitude=current_lat,
                    original_longitude=current_lon,
                    speed=current_speed,
                    heading=parsed_data.get('course'),
                    accuracy=parsed_data.get('accuracy', 0),
                    is_alarm=True,
                    alarm_type='SOS',
                    raw_data={
                        'protocol': decoder_type,
                        'ip_address': ip_address,
                        'raw_hex': raw_data_hex,
                        'packet_type': 'SOS'
                    }
                )
                logger.info(f'Saved SOS LocationData for device {device.imei}')
                
                # Reset HB counter when other packet types received
                self.increment_consecutive_count(device, 'sos')
                device.save()
                
                # Broadcast update
                self.broadcast_device_update(device, speed=current_speed, heading=parsed_data.get('course'), location_data=location_data)
                
                # Delete RawGpsData
                RawGpsData.objects.filter(
                    ip_address=ip_address,
                    raw_data=raw_data_hex
                ).delete()
                logger.info(f'Deleted RawGpsData for SOS packet from {device.imei}')
            else:
                logger.warning(f'SOS packet from {device.imei} has invalid GPS. Keeping RawGpsData.')

        elif packet_type == 'V2':
            # V2 (Alarm/Status) Packet - No GPS coordinates
            logger.info(f'V2 (Alarm) packet received for device {device.imei}')
            
            # 1. Get last known location
            last_location = LocationData.objects.filter(device=device).order_by('-created_at').first()
            
            if last_location:
                # 2. Extract alarms
                alarm_info = parsed_data.get('alarm_info', {})
                active_alarms = [
                    info['name'] 
                    for key, info in alarm_info.items() 
                    if info.get('value')
                ]
                alarm_type_str = ', '.join(active_alarms) if active_alarms else 'Unknown Alarm'
                
                # 3. Create new LocationData with previous coordinates
                location_data = LocationData.objects.create(
                    device=device,
                    latitude=last_location.latitude,
                    longitude=last_location.longitude,
                    speed=last_location.speed,
                    heading=last_location.heading,
                    accuracy=last_location.accuracy,
                    location_source='LastKnown',
                    is_alarm=True,
                    alarm_type=alarm_type_str,
                    raw_data={
                        'protocol': decoder_type,
                        'ip_address': ip_address,
                        'raw_hex': raw_data_hex,
                        'packet_type': 'V2',
                        'alarms': active_alarms
                    }
                )
                logger.info(f'Saved V2 Alarm ({alarm_type_str}) for device {device.imei} using last known location')
                
                # Reset HB counter when other packet types received
                self.increment_consecutive_count(device, 'v2')
                device.save()
                
                # Broadcast update
                self.broadcast_device_update(device, speed=last_location.speed, heading=last_location.heading, location_data=location_data)
                
                # Delete RawGpsData
                RawGpsData.objects.filter(
                    ip_address=ip_address,
                    raw_data=raw_data_hex
                ).delete()
            else:
                logger.warning(f'Received V2 packet for {device.imei} but no previous location found. Cannot save alarm.')

        elif packet_type == 'HB':
            # Heartbeat - delete old HBs, save new one without coordinates
            logger.info(f'Heartbeat received for device {device.imei}')
            # Delete all previous HB records for this device
            LocationData.objects.filter(device=device, packet_type='HB').delete()
            
            # Extract HB data
            voltage = parsed_data.get('voltage_v')
            signal = parsed_data.get('signal_strength')
            # Save new HB without coordinates
            LocationData.objects.create(
                device=device,
                latitude=None,
                longitude=None,
                packet_type='HB',
                speed=0,
                battery_level=int(voltage * 1000) if voltage else None,
                signal_strength=signal or 0,
                raw_data={
                    'protocol': decoder_type,
                    'ip_address': ip_address,
                    'raw_hex': raw_data_hex,
                    'packet_type': 'HB'
                }
            )
            # Update counter and check for Idle state
            if self.increment_consecutive_count(device, 'HB'):
                idle_state, _ = State.objects.get_or_create(name='Idle')
                DeviceState.objects.create(
                    device=device,
                    state=idle_state,
                    location_data=None
                )
                device.consecutive_count['HB'] = 0
                logger.info(f'Device {device.imei} transitioned to Idle state (3 consecutive HBs)')
            
            device.save()
            # Delete RawGpsData
            RawGpsData.objects.filter(
                ip_address=ip_address,
                raw_data=raw_data_hex
            ).delete()
            logger.info(f'Saved HB and deleted RawGpsData for {device.imei}')

        elif packet_type == 'V1' or packet_type == 'GT06': 
            # GPS location packet
            if parsed_data.get('gps_valid'):
                
                # --- NEW LOGIC START ---
                from apps.gps_devices.models import DeviceState, State
                
                # Get speed - HQ decoder returns speed_kph, but fallback to 'speed' field
                current_speed = float(parsed_data.get('speed_kph') or parsed_data.get('speed', 0))
                current_lat = float(parsed_data['latitude'])
                current_lon = float(parsed_data['longitude'])
                
                # Get last DeviceState and LocationData
                last_device_state = DeviceState.objects.filter(device=device).order_by('-timestamp').first()
                last_location = LocationData.objects.filter(device=device).order_by('-created_at').first()
                # Determine if we should save LocationData
                should_save_location = True
                
                # Smart Movement Detection Logic
                # 1. Calculate distance from last location
                distance = 0.0
                if last_location:
                    last_lat = float(last_location.latitude)
                    last_lon = float(last_location.longitude)
                    distance = haversine_distance(current_lat, current_lon, last_lat, last_lon)

                # 2. Check ACC status (if available)
                acc_on = parsed_data.get('acc_on')
                
                # 3. Apply Logic
                if acc_on is False: # ACC is explicitly OFF
                    if distance <= 5.0:
                        # ACC Off + No significant movement = Parked
                        current_speed = 0.0
                        should_save_location = False # Optional: skip saving if completely static
                        logger.info(f"Device {device.imei}: ACC Off + Dist {distance:.1f}m -> Forced Stop")
                    else:
                        # ACC Off + Significant movement = Moving (Faulty ACC wiring?)
                        # Trust the GPS speed
                        should_save_location = True
                        logger.info(f"Device {device.imei}: ACC Off + Dist {distance:.1f}m -> Moving (Faulty ACC?)")
                
                if current_speed == 0 and distance < 5.0:
                    if self.increment_consecutive_count(device, 'stopped'):
                        stopped_state, _ = State.objects.get_or_create(name='Stopped')
                        DeviceState.objects.create(device=device, state=stopped_state, location_data=location_data)
                        device.consecutive_count['stopped'] = 0
                else:
                    if self.increment_consecutive_count(device, 'moving'):
                        moving_state, _ = State.objects.get_or_create(name='Moving')
                        DeviceState.objects.create(device=device, state=moving_state, location_data=location_data)
                        device.consecutive_count['moving'] = 0
                device.save()

                # Determine if we should save DeviceState (state change)
                should_save_state = False
                state_name = None

                if not last_device_state:
                    # First time - save state
                    should_save_state = True
                    state_name = 'Moving' if current_speed > 0 else 'Stopped'
                    logger.info(f"First state for device {device.imei}: {state_name}")
                else:
                    last_state_name = last_device_state.state.name
                    
                    # Check for Moving -> Stopped transition
                    if last_state_name == 'Moving' and current_speed == 0:
                        # Get 2 most recent locations (not including current)
                        recent_locations = LocationData.objects.filter(
                            device=device
                        ).order_by('-created_at')[:2]
                        
                        # Count zero speeds in previous 2 records
                        previous_zero_count = sum(1 for loc in recent_locations if loc.speed == 0)
                        
                        # Current speed is 0, so total zero count = 1 (current) + previous_zero_count
                        total_zero_count = 1 + previous_zero_count
                        
                        if total_zero_count >= 3:  # Current + 2 previous all zero
                            should_save_state = True
                            state_name = 'Stopped'
                            logger.info(f"State change for {device.imei}: Moving -> Stopped (3 consecutive zero speeds)")                        
                    # Check for Stopped -> Moving transition
                    elif last_state_name == 'Stopped' and current_speed > 0:
                        if last_location:
                            last_lat = float(last_location.latitude)
                            last_lon = float(last_location.longitude)
                            distance = haversine_distance(current_lat, current_lon, last_lat, last_lon)
                            
                            if distance > 5.0:  # Moved more than 5 meters
                                should_save_state = True
                                state_name = 'Moving'
                                logger.info(f"State change for {device.imei}: Stopped -> Moving (speed > 0, distance: {distance:.2f}m)")
                
                # Save LocationData if needed
                location_data = None
                if should_save_location:
                    # ذخیره مختصات اصلی
                    original_lat = current_lat
                    original_lon = current_lon
                    
                    # اعمال Map Matching
                    matched_lat = current_lat
                    matched_lon = current_lon
                    is_map_matched = False
                    matched_geometry = None
                    
                    try:
                        from apps.gps_devices.services import MapMatchingService
                        
                        # فقط برای دستگاه‌های در حال حرکت Map Matching اعمال می‌شود
                        if current_speed > 0:
                            # دریافت 9 نقطه آخر برای Map Matching
                            recent_locations = LocationData.objects.filter(
                                device=device
                            ).order_by('-created_at')[:9]  # 9 نقطه قبلی + نقطه فعلی = 10
                            
                            # ساخت لیست نقاط
                            points = [(float(original_lat), float(original_lon))]
                            for loc in reversed(list(recent_locations)):
                                points.insert(0, (float(loc.latitude), float(loc.longitude)))
                            
                            # فراخوانی Map Matching اگر حداقل 2 نقطه داریم
                            if len(points) >= 2:
                                logger.info(f"Attempting map matching for device {device.imei} with {len(points)} points")
                                map_matching_service = MapMatchingService()
                                result = map_matching_service.match_points(points, use_cache=True)
                                
                                if result and 'snappedPoints' in result:
                                    # استفاده از آخرین نقطه تصحیح شده
                                    snapped_points = result['snappedPoints']
                                    if snapped_points:
                                        last_snapped = snapped_points[-1]
                                        location = last_snapped.get('location', {})
                                        matched_lat = location.get('latitude', current_lat)
                                        matched_lon = location.get('longitude', current_lon)
                                        is_map_matched = True
                                        matched_geometry = map_matching_service.get_geometry(result)
                                        logger.info(f'Map matched coordinates for device {device.imei}: ({original_lat}, {original_lon}) -> ({matched_lat}, {matched_lon})')
                                    else:
                                        logger.warning(f"Map matching returned result but no snappedPoints for {device.imei}")
                                else:
                                    logger.warning(f"Map matching failed or returned no result for {device.imei}. Result: {result}")
                            else:
                                logger.info(f"Skipping map matching for {device.imei}: Not enough points ({len(points)})")
                        else:
                            logger.info(f"Skipping map matching for {device.imei}: Speed is 0")
                    except Exception as e:
                        logger.error(f'Map matching failed for device {device.imei}: {e}', exc_info=True)
                        # در صورت خطا، از مختصات اصلی استفاده می‌شود

                    location_data = LocationData.objects.create(
                        device=device,
                        latitude=matched_lat,  # مختصات تصحیح شده
                        longitude=matched_lon,  # مختصات تصحیح شده
                        original_latitude=original_lat,  # مختصات اصلی
                        original_longitude=original_lon,  # مختصات اصلی
                        is_map_matched=is_map_matched,
                        matched_geometry=matched_geometry,
                        speed=current_speed,
                        heading=parsed_data.get('course'),
                        accuracy=parsed_data.get('accuracy', 0),
                        battery_level=parsed_data.get('battery_level'),
                        satellites=parsed_data.get('satellites', 0),
                        raw_data={
                            'protocol': decoder_type,
                            'ip_address': ip_address,
                            'raw_hex': data.hex()
                        }
                    )
                    logger.info(f'Saved LocationData for device {device.imei}')
                
                # Save DeviceState if state changed
                if should_save_state and state_name:
                    state_obj, _ = State.objects.get_or_create(name=state_name)
                    DeviceState.objects.create(
                        device=device,
                        state=state_obj,
                        location_data=location_data or last_location  # Use new or last location
                    )
                    logger.info(f'Saved DeviceState for device {device.imei}: {state_name}')
                
                # Broadcast update if we saved location data
                if should_save_location:
                    self.broadcast_device_update(device, speed=current_speed, heading=parsed_data.get('course'), location_data=location_data)

                # فقط اگر LocationData ذخیره شد، RawGpsData را حذف کن
                if should_save_location and location_data:
                    RawGpsData.objects.filter(
                        ip_address=ip_address,
                        raw_data=data.hex()
                    ).delete()
                    logger.info(f'Deleted RawGpsData for device {device.imei} after successful save')
                else:
                    logger.info(f'Kept RawGpsData for device {device.imei} - LocationData was not saved')
                
                # --- NEW LOGIC END ---
                
            else:
                logger.info(f'GPS invalid for device {device.imei}')

        elif packet_type == 'JT808':
            # JT808 Protocol - Chinese Standard GPS Tracker
            logger.info(f'JT808 packet received for device {device.imei}')
            
            # نمایش ساختار کامل parsed_data برای تحلیل
            logger.info(f'JT808 parsed_data structure: {json.dumps(parsed_data, indent=2, default=str)}')

            # بررسی معتبر بودن GPS
            if parsed_data.get('gps_valid'):
                # استخراج اطلاعات
                current_speed = float(parsed_data.get('speed_kph') or parsed_data.get('speed', 0))
                current_lat = float(parsed_data.get('latitude'))
                current_lon = float(parsed_data.get('longitude'))
    
                # ذخیره LocationData
                location_data = LocationData.objects.create(
                    device=device,
                    latitude=current_lat,
                    longitude=current_lon,
                    original_latitude=current_lat,
                    original_longitude=current_lon,
                    speed=current_speed,
                    heading=parsed_data.get('course') or parsed_data.get('heading', 0),
                    altitude=parsed_data.get('altitude', 0),
                    accuracy=parsed_data.get('accuracy', 0),
                    satellites=parsed_data.get('satellites', 0),
                    signal_strength=parsed_data.get('signal_strength', 0),
                    battery_level=parsed_data.get('battery_level'),
                    raw_data={
                        'protocol': decoder_type,
                        'ip_address': ip_address,
                        'raw_hex': raw_data_hex,
                        'packet_type': 'JT808'
                    }
                )
                logger.info(f'Saved JT808 LocationData for device {device.imei}')
    
                # Reset HB counter when other packet types received
                self.increment_consecutive_count(device, 'jt808')
                device.save()
                
                # Broadcast به WebSocket
                self.broadcast_device_update(
                    device, 
                    speed=current_speed, 
                    heading=parsed_data.get('course') or parsed_data.get('heading', 0),
                    location_data=location_data
                )
    
                # حذف RawGpsData بعد از ذخیره موفق
                RawGpsData.objects.filter(
                    ip_address=ip_address,
                    raw_data=raw_data_hex
                ).delete()
                logger.info(f'Deleted RawGpsData for JT808 packet from {device.imei}')
            else:
                logger.warning(f'JT808 packet from {device.imei} has invalid GPS, keeping RawGpsData')















    def process_gps_data(self, data, ip_address, protocol_type, reply_callback=None):
        """
        Process GPS data: parse, validate, check device, save to LocationData
        Data is expected to be bytes.
        reply_callback: function(bytes) -> None, used to send response back to device
        """
        try:
            # Security check
            security_result = self.check_security(ip_address, data)
            if security_result != 'safe':
                # Log and save as blocked/rejected
                self.save_raw_data(data, ip_address, protocol_type, status='rejected', error_message=f'Security check failed: {security_result}')
                return

            # Protocol Sniffing
            decoded = None
            decoder_type = None
            
            # Check for JT808 (Start byte 0x7E)
            if len(data) >= 2 and data[0] == 0x7E:
                logger.info(f'Detected JT808 Protocol from {ip_address}')
                decoded = self.jt808_decoder.decode(data)
                decoder_type = 'JT808'
            
            # Check for GT06 Binary (Start bytes 0x78 0x78)
            elif len(data) >= 2 and data[0] == 0x78 and data[1] == 0x78:
                logger.info(f'Detected GT06 Binary Protocol from {ip_address}')
                decoded = self.gt06_decoder.decode(data)
                decoder_type = 'GT06'
            
            # Check for HQ Text (Starts with *)
            elif len(data) >= 1 and data[0] == 0x2A: # 0x2A is '*'
                logger.info(f'Detected HQ Text Protocol from {ip_address}')
                try:
                    text_data = data.decode('utf-8', errors='ignore').strip()
                    decoded = self.hq_decoder.decode(text_data)
                    decoder_type = 'HQ'
                except Exception as e:
                    decoded = {"error": f"Text decoding failed: {str(e)}"}
            
            else:
                logger.warning(f'Unknown protocol from {ip_address}: {data.hex()}')
                self.save_raw_data(data, ip_address, protocol_type, status='pending', error_message='Unknown protocol')
                return

            if "error" in decoded:
                logger.warning(f'Decoding failed: {decoded["error"]}')
                self.save_raw_data(data, ip_address, protocol_type, status='pending', error_message=decoded["error"])
                return

            # Common processing logic
            parsed_data = decoded # Decoders should return compatible dicts
            
            # Handle Response (e.g. JT808 Registration Handshake)
            if "response" in parsed_data and reply_callback:
                logger.info(f'Sending response for {decoder_type} packet')
                reply_callback(parsed_data["response"])
            
            # Find device by device_id (IMEI)
            device_id = parsed_data.get('imei') or parsed_data.get('device_id')
            if not device_id:
                self.save_raw_data(data, ip_address, protocol_type, error_message='No Device ID found')
                return

            try:
                device = Device.objects.get(imei=device_id)
            except Device.DoesNotExist:
                # Device not registered - automatically create it and assign to admin
                try:
                    # Get first superuser as default owner
                    admin_user = User.objects.filter(is_superuser=True).first()
                    if not admin_user:
                        logger.error(f'No superuser found to assign device {device_id}')
                        self.save_raw_data(data, ip_address, protocol_type, error_message='No admin user available')
                        return
                    
                    # Get or create a default Model for unknown devices
                    from apps.gps_devices.models import Model

                    # Map decoder_type to model info
                    protocol_model_map = {
                        'HQ': {
                            'model_name': 'HQ TR02',
                            'manufacturer': 'Huabao',
                            'protocol_type': 'TCP',
                            'description': 'HQ Text Protocol GPS Tracker'
                        },
                        'GT06': {
                            'model_name': 'GT06',
                            'manufacturer': 'Concox',
                            'protocol_type': 'TCP',
                            'description': 'GT06 Binary Protocol GPS Tracker'
                        },
                        'JT808': {
                            'model_name': 'JT808',
                            'manufacturer': 'Generic',
                            'protocol_type': 'TCP',
                            'description': 'JT808 Protocol GPS Tracker (Chinese Standard)'
                        }
                    }

                    # Get model info based on detected protocol
                    model_info = protocol_model_map.get(decoder_type, {
                        'model_name': 'Unknown',
                        'manufacturer': 'Unknown',
                        'protocol_type': 'TCP',
                        'description': 'Auto-created for unregistered devices'
                    })

                    # Get or create model
                    default_model, created = Model.objects.get_or_create(
                        model_name=model_info['model_name'],
                        manufacturer=model_info['manufacturer'],
                        defaults={
                            'protocol_type': model_info['protocol_type'],
                            'description': model_info['description']
                        }
                    )

                    if created:
                        logger.info(f'Created new model: {model_info["manufacturer"]} {model_info["model_name"]} ({decoder_type})')
                    device = Device.objects.create(
                        imei=device_id,
                        name=f'{device_id}',
                        owner=admin_user,
                        model=default_model,  # حالا مدل صحیح استفاده می‌شود
                        status='active'
                    )
                    logger.info(f'Automatically created device {device.imei} with model {default_model.model_name} and assigned to admin')

                except Exception as e:
                    logger.error(f'Failed to auto-create device {device_id}: {e}')
                    self.save_raw_data(data, ip_address, protocol_type, error_message=f'Auto-create failed: {str(e)}')
                    return

            # Check if device is active
            if device.status != 'active':
                self.save_raw_data(data, ip_address, protocol_type, device=device, error_message=f'Device not active (status: {device.status})')
                return

            packet_type = parsed_data.get('packet_type') or parsed_data.get('type')

            # Handle UPLOAD packets (batch upload)
            if packet_type == 'UPLOAD':
                logger.info(f'UPLOAD packet received from {device.imei} with {len(parsed_data.get("records", []))} records')
                
                records = parsed_data.get('records', [])
                for record in records:
                    # Filter out invalid records
                    rec_type = record.get('type')
                    if rec_type in ['V1', 'V0', 'SOS', 'V2', 'HB', 'JT808']:
                        # Ensure packet_type is set
                        if not record.get('packet_type'):
                            record['packet_type'] = rec_type
                        
                        # Get raw data for this record if available
                        rec_raw = record.get('raw') or record.get('raw_sub') or data.hex()
                        
                        self.process_parsed_packet(
                            device, 
                            record, 
                            ip_address, 
                            decoder_type, 
                            rec_raw, 
                            reply_callback
                        )
                
            else:
                # حالت عادی (تک پکت)
                self.process_parsed_packet(
                    device, 
                    parsed_data, 
                    ip_address, 
                    decoder_type, 
                    data.hex(), 
                    reply_callback
                )


                # After processing all records, send reply if needed
                if reply_callback and decoder_type == 'HQ':
                    try:
                        response = bytes.fromhex('2a48512c3030303030303030303030302c56312c3030303030302c412c302e3030303030302c4e2c302e3030303030302c452c302e30302c302c3030303030302c46464646464646462c3030302c30302c303030302c303030302c232a')
                        reply_callback(response)
                    except Exception as e:
                        logger.error(f'Error sending UPLOAD response: {e}')
                
                return


# *****************************************
# *****************************************
# *****************************************
# *****************************************
# *****************************************
# *****************************************
# *****************************************


        


        except Exception as e:
            logger.error(f'Error processing GPS data: {e}')
            self.save_raw_data(data, ip_address, protocol_type, error_message=str(e))

    def check_security(self, ip_address, data):
        """
        Security checks: rate limiting and malicious/suspicious data detection
        Returns: 'safe' | 'suspicious' | 'malicious' | 'rate_limited'
        """
        from datetime import datetime, timedelta

        current_time = datetime.now()

        # Rate limiting: max 20 requests per minute per IP
        if ip_address not in self.rate_limit_cache:
            self.rate_limit_cache[ip_address] = []

        # Clean old entries
        self.rate_limit_cache[ip_address] = [
            t for t in self.rate_limit_cache[ip_address]
            if current_time - t < timedelta(minutes=1)
        ]

        # Check rate limit
        if len(self.rate_limit_cache[ip_address]) >= 20:
            return 'rate_limited'

        self.rate_limit_cache[ip_address].append(current_time)

        # Enhanced malicious data detection
        if len(data) > 2000:  # Too long
            return 'malicious'

        # For binary data, skip text-based pattern matching
        
        # JT808 (Start byte 0x7E)
        if len(data) >= 2 and data[0] == 0x7E:
            return 'safe'

        # GT06 (Start bytes 0x78 0x78)
        if len(data) >= 2 and data[0] == 0x78 and data[1] == 0x78:
            return 'safe'
            
        # If it looks like HQ Text (starts with *), do text checks
        if len(data) >= 1 and data[0] == 0x2A:
            try:
                text_data = data.decode('utf-8', errors='ignore').lower()
                malicious_patterns = ['<script', 'eval(', 'system(', 'drop table']
                if any(pattern in text_data for pattern in malicious_patterns):
                    return 'malicious'
                return 'safe'
            except:
                pass

        # Unknown format
        return 'suspicious'

    
    def broadcast_device_update(self, device, speed=0, heading=0, location_data=None):
        """
        Broadcast device location update to WebSocket clients
        """
        try:
            channel_layer = get_channel_layer()
            
            last_update = None
            lat = None
            lng = None
            
            # 1. Try to get data from the provided location_data
            if location_data:
                lat = float(location_data.latitude)
                lng = float(location_data.longitude)
                if location_data.created_at:
                     last_update = location_data.created_at.isoformat()
            
            # 2. Fallback: Query the latest LocationData from DB if not provided
            if lat is None or lng is None:
                latest_loc = LocationData.objects.filter(device=device).order_by('-created_at').first()
                if latest_loc:
                    lat = float(latest_loc.latitude)
                    lng = float(latest_loc.longitude)
                    if latest_loc.created_at:
                        last_update = latest_loc.created_at.isoformat()

            # 3. Default time if still missing
            if not last_update:
                from datetime import datetime, timezone
                last_update = datetime.now(timezone.utc).isoformat()

            device_data = {
                'id': device.id,
                'name': device.name,
                'imei': device.imei,
                'device_id': device.imei,
                'lat': lat,
                'lng': lng,
                'last_update': last_update,
                'status': device.status,
                'battery_level': getattr(location_data, 'battery_level', 0) if location_data else 0,
                'speed': float(speed) if speed is not None else 0,
                'heading': float(heading) if heading is not None else 0,
                'accuracy': getattr(location_data, 'accuracy', 0) if location_data else 0,
                'satellites': getattr(location_data, 'satellites', 0) if location_data else 0,
                'signal_strength': getattr(location_data, 'signal_strength', 0) if location_data else 0,
                'matched_geometry': getattr(location_data, 'matched_geometry', None) if location_data else None,
                'is_alarm': getattr(location_data, 'is_alarm', False) if location_data else False,
                'alarm_type': getattr(location_data, 'alarm_type', '') if location_data else '',           
            }

            # Send to admins group (they see all devices)
            async_to_sync(channel_layer.group_send)(
                'admins_group',
                {
                    'type': 'device_update',
                    'data': device_data
                }
            )
            
            # Send to device owner's personal group
            if device.owner:
                async_to_sync(channel_layer.group_send)(
                    f'user_group_{device.owner.id}',
                    {
                        'type': 'device_update',
                        'data': device_data
                    }
                )

        except Exception as e:
            logger.error(f'Error broadcasting device update: {e}')

    def save_raw_data(self, data, ip_address, protocol_type, device=None, status='pending', processed=False, error_message='', unknown_sections=None):
        """
        Save raw GPS data with processing status
        """
        try:
            # Convert bytes to hex string for storage if it's binary
            if isinstance(data, bytes):
                try:
                    raw_data_str = data.decode('utf-8')
                except:
                    raw_data_str = data.hex()
            else:
                raw_data_str = str(data)

           

            # Save raw data (without protocol reference)
            raw_data = RawGpsData.objects.create(
                raw_data=raw_data_str,
                ip_address=ip_address,
                device=device,
                status=status,
                error_message=error_message,
            )
            return raw_data
        except Exception as e:
            logger.error(f'Error saving raw data: {e}')
            return None