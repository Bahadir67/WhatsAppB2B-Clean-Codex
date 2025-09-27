#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Debug the specific Unicode position causing the issue"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_orders import get_order_history

def debug_unicode_position():
    print("=== Debugging Unicode at specific position ===\n")

    whatsapp_number = "905306897885@c.us"

    try:
        result = get_order_history(whatsapp_number, "eylül ayı")

        print(f"Total result length: {len(result)}")

        # Check characters around position 1313-1314
        if len(result) > 1315:
            print("\nCharacters around position 1313-1314:")
            for i in range(max(0, 1310), min(len(result), 1320)):
                char = result[i]
                try:
                    ord_val = ord(char)
                    if ord_val > 127:  # Non-ASCII
                        print(f"Position {i}: '{char}' (U+{ord_val:04X}) [NON-ASCII]")
                    else:
                        print(f"Position {i}: '{char}' (U+{ord_val:04X})")
                except:
                    print(f"Position {i}: [ERROR getting char]")
        else:
            print(f"Result too short ({len(result)} chars), checking all non-ASCII:")
            for i, char in enumerate(result):
                if ord(char) > 127:
                    print(f"Position {i}: '{char}' (U+{ord(char):04X})")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_unicode_position()