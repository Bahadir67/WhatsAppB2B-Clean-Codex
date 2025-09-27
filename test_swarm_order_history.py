#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test the full Swarm system with September order query"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_runtime import SwarmB2BSystem

def test_swarm_system():
    print("=== Testing Swarm System with September Order Query ===\n")

    system = SwarmB2BSystem()

    # Test different WhatsApp number formats
    whatsapp_formats = [
        "905306897885",
        "905306897885@c.us",
        "+905306897885",
        "+905306897885@c.us"
    ]

    test_message = "eylül ayı siparişlerimi görebilir miyim?"

    for whatsapp_number in whatsapp_formats:
        print(f"Testing with WhatsApp number: {whatsapp_number}")
        try:
            result = system.process_message(test_message, whatsapp_number)
            print(f"Result length: {len(result) if result else 0}")
            if result:
                if "teknik sorun" in result.lower():
                    print("❌ Technical problem detected")
                elif "eylül" in result.lower() or "september" in result.lower():
                    print("✅ September orders detected")
                elif "http" in result:
                    print("✅ HTTP link generated")
                else:
                    print("⚠️ Unexpected response")

            print(f"First 200 chars: {result[:200] if result else 'None'}...")
            print("-" * 50)
        except Exception as e:
            print(f"❌ ERROR: {e}")
            print("-" * 50)

if __name__ == "__main__":
    test_swarm_system()