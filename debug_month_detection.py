#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to debug September month detection issue"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_orders import _resolve_order_history_timeframe, _normalize_timeframe_text, _MONTH_KEYWORDS
from swarm_orders import _llm_resolve_order_history_timeframe

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

def test_llm_timeframe_parsing():
    print("=== LLM Timeframe Parsing Debug ===\n")

    examples = [
        "geçen cuma günü sparişler görebilir miyim?",
        "geçen hafta cuma siparişlerimi listele",
        "son 2 hafta siparişler",
        "temmuz başındaki siparişler",
    ]

    for query in examples:
        print(f"Query: {query}")
        result = _llm_resolve_order_history_timeframe(query)
        if result:
            start, end, label, note = result
            print(f"  LLM Start: {start}")
            print(f"  LLM End:   {end}")
            print(f"  Label:     {label}")
            print(f"  Note:      {note}")
        else:
            print("  LLM parser returned None, falling back to deterministic logic")
            start, end, label, note = _resolve_order_history_timeframe(query)
            print(f"  Fallback Start: {start}")
            print(f"  Fallback End:   {end}")
            print(f"  Label:          {label}")
            if note:
                print(f"  Note:           {note}")
        print()

if __name__ == "__main__":
    test_month_detection()
    test_llm_timeframe_parsing()
