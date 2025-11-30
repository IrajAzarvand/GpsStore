#!/usr/bin/env python3
"""
Test script to verify GPS data parsing with sample data.
"""

import sys
import os

# Add project root to path for importing HQ_Decoder
sys.path.append(os.path.dirname(__file__))

from HQ_Decoder import HQDecoder

def test_gps_parsing():
    # Sample GPS data
    sample_data = "*HQ,9176515388,V1,150429,A,2928.2347,N,05232.7644,E,0.00,0,201125,fbfffbff,432,35,32645,31251#"

    # Initialize decoder
    decoder = HQDecoder()

    # Decode the data
    decoded = decoder.decode(sample_data)

    if "error" in decoded:
        print(f"Error decoding data: {decoded['error']}")
        return

    # Extract voltage and temperature
    voltage = decoded.get('voltage_mv')
    temperature = decoded.get('temperature_c')

    print(f"Parsed voltage: {voltage} V")
    print(f"Parsed temperature: {temperature} °C")

    # Verify expected values
    expected_voltage = 4.32
    expected_temperature = -5.0

    if voltage == expected_voltage and temperature == expected_temperature:
        print("PASS: Voltage and temperature match expected values")
    else:
        print("FAIL: Values do not match expected")
        print(f"  Expected: voltage={expected_voltage}, temperature={expected_temperature}")
        print(f"  Got:      voltage={voltage}, temperature={temperature}")

if __name__ == "__main__":
    test_gps_parsing()