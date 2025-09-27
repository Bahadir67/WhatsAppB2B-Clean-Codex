#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to debug get_order_history function"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_orders import get_order_history
from database_tools_fixed import db

def test_order_history():
    print("=== Order History Debug ===\n")

    # Test WhatsApp number - check recent conversation from the logs
    whatsapp_number = "905306897885@c.us"  # This seems to be the user from the conversation

    print(f"Testing order history for: {whatsapp_number}")

    # First check if this user has any orders at all
    cursor = db.connection.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE whatsapp_number = %s", [whatsapp_number])
    total_orders = cursor.fetchone()[0]
    print(f"Total orders for this user: {total_orders}")

    if total_orders > 0:
        # Check what orders exist
        cursor.execute("""
            SELECT order_number, status, total_amount, created_at
            FROM orders
            WHERE whatsapp_number = %s
            ORDER BY created_at DESC
        """, [whatsapp_number])
        orders = cursor.fetchall()
        print("\nExisting orders:")
        for order in orders:
            print(f"  {order[0]} - {order[1]} - {order[2]} TL - {order[3]}")

    cursor.close()

    print("\n" + "="*50)
    print("Testing September order query...")

    # Test the actual get_order_history function
    result = get_order_history(whatsapp_number, "eylül ayı")
    print("Result:")
    print(result)

if __name__ == "__main__":
    test_order_history()