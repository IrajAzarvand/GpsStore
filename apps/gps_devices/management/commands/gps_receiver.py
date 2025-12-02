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
                    default_model, _ = Model.objects.get_or_create(
                        model_name='Unknown',
                        defaults={
                            'manufacturer': 'Unknown',
                            'protocol_type': 'TCP',
                            'description': 'Auto-created for unregistered devices'
                        }
                    )
                    
                    device = Device.objects.create(
                        imei=device_id,
                        name=f'{device_id}',
                        owner=admin_user,
                        model=default_model,
                        status='active'
                    )
                    logger.info(f'Automatically created device {device.imei} and assigned to admin')
                except Exception as e:
                    logger.error(f'Failed to auto-create device {device_id}: {e}')
                    self.save_raw_data(data, ip_address, protocol_type, error_message=f'Auto-create failed: {str(e)}')
                    return

            # Check if device is active
            if device.status != 'active':
                self.save_raw_data(data, ip_address, protocol_type, device=device, error_message=f'Device not active (status: {device.status})')
                return

            packet_type = parsed_data.get('packet_type') or parsed_data.get('type')

            if packet_type == 'V1' or packet_type == 'GT06': 
                # GPS location packet
                if parsed_data.get('gps_valid'):
                    
                    # --- NEW LOGIC START ---
                    from apps.gps_devices.models import DeviceState, State
                    
                    # Get speed - HQ decoder returns speed_kph, but fallback to 'speed' field
                    current_speed = float(parsed_data.get('speed_kph') or parsed_data.get('speed', 0))
                    current_lat = float(parsed_data['latitude'])
                    current_lon = float(parsed_data['longitude'])
                    
                    # Determine current state
                    # Assuming 'Moving' if speed > 0, else 'Stopped'
                    state_name = 'Moving' if current_speed > 0 else 'Stopped'
                    
                    # Get or create State object
                    state_obj, _ = State.objects.get_or_create(name=state_name)
                    
                    # Get last DeviceState
                    last_device_state = DeviceState.objects.filter(device=device).order_by('-timestamp').first()
                    
                    should_update = False
                    
                    if not last_device_state:
                        # First time seeing this device state
                        should_update = True
                        logger.info(f"First state for device {device.imei}")
                    else:
                        last_speed = last_device_state.location_data.speed if last_device_state.location_data else 0
                        last_state_name = last_device_state.state.name
                        
                        # Check for state change or speed change
                        # Note: You might want a threshold for speed change to avoid jitter
                        if last_state_name != state_name:
                            should_update = True
                            logger.info(f"State changed for {device.imei}: {last_state_name} -> {state_name}")
                        elif abs(current_speed - last_speed) > 1.0: # 1 km/h threshold for speed change
                             should_update = True
                             logger.info(f"Speed changed for {device.imei}: {last_speed} -> {current_speed}")
                        else:
                            # Check distance
                            if last_device_state.location_data:
                                last_lat = float(last_device_state.location_data.latitude)
                                last_lon = float(last_device_state.location_data.longitude)
                                distance = haversine_distance(current_lat, current_lon, last_lat, last_lon)
                                
                                if distance > 5.0: # 5 meters threshold
                                    should_update = True
                                    logger.info(f"Distance changed for {device.imei}: {distance:.2f}m")
                    
                    if should_update:
                        location_data = LocationData.objects.create(
                            device=device,
                            latitude=parsed_data['latitude'],
                            longitude=parsed_data['longitude'],
                            speed=current_speed,  # Already converted to km/h
                            heading=parsed_data.get('course'),
                            battery_level=parsed_data.get('battery_level'),
                            satellites=parsed_data.get('satellites', 0),
                            raw_data={
                                'protocol': decoder_type,
                                'ip_address': ip_address,
                                'raw_hex': data.hex()
                            }
                        )
                        
                        # Create DeviceState
                        DeviceState.objects.create(
                            device=device,
                            state=state_obj,
                            location_data=location_data
                        )

                        # Broadcast update
                        self.broadcast_device_update(device, speed=current_speed, heading=parsed_data.get('course'), location_data=location_data)

                        logger.info(f'Saved location data and state for device {device.imei}')
                    else:
                        logger.info(f'Skipping update for device {device.imei} - no significant change')

                    # Successfully processed - delete raw data to avoid redundancy
                    # We delete it even if we skipped saving LocationData, because it was "processed"
                    RawGpsData.objects.filter(
                        ip_address=ip_address,
                        raw_data=data.hex()
                    ).delete()
                    
                    # --- NEW LOGIC END ---
                    
                else:
                    logger.info(f'GPS invalid for device {device.imei}')

            elif packet_type == 'HB':
                # Heartbeat - just log it
                logger.info(f'Heartbeat received for device {device.imei}')
                
            # Delete raw data for registered device to save space
            RawGpsData.objects.filter(device=device).delete()

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
            }

            async_to_sync(channel_layer.group_send)(
                f'device_{device.id}',
                {
                    'type': 'device_update',
                    'device': device_data
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