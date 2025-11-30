#!/usr/bin/env python3
"""
Test script to verify JT808 Decoder supports both 6-byte and 8-byte Terminal IDs
"""
import sys
sys.path.append('.')

from JT808_Decoder import JT808Decoder

def test_6byte_heartbeat():
    """Test 6-byte Terminal ID (Standard) - Heartbeat packets from user"""
    decoder = JT808Decoder()
    
    # User provided heartbeat packets (all should have 6-byte Terminal ID)
    test_packets = [
        "7e000300000191765333551ded207e",
        "7e000300000191765333551df5387e",
        "7e000300000191765333551dfd307e",
        "7e000300000191765333551e05cb7e",
        "7e000300000191765333551e0dc37e",
        "7e000300000191765333551e15db7e",
        "7e000300000191765333551e1cd27e",
        "7e000300000191765333551e2ce27e",
    ]
    
    print("=" * 60)
    print("Testing 6-byte Terminal ID (Standard JT808)")
    print("=" * 60)
    
    for i, hex_str in enumerate(test_packets, 1):
        data = bytes.fromhex(hex_str)
        result = decoder.decode(data)
        
        print(f"\nTest {i}: {hex_str}")
        
        if "error" in result:
            print(f"  ❌ FAILED: {result['error']}")
            return False
        
        # Verify expected values
        expected_imei = "19176533355"
        expected_packet_type = "HB"
        expected_terminal_id_length = 6
        
        checks = [
            (result.get('imei') == expected_imei, f"IMEI: {result.get('imei')} (expected {expected_imei})"),
            (result.get('packet_type') == expected_packet_type, f"Packet Type: {result.get('packet_type')} (expected {expected_packet_type})"),
            (result.get('terminal_id_length') == expected_terminal_id_length, f"Terminal ID Length: {result.get('terminal_id_length')} bytes"),
            ('response' in result, "Response generated"),
        ]
        
        all_passed = True
        for passed, msg in checks:
            status = "✓" if passed else "❌"
            print(f"  {status} {msg}")
            if not passed:
                all_passed = False
        
        if all_passed:
            print(f"  ✅ Test {i} PASSED")
        else:
            print(f"  ❌ Test {i} FAILED")
            return False
    
    print("\n" + "=" * 60)
    print("✅ All 6-byte Terminal ID tests PASSED")
    print("=" * 60)
    return True

def test_8byte_registration():
    """Test 8-byte Terminal ID (Legacy) - Simulated registration packet"""
    decoder = JT808Decoder()
    
    print("\n" + "=" * 60)
    print("Testing 8-byte Terminal ID (Legacy/Extended)")
    print("=" * 60)
    
    # Simulated 8-byte Terminal ID packet (0x0100 Registration)
    # Structure: 7E + MsgID(0100) + Props(002D=45 bytes body) + TermID(8 bytes) + Serial(0022) + Body(45 bytes) + Checksum + 7E
    # Using the structure from the old code comments
    # This is a synthetic packet for testing purposes
    
    # Let's create a minimal valid 8-byte packet
    # For simplicity, we'll use a heartbeat (0x0003) with 8-byte Terminal ID
    # 7E + 0003 + 0000 (body length 0) + 01917653335512345678 (8 bytes) + 0001 (serial) + checksum + 7E
    
    # Manual construction:
    msg_id = bytes.fromhex("0003")  # Heartbeat
    body_props = bytes.fromhex("0000")  # Body length = 0
    terminal_id = bytes.fromhex("0191765333551234")  # 8 bytes (6 bytes IMEI + 2 extra)
    msg_serial = bytes.fromhex("0001")
    
    # Calculate checksum
    content = msg_id + body_props + terminal_id + msg_serial
    checksum = 0
    for byte in content:
        checksum ^= byte
    
    packet = b'\x7e' + content + bytes([checksum]) + b'\x7e'
    hex_str = packet.hex()
    
    print(f"\nTest: {hex_str}")
    result = decoder.decode(packet)
    
    if "error" in result:
        print(f"  ❌ FAILED: {result['error']}")
        return False
    
    expected_imei = "19176533355"
    expected_terminal_id_length = 8
    
    checks = [
        (result.get('imei') == expected_imei, f"IMEI: {result.get('imei')} (expected {expected_imei})"),
        (result.get('terminal_id_length') == expected_terminal_id_length, f"Terminal ID Length: {result.get('terminal_id_length')} bytes"),
        ('response' in result, "Response generated"),
    ]
    
    all_passed = True
    for passed, msg in checks:
        status = "✓" if passed else "❌"
        print(f"  {status} {msg}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print(f"  ✅ 8-byte Terminal ID test PASSED")
    else:
        print(f"  ❌ 8-byte Terminal ID test FAILED")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 8-byte Terminal ID test PASSED")
    print("=" * 60)
    return True

if __name__ == "__main__":
    print("\n🧪 JT808 Decoder Dual Terminal ID Test Suite\n")
    
    success = True
    
    # Test 6-byte (standard)
    if not test_6byte_heartbeat():
        success = False
    
    # Test 8-byte (legacy)
    if not test_8byte_registration():
        success = False
    
    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 60)
        sys.exit(1)
