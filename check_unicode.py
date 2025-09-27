#!/usr/bin/env python3
# -*- coding: utf-8 -*-

print("Unicode character analysis:")
print(f"\\U0001f525 = {chr(0x1f525)}")  # This is the 🔥 emoji
print(f"\\U0001f6d2 = {chr(0x1f6d2)}")  # This is the 🛒 emoji

# Check what's in our order history response
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_orders import get_order_history

# Test without printing the result
result = get_order_history("905306897885@c.us", "eylül ayı")
print(f"Response length: {len(result)}")

# Find problematic characters
for i, char in enumerate(result):
    if ord(char) > 127:  # Non-ASCII characters
        print(f"Position {i}: {repr(char)} (U+{ord(char):04X})")
        if i > 210 and i < 220:  # Around position 217 where error occurs
            print(f"  -> This is near position 217 where error occurs")