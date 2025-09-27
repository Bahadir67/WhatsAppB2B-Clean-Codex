#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple test for order history without printing emojis"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_orders import get_order_history

def test_order_history_simple():
    whatsapp_number = "905306897885@c.us"

    try:
        result = get_order_history(whatsapp_number, "eylül ayı")

        # Count characters to see if result is valid
        if result and len(result) > 0:
            print(f"SUCCESS: Function returned {len(result)} characters")
            print(f"Contains HTTP link: {'http' in result}")
            print(f"Contains tunnel URL: {'trycloudflare.com' in result or 'localhost:3005' in result}")

            # Extract just the essential info without emojis
            lines = result.split('\n')
            for line in lines:
                if 'bulundu' in line or 'http' in line or 'Eylul' in line or 'Eyll' in line:
                    try:
                        print(f"Key line: {line}")
                    except:
                        print("Key line: [contains non-printable characters]")
        else:
            print("ERROR: Function returned empty result")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_order_history_simple()