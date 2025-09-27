#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the Swarm system after emoji fixes"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_runtime import SwarmB2BSystem

def test_fixed_swarm():
    print("=== Testing Fixed Swarm System ===\n")

    system = SwarmB2BSystem()
    whatsapp_number = "905306897885"
    test_message = "eylül ayı siparişlerimi görebilir miyim?"

    print(f"Testing with: {whatsapp_number}")
    print(f"Message: {test_message}")
    print("-" * 50)

    try:
        result = system.process_message(test_message, whatsapp_number)

        if result:
            print(f"SUCCESS! Result length: {len(result)}")
            print(f"Contains 'Eylul': {'eylul' in result.lower() or 'eyll' in result.lower()}")
            print(f"Contains HTTP link: {'http' in result}")
            print(f"Contains 'teknik sorun': {'teknik sorun' in result.lower()}")

            # Print safe portions
            lines = result.split('\n')
            for i, line in enumerate(lines):
                if len(line.strip()) > 0:
                    try:
                        print(f"Line {i+1}: {line}")
                    except UnicodeEncodeError:
                        print(f"Line {i+1}: [contains non-printable chars]")

        else:
            print("ERROR: No result returned")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_fixed_swarm()