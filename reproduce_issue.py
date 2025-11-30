import socket
import time
import sys

def send_packet(data, description):
    print(f"--- Testing: {description} ---")
    print(f"Sending: {data}")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(('127.0.0.1', 5000))
        s.sendall(data)
        # Wait a bit for server to process
        time.sleep(1)
        s.close()
        print("Sent successfully.")
    except Exception as e:
        print(f"Failed to send: {e}")
    print("-" * 30)

if __name__ == "__main__":
    # Test 1: Standard *HQ packet with the problematic ID prefix (1917...)
    # Assuming ID is 15 digits: 191712345678901
    # Format: *HQ,ID,V1,HHMMSS,A,LAT,D,LON,D,SPD,DIR,DDMMYY,FLAGS,MCC,MNC,LAC,CID#
    packet_text = b"*HQ,191712345678901,V1,120000,A,3542.0000,N,05125.0000,E,0.00,0,241125,FFFFFFFF,432,11,1234,5678#"
    send_packet(packet_text, "Text Protocol with ID 1917...")

    # Test 2: Binary-like packet (simulated GT06 binary)
    # GT06 binary usually starts with 0x78 0x78
    # We send it as bytes.
    packet_binary = b"\x78\x78\x0D\x01\x01\x23\x45\x67\x89\x01\x23\x45\x00\x01\x8C\xDD\x0D\x0A" 
    send_packet(packet_binary, "Binary Protocol (0x78 0x78...)")

    # Test 3: Text packet WITHOUT start/end markers (to test security check)
    packet_no_markers = b"HQ,191712345678901,V1,120000,A,3542.0000,N,05125.0000,E,0.00,0,241125,FFFFFFFF,432,11,1234,5678"
    send_packet(packet_no_markers, "Text Protocol missing * and #")
