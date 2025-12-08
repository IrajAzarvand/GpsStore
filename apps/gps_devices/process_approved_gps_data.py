import logging
import sys
import os
from datetime import datetime, timezone
from django.core.management.base import BaseCommand
from apps.gps_devices.models import RawGpsData, Device, LocationData
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

# Add project root to path for importing HQ_Decoder
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../..'))
from HQ_Decoder import HQFullDecoder

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process approved GPS data that requires admin confirmation'

    def handle(self, *args, **options):
        self.stdout.write('Processing approved GPS data...')

        # Instantiate HQFullDecoder
        self.decoder = HQFullDecoder()

        # Get all approved but not processed data
        approved_data = RawGpsData.objects.filter(status__in=['approved', 'registered'], processed=False)

        processed_count = 0
        for raw_data in approved_data:
            try:
                self.process_raw_data(raw_data)
                processed_count += 1
            except Exception as e:
                logger.error(f'Error processing approved data {raw_data.id}: {e}')
                raw_data.mark_error(str(e))

        self.stdout.write(f'Successfully processed {processed_count} approved GPS data entries.')

    def process_raw_data(self, raw_data):
        """
        Process a single raw GPS data entry
        """
        # Decode the data using HQDecoder
        decoded = self.decoder.decode(raw_data.raw_data)
        parsed_data = self.convert_decoded_to_parsed(decoded)
        if not parsed_data:
            raw_data.mark_error('Failed to decode GPS data')
            return

        # Find device
        try:
            device = Device.objects.get(imei=parsed_data['device_id'])
        except Device.DoesNotExist:
            raw_data.mark_error(f'Unregistered device {parsed_data["device_id"]}')
            return

        # Check if device is active
        if device.status != 'active':
            raw_data.mark_error(f'Device not active (status: {device.status})')
            return

        packet_type = parsed_data.get('packet_type')

        if packet_type == 'V1':
            # GPS location packet
            location_data = LocationData.objects.create(
                device=device,
                latitude=parsed_data['latitude'],
                longitude=parsed_data['longitude'],
                speed=parsed_data['speed'],
                heading=parsed_data['heading'],
                timestamp=parsed_data['timestamp'],
                battery_level=None,  # V1 packets do not contain voltage
                raw_data={
                    'device_id': parsed_data['device_id'],
                    'validity': parsed_data['validity'],
                    'status': parsed_data['status'],
                    'mcc': parsed_data['mcc'],
                    'mnc': parsed_data['mnc'],
                    'lac': parsed_data['lac'],
                    'cid': parsed_data['cid'],
                    'protocol': 'HQ',
                    'ip_address': raw_data.ip_address
                }
            )

            # Broadcast device update
            self.broadcast_device_update(device)

        elif packet_type == 'V0':
            # LBS packet - just log it
            logger.info(f'LBS packet received for device {device.imei}')

        elif packet_type == 'V2':
            # Alarm/Status packet - log and broadcast alert
            alarm = parsed_data.get('alarm')
            logger.info(f'Alarm packet received for device {device.imei}: {alarm}')
            # Broadcast alert status
            self.broadcast_device_update(device, status_override='alert')

        elif packet_type == 'HB':
            # Heartbeat packet - log and broadcast
            logger.info(f'Heartbeat received for device {device.imei}')
            # Broadcast idle status
            self.broadcast_device_update(device, status_override='idle')

        elif packet_type == 'UPLOAD':
            # Multi-record packet - process each record
            records = parsed_data.get('records', [])
            for record in records:
                # Each record is like {"type": "V1_raw", "raw": "..."}
                if record.get('type') == 'V1_raw':
                    raw_record = record.get('raw')
                    if raw_record:
                        # Recursively process the record
                        self.process_gps_data(raw_record, raw_data.ip_address, 'HQ')
            logger.info(f'Processed {len(records)} records from UPLOAD packet for device {device.imei}')

        # Mark as processed
        raw_data.mark_processed()

    def parse_gps_data(self, data):
        """
        Parse GPS data in format: *HQ,IMEI,V1,time,validity,lat,N,lon,E,speed,direction,date,status,mcc,mnc,lac,cid,checksum#
        """
        logger.info(f'Parsing GPS data: {data}')
        try:
            # Remove * and # if present
            if data.startswith('*'):
                data = data[1:]
            if data.endswith('#'):
                data = data[:-1]
            logger.info(f'Cleaned GPS data: {data}')

            # Split by comma
            parts = data.split(',')
            logger.info(f'Split into {len(parts)} parts: {parts}')
            if len(parts) < 16:
                logger.error(f'Insufficient parts: {len(parts)}, expected 16+, data: {data}')
                return None

            if len(parts) >= 17:
                parts = parts[:17]
            else:
                parts = parts[:16]

            # Extract fields
            if len(parts) == 17:
                header, device_id, v1, time_str, validity, lat_str, lat_dir, lon_str, lon_dir, speed_str, direction_str, date_str, status, mcc_str, mnc_str, lac_str, cid_str = parts
            else:
                header, device_id, v1, time_str, validity, lat_str, lat_dir, lon_str, lon_dir, speed_str, direction_str, date_str, status, mcc_str, mnc_str, lac_str = parts
                cid_str = None

            # Validate header
            if header != 'HQ':
                logger.error(f'Invalid header: {header}, expected HQ, data: {data}')
                return None

            # Parse coordinates from DDMM.MMMM format
            # Latitude: DDMM.MMMM -> degrees + minutes/60
            try:
                lat_deg = int(lat_str[:2])
                lat_min = float(lat_str[2:])
                lat = lat_deg + (lat_min / 60)
                if lat_dir == 'S':
                    lat = -lat
            except (ValueError, IndexError) as e:
                logger.error(f'Error parsing latitude {lat_str} {lat_dir}: {e}, data: {data}')
                return None

            # Longitude: DDDMM.MMMM -> degrees + minutes/60
            try:
                lon_deg = int(lon_str[:3])
                lon_min = float(lon_str[3:])
                lon = lon_deg + (lon_min / 60)
                if lon_dir == 'W':
                    lon = -lon
            except (ValueError, IndexError) as e:
                logger.error(f'Error parsing longitude {lon_str} {lon_dir}: {e}, data: {data}')
                return None

            try:
                speed = float(speed_str) if speed_str else 0
                direction = float(direction_str) if direction_str else 0
                mcc = float(mcc_str) if mcc_str else None
                mnc = float(mnc_str) if mnc_str else None
                lac = float(lac_str) if lac_str else None
                cid = float(cid_str) if cid_str else None
            except ValueError as e:
                logger.error(f'Error parsing numeric fields: {e}, data: {data}')
                return None

            # Validate coordinates
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                logger.error(f'Invalid coordinates lat={lat}, lon={lon}, data: {data}')
                return None

            # Parse timestamp
            from datetime import datetime, timezone
            try:
                time_obj = datetime.strptime(f'{date_str}{time_str}', '%d%m%y%H%M%S')
                timestamp = time_obj.replace(tzinfo=timezone.utc)
            except ValueError as e:
                logger.error(f'Error parsing timestamp date_str={date_str}, time_str={time_str}: {e}, data: {data}')
                return None

            parsed_result = {
                'device_id': device_id,
                'latitude': lat,
                'longitude': lon,
                'speed': speed,
                'heading': direction,
                'timestamp': timestamp,
                'validity': validity,
                'status': status,
                'mcc': mcc,
                'mnc': mnc,
                'lac': lac,
                'cid': cid,
                'raw_data': data
            }
            logger.info(f'Successfully parsed GPS data for device {device_id}')
            return parsed_result

        except Exception as e:
            logger.error(f'Error parsing GPS data: {e}')
            return None

    def convert_decoded_to_parsed(self, decoded):
        """
        Convert HQDecoder output to the expected parsed_data format
        """
        if "error" in decoded:
            return None

        packet_type = decoded.get("type")

        # Parse timestamp
        timestamp_str = decoded.get("timestamp")
        if timestamp_str:
            try:
                if packet_type == "HB":
                    # HB has only time, use current date
                    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    timestamp = datetime.strptime(f"{current_date} {timestamp_str}", "%Y-%m-%d %H:%M:%S")
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                else:
                    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except ValueError as e:
                logger.error(f"Invalid timestamp: {e}")
                return None
        else:
            return None

        if packet_type == "V1":
            parsed_data = {
                'device_id': decoded.get('imei'),
                'latitude': decoded.get('latitude'),
                'longitude': decoded.get('longitude'),
                'speed': decoded.get('speed_kph', 0),
                'heading': decoded.get('angle', 0),
                'timestamp': timestamp,
                'validity': decoded.get('gps_valid', False),  # GPS validity
                'status': decoded.get('status'),
                'mcc': decoded.get('mcc'),
                'mnc': decoded.get('mnc'),
                'lac': decoded.get('lac'),
                'cid': decoded.get('cid'),
                'unknown_sections': [],
                'raw_data': '',
                'packet_type': 'V1'
            }
            return parsed_data
        elif packet_type == "V0":
            # LBS packet - no GPS location, but update device status
            parsed_data = {
                'device_id': decoded.get('imei'),
                'timestamp': timestamp,
                'mcc': decoded.get('mcc'),
                'mnc': decoded.get('mnc'),
                'lac': decoded.get('lac'),
                'cid': decoded.get('cid'),
                'packet_type': 'V0'
            }
            return parsed_data
        elif packet_type == "V2":
            # Alarm/Status packet
            parsed_data = {
                'device_id': decoded.get('imei'),
                'timestamp': timestamp,
                'status': decoded.get('status'),
                'alarm': decoded.get('alarm'),
                'packet_type': 'V2'
            }
            return parsed_data
        elif packet_type == "HB":
            # Heartbeat packet
            parsed_data = {
                'device_id': decoded.get('imei'),
                'timestamp': timestamp,
                'status': decoded.get('status'),
                'voltage_mv': decoded.get('voltage_mv'),
                'signal_strength': decoded.get('signal_strength'),
                'packet_type': 'HB'
            }
            return parsed_data
        elif packet_type == "UPLOAD":
            # Multi-record packet
            parsed_data = {
                'device_id': decoded.get('imei'),
                'records': decoded.get('records', []),
                'packet_type': 'UPLOAD'
            }
            return parsed_data
        else:
            logger.error(f"Unknown packet type: {packet_type}")
            return None

    def map_alarm_to_alert_type(self, alarm):
        """
        Map alarm string from V2 packet to Alert alert_type
        """
        alarm_lower = alarm.lower()
        if 'sos' in alarm_lower:
            return 'sos_button'
        elif 'battery' in alarm_lower or 'low' in alarm_lower:
            return 'low_battery'
        elif 'speed' in alarm_lower:
            return 'speed_limit'
        elif 'offline' in alarm_lower:
            return 'device_offline'
        else:
            # For unknown alarms, we could create a custom alert or skip
            return None

    def process_gps_data(self, data, ip_address, protocol_type):
        """
        Process GPS data recursively for UPLOAD packets
        """
        try:
            # Decode data using HQDecoder
            decoded = self.decoder.decode(data)
            parsed_data = self.convert_decoded_to_parsed(decoded)
            if not parsed_data:
                logger.warning(f'Failed to decode GPS data in UPLOAD: {data}')
                return

            # Find device by device_id
            try:
                device = Device.objects.get(imei=parsed_data['device_id'])
            except Device.DoesNotExist:
                logger.warning(f'Unregistered device in UPLOAD {parsed_data["device_id"]}')
                return

            # Check if device is active
            if device.status != 'active':
                logger.warning(f'Device in UPLOAD {device.imei} is not active (status: {device.status})')
                return

            packet_type = parsed_data.get('packet_type')

            if packet_type == 'V1':
                # GPS location packet
                location_data = LocationData.objects.create(
                    device=device,
                    latitude=parsed_data['latitude'],
                    longitude=parsed_data['longitude'],
                    speed=parsed_data['speed'],
                    heading=parsed_data['heading'],
                    timestamp=parsed_data['timestamp'],
                    battery_level=parsed_data['voltage'],
                    raw_data={
                        'device_id': parsed_data['device_id'],
                        'validity': parsed_data['validity'],
                        'status': parsed_data['status'],
                        'temperature': parsed_data['temperature'],
                        'odometer': parsed_data['odometer'],
                        'mcc': parsed_data['mcc'],
                        'mnc': parsed_data['mnc'],
                        'lac': parsed_data['lac'],
                        'cid': parsed_data['cid'],
                        'protocol': protocol_type,
                        'ip_address': ip_address
                    }
                )

                # Broadcast device update
                self.broadcast_device_update(device)

                logger.info(f'Processed UPLOAD location data for device {device.imei}: {location_data.id}')

        except Exception as e:
            logger.error(f'Error processing GPS data in UPLOAD: {e}')

    def broadcast_device_update(device, location_data=None, status_override=None):
        """
        Broadcast device location update to WebSocket clients
        """
        try:
            channel_layer = get_channel_layer()
            if status_override:
                status = status_override
            elif location_data:
                if location_data.is_alarm:
                    status = 'alert'
                elif location_data.speed > 0:
                    status = 'moving'
                elif location_data.packet_type == 'HB':
                    status = 'idle'
                else:
                    status = 'parked'
            else:
                # Get latest location for status determination if no location_data provided
                latest_location = device.locations.first()
                if latest_location:
                    if latest_location.is_alarm:
                        status = 'alert'
                    elif latest_location.speed > 0:
                        status = 'moving'
                    elif latest_location.packet_type == 'HB':
                        status = 'idle'
                    else:
                        status = 'parked'
                else:
                    status = 'offline'

            # Get latest location data for broadcasting
            latest_location = location_data or device.locations.first()

            device_data = {
                'id': device.id,
                'name': device.name,
                'imei': device.imei,
                'status': status,
                'driver_name': device.driver_name,
                'lat': float(latest_location.latitude) if latest_location and latest_location.latitude else None,
                'lng': float(latest_location.longitude) if latest_location and latest_location.longitude else None,
                'last_update': latest_location.created_at.isoformat() if latest_location else None,
                'battery_level': latest_location.battery_level if latest_location else None,
                'speed': latest_location.speed if latest_location else 0,
                'heading': latest_location.heading if latest_location else 0,
                'signal_strength': latest_location.signal_strength if latest_location else None,
                'satellites': latest_location.satellites if latest_location else None,
                'matched_geometry': latest_location.matched_geometry if latest_location else None,
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

            logger.info(f'Broadcasted update for device {device.imei}')

        except Exception as e:
            logger.error(f'Error broadcasting device update: {e}')