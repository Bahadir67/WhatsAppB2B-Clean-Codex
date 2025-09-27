#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test script to debug September month detection issue"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'core'))

from swarm_orders import _resolve_order_history_timeframe, _normalize_timeframe_text, _MONTH_KEYWORDS
from swarm_orders import _llm_resolve_order_history_timeframe, get_cache_stats, reset_cache_stats
from swarm_orders import _evaluate_llm_confidence, _get_adaptive_threshold, track_llm_accuracy
from swarm_orders import validate_and_sanitize_input, logger, _normalize_whatsapp_identifier

def test_month_detection():
    print("=== September Month Detection Debug ===\n")

    # Reset cache stats for clean testing
    reset_cache_stats()
    print("Cache istatistikleri sıfırlandı\n")

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

    print("=== Regex Pattern Test ===\n")

    # Test new regex patterns
    regex_test_cases = [
        "geçen hafta",
        "önceki hafta",
        "son hafta",
        "bu hafta",
        "hafta sonu",
        "son 7 gün",
        "son 15 gün",
        "5 gün önce",
        "2 hafta önce",
        "geçen ay",
        "bu ay",
        "ayın başı",
        "ayın sonu",
    ]

    for test_case in regex_test_cases:
        print(f"Testing REGEX: '{test_case}'")
        try:
            start_dt, end_dt, label, note = _resolve_order_history_timeframe(test_case)
            print(f"  ✅ Result: {label}")
            print(f"     Start: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"     End: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
            if note:
                print(f"     Note: {note}")
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
        print()

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
        "geçen hafta siparişlerim",
        "önceki hafta siparişler",
        "hafta sonu siparişlerim",
        "ayın başı siparişler",
        "ayın sonu siparişler",
        "son 15 gün",
        "bu hafta",
        "geçen ayın son haftası",
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

def test_edge_cases():
    """Test edge cases and boundary conditions."""
    print("\n" + "="*60)
    print("EDGE CASES & BOUNDARY CONDITIONS TEST")
    print("="*60)

    edge_cases = [
        # Empty and None cases
        ("", "Empty string"),
        (None, "None input"),

        # Very long inputs
        ("a" * 1000, "Very long input"),

        # Special characters
        ("geçen hafta!!! ???", "Special characters"),
        ("geçen-hafta", "Hyphenated input"),
        ("geçen   hafta", "Multiple spaces"),

        # Unicode characters
        ("geçen hafta 🚀", "Unicode emoji"),
        ("eylül ayı ñáéíóú", "Accented characters"),

        # Mixed case edge cases
        ("GEÇEN Hafta", "Mixed case"),
        ("EyLüL AyI", "Random case"),

        # Numbers in text
        ("son 0 gün", "Zero days"),
        ("son -5 gün", "Negative days"),
        ("son 999 gün", "Very large number"),
    ]

    print("Edge Case Resolution Tests:")
    for test_input, description in edge_cases:
        try:
            result = _resolve_order_history_timeframe(test_input)
            if result:
                label = result[2]
                print(f"  ✅ {description}: {label}")
            else:
                print(f"  ⚠️ {description}: No result")
        except Exception as e:
            print(f"  ❌ {description}: Error - {str(e)[:50]}...")

def test_performance():
    """Test performance of different resolution methods."""
    print("\n" + "="*60)
    print("PERFORMANCE TEST")
    print("="*60)

    import time

    test_queries = [
        "geçen hafta", "bu ay", "son 7 gün", "eylül ayı",
        "ayın başı", "hafta sonu", "geçen ay", "bu hafta"
    ] * 10  # Repeat for more accurate measurement

    # Test regex performance
    start_time = time.time()
    for query in test_queries:
        _resolve_order_history_timeframe(query)
    regex_time = time.time() - start_time

    # Test normalization performance
    start_time = time.time()
    for query in test_queries:
        _normalize_timeframe_text(query)
    normalize_time = time.time() - start_time

    print(f"Regex Resolution: {regex_time:.3f}s for {len(test_queries)} queries")
    print(f"Text Normalization: {normalize_time:.3f}s for {len(test_queries)} queries")
    print(f"Average per query: {(regex_time + normalize_time) / len(test_queries) * 1000:.2f}ms")

def test_error_handling():
    """Test the new error handling and logging system."""
    print("\n" + "="*60)
    print("ERROR HANDLING & LOGGING TEST")
    print("="*60)

    # Test input validation
    test_inputs = [
        ("", "timeframe", "Empty input"),
        ("<script>alert('xss')</script>", "timeframe", "XSS attempt"),
        ("a" * 600, "timeframe", "Too long input"),
        ("+905306897885@c.us", "whatsapp_id", "Valid WhatsApp ID"),
        ("invalid-id", "whatsapp_id", "Invalid WhatsApp ID"),
    ]

    print("Input Validation Tests:")
    for input_val, input_type, description in test_inputs:
        try:
            result = validate_and_sanitize_input(input_val, input_type)
            print(f"  ✅ {description}: {len(result)} chars")
        except Exception as e:
            print(f"  ❌ {description}: {str(e)}")

    print("\nTimeframe Resolution Error Tests:")
    error_inputs = [
        None,
        "",
        "<script>alert('hack')</script>",
        "a" * 1000,
    ]

    for error_input in error_inputs:
        try:
            result = _resolve_order_history_timeframe(error_input)
            if result:
                print(f"  ✅ Error input handled: {type(error_input).__name__}")
            else:
                print(f"  ⚠️ Error input returned None: {type(error_input).__name__}")
        except Exception as e:
            print(f"  ❌ Error input caused exception: {str(e)[:50]}...")

def test_confidence_scoring():
    """Test the new confidence scoring system."""
    print("\n" + "="*60)
    print("LLM CONFIDENCE SCORING TEST")
    print("="*60)

    from datetime import datetime

    # Test cases with different complexity levels
    test_cases = [
        ("son 7 gün", "simple"),           # Basit pattern
        ("geçen hafta", "medium"),         # Orta seviye
        ("temmuz başındaki siparişler", "complex"),  # Karmaşık pattern
        ("ayın sonu", "medium"),           # Orta seviye
    ]

    for query, expected_pattern in test_cases:
        print(f"\nQuery: '{query}' (Expected: {expected_pattern})")

        # Get adaptive threshold
        threshold = _get_adaptive_threshold(query)
        print(f"  Adaptive Threshold: {threshold}")

        # Test with mock LLM result
        mock_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        mock_end = mock_start.replace(hour=23, minute=59, second=59)
        mock_result = (mock_start, mock_end, "Test Label", "Test note")

        # Evaluate confidence
        confidence = _evaluate_llm_confidence(query, mock_result)
        print(f"  Calculated Confidence: {confidence:.3f}")

        # Decision
        if confidence >= threshold:
            print(f"  ✅ LLM sonucu kullanılacak (≥ {threshold})")
        else:
            print(f"  ❌ Regex fallback kullanılacak (< {threshold})")

def show_cache_performance():
    """Display cache performance statistics."""
    print("\n" + "="*60)
    print("CACHE PERFORMANS İSTATİSTİKLERİ")
    print("="*60)

    stats = get_cache_stats()
    total_requests = stats['hits'] + stats['misses']

    if total_requests > 0:
        hit_rate = (stats['hits'] / total_requests) * 100
        print(f"Toplam İstek: {total_requests}")
        print(f"Cache Hit: {stats['hits']}")
        print(f"Cache Miss: {stats['misses']}")
        print(f"Hit Rate: {hit_rate:.1f}%")
        print(f"Regex Çağrıları: {stats['regex_calls']}")
        print(f"LLM Çağrıları: {stats['llm_calls']}")
    else:
        print("Henüz cache istatistiği yok")

    print("="*60)

def test_whatsapp_normalization():
    """Test WhatsApp ID normalization."""
    print("\n" + "="*60)
    print("WHATSAPP ID NORMALIZATION TEST")
    print("="*60)

    test_ids = [
        "+905306897885",
        "905306897885",
        "05306897885",
        "5306897885",
        "+905306897885@c.us",
        "invalid-id",
        "",
        None,
    ]

    print("WhatsApp ID Normalization Tests:")
    for test_id in test_ids:
        try:
            result = _normalize_whatsapp_identifier(test_id)
            if result:
                print(f"  ✅ {test_id} -> {result}")
            else:
                print(f"  ⚠️ {test_id} -> No result")
        except Exception as e:
            print(f"  ❌ {test_id} -> Error: {str(e)}")

def test_cache_effectiveness():
    """Test cache effectiveness with repeated queries."""
    print("\n" + "="*60)
    print("CACHE EFFECTIVENESS TEST")
    print("="*60)

    # Reset cache stats
    reset_cache_stats()

    test_query = "geçen hafta"

    print(f"Testing repeated queries for: '{test_query}'")

    # First call - should be cache miss
    start_time = time.time()
    result1 = _resolve_order_history_timeframe(test_query)
    first_call_time = time.time() - start_time

    # Second call - should be cache hit
    start_time = time.time()
    result2 = _resolve_order_history_timeframe(test_query)
    second_call_time = time.time() - start_time

    # Third call - should be cache hit
    start_time = time.time()
    result3 = _resolve_order_history_timeframe(test_query)
    third_call_time = time.time() - start_time

    print(f"First call:  {first_call_time*1000:.2f}ms")
    print(f"Second call: {second_call_time*1000:.2f}ms")
    print(f"Third call:  {third_call_time*1000:.2f}ms")

    speedup = first_call_time / second_call_time if second_call_time > 0 else float('inf')
    print(f"Cache speedup: {speedup:.1f}x")

    # Show cache stats
    stats = get_cache_stats()
    print(f"Cache hits: {stats['hits']}, misses: {stats['misses']}")

if __name__ == "__main__":
    test_month_detection()
    test_edge_cases()
    test_performance()
    test_error_handling()
    test_confidence_scoring()
    test_whatsapp_normalization()
    test_cache_effectiveness()
    test_llm_timeframe_parsing()
    show_cache_performance()
