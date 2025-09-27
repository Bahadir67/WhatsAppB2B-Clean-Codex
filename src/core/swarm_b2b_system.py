#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OpenAI Swarm Multi-Agent B2B System entrypoint."""

import os
import sys

if sys.platform == "win32":
    import locale

    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.utf8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.utf8')
        except locale.Error:
            pass

from swarm_api import app
from swarm_runtime import SwarmB2BSystem


def run_test_mode() -> None:
    print("=" * 60)
    print("OpenAI Swarm Single-Product B2B System - TEST MODE")
    print("5 Agents: Intent -> Customer/Product/Sales/Order")
    print("Workflow: Single-Product Instant Ordering")
    print("TASK 2.4: ÜRÜN_SEÇİLDİ intent testing")
    print("TASK 2.5: Enhanced MIKTAR_GİRİŞİ intent testing")
    print("=" * 60)

    system = SwarmB2BSystem()

    print("\n--- TASK 2.4 TEST ---")
    test_message = "ÜRÜN_SEÇİLDİ: 17A0040 - Hidrolik Silindir 100x200 - 1250.00 TL"
    result = system.process_message(test_message, "905306897885")
    print("TASK 2.4 SONUCU:")
    print(result)

    print("\n--- TASK 2.5 TEST ---")
    for qty_input in ["5", "10 adet", "beş tane", "yaklaşık 7", "cancel"]:
        print(f"\n> Testing quantity: '{qty_input}'")
        response = system.process_message(qty_input, "905306897885")
        print(f"MIKTAR TEST SONUCU ({qty_input}): {response[:200]}...")

    print("=" * 60)


def run_server() -> None:
    print("=" * 60)
    print("OpenAI Swarm Single-Product B2B HTTP Server")
    print("5 Agents: Intent -> Customer/Product/Sales/Order")
    print("Workflow: Single-Product Instant Ordering (Cart Removed)")
    print("TASK 2.4: ÜRÜN_SEÇİLDİ intent implementation")
    print("TASK 2.5: Enhanced MIKTAR_GİRİŞİ intent implementation")
    print("Port: 3007 (Swarm)")
    print("Endpoints:")
    print("  POST /process-message - WhatsApp mesaj işleme")
    print("  GET  /health - System health check")
    print("=" * 60)

    app.run(
        host="0.0.0.0",
        port=3007,
        debug=True,
        threaded=True,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_test_mode()
    else:
        run_server()
