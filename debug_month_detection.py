#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to debug September month detection issue"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_orders import _resolve_order_history_timeframe, _normalize_timeframe_text, _MONTH_KEYWORDS
from datetime import datetime

def test_month_detection():
    print("=== September Month Detection Debug ===\n")

    # Test cases that should work
    test_cases = [
        "eylül ayı",
        "eylul ayi",
        "september",
        "Eylül",
        "EYLÜL AYI",
        "eylül",
        "eylul",
        "eylül 2024",
        "september 2024"
    ]

    print("Month Keywords Map:")
    for keyword, month in _MONTH_KEYWORDS.items():
        if month == 9:  # September
            print(f"  '{keyword}' -> {month}")
    print()

    for test_case in test_cases:
        print(f"Testing: '{test_case}'")
        normalized = _normalize_timeframe_text(test_case)
        print(f"  Normalized: '{normalized}'")

        try:
            start_dt, end_dt, label, note = _resolve_order_history_timeframe(test_case)
            print(f"  Result: {label}")
            print(f"  Start: {start_dt}")
            print(f"  End: {end_dt}")
            if note:
                print(f"  Note: {note}")
        except Exception as e:
            print(f"  ERROR: {e}")
        print()

if __name__ == "__main__":
    test_month_detection()