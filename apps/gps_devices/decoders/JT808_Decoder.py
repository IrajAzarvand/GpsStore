import struct
import datetime
from datetime import timezone

class JT808Decoder:
    """
    Decoder for JT808 Protocol (China National Standard)
    Start/End byte: 0x7E
    """

    def unescape(self, data):
        """
        Unescape data: 
        0x7d 0x02 -> 0x7e
        0x7d 0x01 -> 0x7d
        """
        return data.replace(b'\x7d\x02', b'\x7e').replace(b'\x7d\x01', b'\x7d')

    def escape(self, data):
        """
        Escape data for transmission:
        0x7e -> 0x7d 0x02
        0x7d -> 0x7d 0x01
        """
        return data.replace(b'\x7d', b'\x7d\x01').replace(b'\x7e', b'\x7d\x02')

    def calculate_checksum(self, data):
        """
        XOR checksum of all bytes
        """
        checksum = 0
        for byte in data:
            checksum ^= byte
        return checksum

    def decode(self, data):
        """
        Decode raw bytes from JT808 device.
        Returns a dictionary with parsed data or error.
        If a response is required, it includes a 'response' key with bytes to send back.
        
        Supports both 6-byte (standard) and 8-byte (legacy) Terminal ID formats.
        """
        try:
            if not isinstance(data, bytes):
                return {"error": "Data must be bytes"}
            
            if len(data) < 13: # Min length for a valid packet
                return {"error": "Packet too short"}
            
            # Check start and end bytes
            if data[0] != 0x7e or data[-1] != 0x7e:
                return {"error": "Invalid start/end bytes"}
            
            # Unescape the body (everything between start and end 7E)
            raw_body = data[1:-1]
            unescaped_body = self.unescape(raw_body)
            
            # Verify Checksum
            # The checksum is the last byte of the unescaped body
            received_checksum = unescaped_body[-1]
            content_for_checksum = unescaped_body[:-1]
            calculated_checksum = self.calculate_checksum(content_for_checksum)
            
            if received_checksum != calculated_checksum:
                return {"error": f"Checksum failed. Calc: {hex(calculated_checksum)}, Recv: {hex(received_checksum)}"}
            
            # Parse Header - First 4 bytes are always: MsgID(2) + Props(2)
            # Message ID (2 bytes)
            msg_id = struct.unpack('>H', unescaped_body[0:2])[0]
            
            # Body Properties (2 bytes)
            body_props = struct.unpack('>H', unescaped_body[2:4])[0]
            body_length = body_props & 0x03FF # Lower 10 bits
            has_sub_package = (body_props >> 13) & 1
            
            # Dynamic Terminal ID Length Detection
            # Total unescaped length = Header + Body + Checksum(1)
            # Header = MsgID(2) + Props(2) + TermID(?) + Serial(2)
            # So: len(unescaped_body) = Header + Body + 1
            # Header = len(unescaped_body) - body_length - 1
            # TermID_len = Header - 2 - 2 - 2 = Header - 6
            
            total_length = len(unescaped_body)
            header_length = total_length - body_length - 1  # -1 for checksum
            terminal_id_length = header_length - 6  # -6 for MsgID(2) + Props(2) + Serial(2)
            
            # Validate Terminal ID length
            if terminal_id_length == 6:
                # Standard JT808: 6-byte Terminal ID
                terminal_id_bytes = unescaped_body[4:10]
                msg_serial_offset = 10
            elif terminal_id_length == 8:
                # Legacy/Extended: 8-byte Terminal ID
                terminal_id_bytes = unescaped_body[4:12]
                msg_serial_offset = 12
            else:
                return {"error": f"Invalid Terminal ID length: {terminal_id_length} bytes (expected 6 or 8)"}
            
            # Decode BCD for the first 6 bytes to get IMEI
            imei = self.bcd_to_str(terminal_id_bytes[:6])
            # Strip leading zero if present
            if imei.startswith('0'):
                imei = imei[1:]
            
            # Message Serial Number (2 bytes)
            msg_serial = struct.unpack('>H', unescaped_body[msg_serial_offset:msg_serial_offset+2])[0]
            
            # Body content starts after header, ends before checksum
            body_start = msg_serial_offset + 2
            body_content = unescaped_body[body_start:-1] # Exclude checksum at end
            
            result = {
                "raw": data.hex(),
                "protocol_num": hex(msg_id),
                "type": "JT808",
                "imei": imei,
                "msg_serial": msg_serial,
                "terminal_id_length": terminal_id_length  # For debugging
            }
            
            # Terminal Registration (0x0100)
            if msg_id == 0x0100:
                result["packet_type"] = "LOGIN"
                # Generate Response (0x8100)
                response_bytes = self.generate_registration_response(msg_serial, terminal_id_bytes)
                result["response"] = response_bytes
                
            # Location Report (0x0200)
            elif msg_id == 0x0200:
                result["packet_type"] = "V1" # Map to V1 for compatibility
                # Parse Body
                # Alarm Flag (4) + Status (4) + Lat (4) + Lon (4) + Alt (2) + Speed (2) + Heading (2) + Time (6)
                if len(body_content) < 28:
                     result["error"] = "Location body too short"
                     return result
                     
                lat_int = struct.unpack('>I', body_content[8:12])[0]
                lon_int = struct.unpack('>I', body_content[12:16])[0]
                speed_int = struct.unpack('>H', body_content[18:20])[0]
                heading_int = struct.unpack('>H', body_content[20:22])[0]
                time_bytes = body_content[22:28]
                
                result["latitude"] = lat_int / 1000000.0
                result["longitude"] = lon_int / 1000000.0
                result["speed"] = speed_int / 10.0
                result["heading"] = heading_int
                
                # Date Time BCD
                try:
                    time_str = self.bcd_to_str(time_bytes)
                    # Format: YYMMDDHHmmSS
                    year = int("20" + time_str[0:2])
                    month = int(time_str[2:4])
                    day = int(time_str[4:6])
                    hour = int(time_str[6:8])
                    minute = int(time_str[8:10])
                    second = int(time_str[10:12])
                    timestamp = datetime.datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
                    result["timestamp"] = timestamp
                    result["gps_valid"] = True
                except:
                    result["gps_valid"] = False
                    
                # Send Platform General Response (0x8001) to acknowledge location
                response_bytes = self.generate_general_response(msg_id, msg_serial, terminal_id_bytes)
                result["response"] = response_bytes

            # Heartbeat (0x0002)
            elif msg_id == 0x0002:
                result["packet_type"] = "HB"
                result["status"] = "online"
                response_bytes = self.generate_general_response(msg_id, msg_serial, terminal_id_bytes)
                result["response"] = response_bytes

            # Heartbeat / Unregistration (0x0003) - User reported this as Heartbeat
            elif msg_id == 0x0003:
                result["packet_type"] = "HB"
                result["status"] = "online"
                # Standard JT808 0x0003 is Unregistration, but if used as HB, we should ack it.
                response_bytes = self.generate_general_response(msg_id, msg_serial, terminal_id_bytes)
                result["response"] = response_bytes
                
            else:
                result["packet_type"] = "UNKNOWN"
                
            return result
            
        except Exception as e:
            return {"error": f"Decoding error: {str(e)}"}

    def bcd_to_str(self, bcd_data):
        return ''.join('{:02X}'.format(b) for b in bcd_data)

    def generate_registration_response(self, msg_serial, terminal_id_bytes):
        """
        Generate 0x8100 response
        Body: Serial(2) + Result(1) + AuthCode(Str)
        Works with both 6-byte and 8-byte Terminal IDs
        """
        # Header
        msg_id = b'\x81\x00'
        
        # Body Content
        # 1. Response Serial Number (2 bytes) - same as received msg_serial
        resp_serial = struct.pack('>H', msg_serial)
        # 2. Result (1 byte) - 0 = Success
        result = b'\x00'
        # 3. Auth Code (String) - e.g. "1"
        auth_code = b'1'
        
        body = resp_serial + result + auth_code
        
        # Body Properties
        # Length is len(body)
        # No encryption, no sub-package
        body_len = len(body)
        body_props = struct.pack('>H', body_len)
        
        # Serial Number for this response (server maintains its own counter, but let's use 0 for simplicity or random)
        server_serial = b'\x00\x01'
        
        # Construct Unescaped Packet
        # Header: MsgID(2) + Props(2) + TermID(6 or 8) + Serial(2)
        # Note: Using the same Terminal ID format as received (dynamic length)
        header = msg_id + body_props + terminal_id_bytes + server_serial
        
        packet_content = header + body
        
        # Checksum
        checksum = self.calculate_checksum(packet_content)
        
        # Escape
        escaped_content = self.escape(packet_content + bytes([checksum]))
        
        # Final Packet
        return b'\x7e' + escaped_content + b'\x7e'

    def generate_general_response(self, ack_msg_id, ack_msg_serial, terminal_id_bytes):
        """
        Generate 0x8001 General Response
        Body: AckSerial(2) + AckMsgId(2) + Result(1)
        Works with both 6-byte and 8-byte Terminal IDs
        """
        msg_id = b'\x80\x01'
        
        # Body
        resp_serial = struct.pack('>H', ack_msg_serial)
        resp_msg_id = struct.pack('>H', ack_msg_id)
        result = b'\x00' # Success
        
        body = resp_serial + resp_msg_id + result
        
        body_len = len(body)
        body_props = struct.pack('>H', body_len)
        server_serial = b'\x00\x02' # Increment ideally
        
        # Header: MsgID(2) + Props(2) + TermID(6 or 8) + Serial(2)
        # Note: Using the same Terminal ID format as received (dynamic length)
        header = msg_id + body_props + terminal_id_bytes + server_serial
        packet_content = header + body
        checksum = self.calculate_checksum(packet_content)
        escaped_content = self.escape(packet_content + bytes([checksum]))
        
        return b'\x7e' + escaped_content + b'\x7e'
