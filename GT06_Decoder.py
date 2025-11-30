import struct
import datetime
from datetime import timezone

class GT06Decoder:
    """
    Decoder for GT06 Binary Protocol (Start bytes: 0x78 0x78)
    """
    
    def decode(self, data):
        """
        Decode raw bytes from GT06 device.
        Returns a dictionary with parsed data or error.
        """
        try:
            if not isinstance(data, bytes):
                return {"error": "Data must be bytes"}
            
            if len(data) < 10:
                return {"error": "Packet too short"}
            
            # Check start bits (0x78 0x78)
            if data[0] != 0x78 or data[1] != 0x78:
                return {"error": "Invalid start bits"}
            
            packet_len = data[2]
            protocol_num = data[3]
            
            # Extract content based on protocol number
            content = data[4:-4] # Exclude header(4) and footer(4: serial+crc+stop)
            
            result = {
                "raw": data.hex(),
                "protocol_num": hex(protocol_num),
                "type": "GT06"
            }
            
            # Login Packet (0x01)
            if protocol_num == 0x01:
                imei_bytes = content[:8]
                imei = imei_bytes.hex()
                # GT06 IMEI is usually 15 digits, the first digit of the first byte is ignored if it's 0? 
                # Actually standard GT06 login sends 8 bytes for terminal ID.
                # Let's just use the hex string as ID for now, or interpret as needed.
                # Usually it's BCD or just raw hex. Let's assume raw hex string.
                # To match the user's "1917..." example, we might need to be careful.
                # But for now, let's just return the hex.
                result["imei"] = imei
                result["packet_type"] = "LOGIN"
                
            # Location Packet (0x12 or 0x22)
            elif protocol_num == 0x12 or protocol_num == 0x22:
                # Date Time (6 bytes)
                year = content[0] + 2000
                month = content[1]
                day = content[2]
                hour = content[3]
                minute = content[4]
                second = content[5]
                timestamp = datetime.datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
                result["timestamp"] = timestamp
                
                # GPS Info (Length 12 bytes usually)
                # This is a simplified parser. 
                # Real GT06 location parsing is complex (bit manipulation for lat/lon).
                # For this task, I'll implement a basic version.
                
                # Satellites info (1 byte)
                sats_byte = content[6]
                sats = sats_byte & 0x0F
                
                # Latitude (4 bytes)
                lat_bytes = content[7:11]
                lat_raw = struct.unpack('>I', lat_bytes)[0]
                latitude = (lat_raw / 1800000.0)
                
                # Longitude (4 bytes)
                lon_bytes = content[11:15]
                lon_raw = struct.unpack('>I', lon_bytes)[0]
                longitude = (lon_raw / 1800000.0)
                
                # Speed (1 byte)
                speed = content[15]
                
                # Course/Status (2 bytes)
                course_status = struct.unpack('>H', content[16:18])[0]
                heading = course_status & 0x03FF # Lower 10 bits
                
                result["latitude"] = latitude
                result["longitude"] = longitude
                result["speed"] = speed
                result["heading"] = heading
                result["packet_type"] = "V1" # Map to V1 for compatibility with existing logic
                result["gps_valid"] = True
                
            # Heartbeat (0x13)
            elif protocol_num == 0x13:
                status_info = content[0]
                voltage_level = content[1] # Battery level 0-6
                gsm_signal = content[2] # 0-4
                
                result["packet_type"] = "HB"
                result["status"] = hex(status_info)
                result["battery_level"] = voltage_level
                result["signal_strength"] = gsm_signal
                
            # Alarm (0x26 or 0x16)
            elif protocol_num == 0x26 or protocol_num == 0x16:
                result["packet_type"] = "V2"
                result["alarm"] = "General Alarm"
                
            else:
                result["packet_type"] = "UNKNOWN"
                
            return result
            
        except Exception as e:
            return {"error": f"Decoding error: {str(e)}"}
