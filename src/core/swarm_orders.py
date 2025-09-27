"""Order handling helpers extracted from the legacy Swarm module."""
from __future__ import annotations

import os
import random
import time
import calendar
import functools
import logging
import traceback
from datetime import datetime, timedelta
import re
import json
from typing import Any, Dict, List, Tuple, TypedDict

from database_tools_fixed import db

import swarm_html
from swarm_context import (
    clear_selected_product_context,
    detect_quantity_input,
    get_selected_product_context,
    is_quantity_context_valid,
    parse_product_selection_message,
    store_selected_product_context,
)

# Cache statistics tracking
_cache_stats = {
    'hits': 0,
    'misses': 0,
    'llm_calls': 0,
    'regex_calls': 0
}

# LLM accuracy tracking for confidence scoring
_llm_accuracy_history = {}
_llm_confidence_thresholds = {
    'simple_patterns': 0.6,    # Basit kalıplar için düşük threshold
    'complex_patterns': 0.8,   # Karmaşık kalıplar için yüksek threshold
    'default': 0.7             # Genel threshold
}

# Performance monitoring
_performance_metrics = {
    'start_time': time.time(),
    'total_requests': 0,
    'successful_requests': 0,
    'failed_requests': 0,
    'llm_api_calls': 0,
    'regex_resolutions': 0,
    'cache_hits': 0,
    'cache_misses': 0,
    'total_response_time': 0.0,
    'llm_response_time': 0.0,
    'regex_response_time': 0.0,
    'memory_usage': [],
    'error_counts': {},
}

def get_performance_metrics() -> Dict[str, Any]:
    """Get comprehensive performance metrics."""
    current_time = time.time()
    uptime = current_time - _performance_metrics['start_time']

    # Calculate rates
    total_requests = _performance_metrics['total_requests']
    success_rate = (_performance_metrics['successful_requests'] / total_requests * 100) if total_requests > 0 else 0
    avg_response_time = (_performance_metrics['total_response_time'] / total_requests * 1000) if total_requests > 0 else 0

    return {
        'uptime_seconds': uptime,
        'total_requests': total_requests,
        'successful_requests': _performance_metrics['successful_requests'],
        'failed_requests': _performance_metrics['failed_requests'],
        'success_rate_percent': success_rate,
        'average_response_time_ms': avg_response_time,
        'llm_api_calls': _performance_metrics['llm_api_calls'],
        'regex_resolutions': _performance_metrics['regex_resolutions'],
        'cache_hit_rate_percent': calculate_cache_hit_rate(),
        'error_breakdown': _performance_metrics['error_counts'].copy(),
        'memory_usage_mb': get_memory_usage(),
    }

def calculate_cache_hit_rate() -> float:
    """Calculate cache hit rate percentage."""
    hits = _performance_metrics['cache_hits']
    misses = _performance_metrics['cache_misses']
    total = hits + misses
    return (hits / total * 100) if total > 0 else 0

def get_memory_usage() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil
        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024  # MB
    except ImportError:
        return 0.0

def record_request(success: bool, response_time: float, method: str):
    """Record request metrics."""
    _performance_metrics['total_requests'] += 1
    _performance_metrics['total_response_time'] += response_time

    if success:
        _performance_metrics['successful_requests'] += 1
    else:
        _performance_metrics['failed_requests'] += 1

    # Record method-specific metrics
    if method == 'llm':
        _performance_metrics['llm_api_calls'] += 1
        _performance_metrics['llm_response_time'] += response_time
    elif method == 'regex':
        _performance_metrics['regex_resolutions'] += 1
        _performance_metrics['regex_response_time'] += response_time

def record_error(error_type: str):
    """Record error occurrence."""
    _performance_metrics['error_counts'][error_type] = _performance_metrics['error_counts'].get(error_type, 0) + 1

def record_cache_hit():
    """Record cache hit."""
    _performance_metrics['cache_hits'] += 1

def record_cache_miss():
    """Record cache miss."""
    _performance_metrics['cache_misses'] += 1

# Constants
DEFAULT_CACHE_SIZE = 500
MAX_INPUT_LENGTH = 500
CONFIDENCE_THRESHOLDS = {
    'simple_patterns': 0.6,
    'complex_patterns': 0.8,
    'default': 0.7
}
MAX_LLM_RETRIES = 3
CACHE_TTL_SECONDS = 3600

# Enhanced logging system
def setup_logging() -> logging.Logger:
    """
    Setup structured logging for the application.

    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger('swarm_orders')
    logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with detailed formatting
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Structured formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

# Global logger instance
logger = setup_logging()

# Error classification
class OrderError(Exception):
    """Base exception for order-related errors."""
    pass

class TimeframeParsingError(OrderError):
    """Error in timeframe parsing."""
    pass

class DatabaseError(OrderError):
    """Database operation error."""
    pass

class LLMError(OrderError):
    """LLM API related error."""
    pass

class ValidationError(OrderError):
    """Input validation error."""
    pass

def log_error_with_context(logger, error, context: Dict[str, Any], error_type: str = "GENERAL"):
    """Log error with structured context information."""
    error_context = {
        'error_type': error_type,
        'error_message': str(error),
        'timestamp': datetime.now().isoformat(),
        **context
    }

    logger.error(
        f"[{error_type}] {str(error)}",
        extra={'context': error_context, 'traceback': traceback.format_exc()}
    )

    return error_context

def safe_database_operation(operation_name: str, operation_func, *args, **kwargs):
    """Safely execute database operations with error handling."""
    try:
        logger.debug(f"DB operation starting: {operation_name}")
        result = operation_func(*args, **kwargs)
        logger.debug(f"DB operation completed: {operation_name}")
        return result

    except Exception as e:
        context = {
            'operation': operation_name,
            'args_count': len(args),
            'kwargs_keys': list(kwargs.keys())
        }
        log_error_with_context(logger, e, context, "DATABASE_ERROR")
        raise DatabaseError(f"Database operation failed: {operation_name}") from e

def safe_llm_operation(operation_name: str, operation_func, *args, **kwargs):
    """Safely execute LLM operations with error handling and retry logic."""
    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            logger.debug(f"LLM operation attempt {attempt + 1}: {operation_name}")
            result = operation_func(*args, **kwargs)
            logger.debug(f"LLM operation succeeded: {operation_name}")
            return result

        except Exception as e:
            context = {
                'operation': operation_name,
                'attempt': attempt + 1,
                'max_retries': max_retries,
                'args_count': len(args),
                'kwargs_keys': list(kwargs.keys())
            }

            if attempt == max_retries - 1:
                # Last attempt failed
                log_error_with_context(logger, e, context, "LLM_ERROR")
                raise LLMError(f"LLM operation failed after {max_retries} attempts: {operation_name}") from e
            else:
                # Retry after delay
                logger.warning(f"LLM operation failed, retrying in {retry_delay}s: {operation_name}")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

def validate_and_sanitize_input(input_value: str, input_type: str) -> str:
    """Validate and sanitize user input with comprehensive checks."""
    try:
        if not isinstance(input_value, str):
            raise ValidationError(f"Input must be string, got {type(input_value)}")

        # Basic sanitization
        sanitized = input_value.strip()

        # Length validation
        if len(sanitized) > 500:
            raise ValidationError("Input too long (>500 characters)")

        if len(sanitized) < 1:
            raise ValidationError("Input too short (empty)")

        # Type-specific validation
        if input_type == "timeframe":
            # Check for potentially dangerous patterns
            dangerous_patterns = ['<script', 'javascript:', 'eval(', 'exec(']
            for pattern in dangerous_patterns:
                if pattern.lower() in sanitized.lower():
                    raise ValidationError(f"Potentially dangerous content detected: {pattern}")

        elif input_type == "whatsapp_id":
            # WhatsApp ID format validation
            if not re.match(r'^[\d\+\-\@\.\s]+$', sanitized):
                raise ValidationError("Invalid WhatsApp ID format")

        logger.debug(f"Input validated: {input_type} - {len(sanitized)} chars")
        return sanitized

    except ValidationError:
        raise
    except Exception as e:
        logger.error(f"Unexpected validation error: {e}")
        raise ValidationError(f"Input validation failed: {str(e)}") from e

def get_cache_stats() -> Dict[str, int]:
    """Get cache performance statistics."""
    return _cache_stats.copy()

def reset_cache_stats() -> None:
    """Reset cache statistics."""
    global _cache_stats
    _cache_stats = {'hits': 0, 'misses': 0, 'llm_calls': 0, 'regex_calls': 0}

def track_llm_accuracy(query: str, llm_result: tuple, was_correct: bool) -> None:
    """Track LLM accuracy for confidence scoring."""
    global _llm_accuracy_history

    # Extract pattern from query for categorization
    pattern = _extract_query_pattern(query)
    if pattern not in _llm_accuracy_history:
        _llm_accuracy_history[pattern] = []

    _llm_accuracy_history[pattern].append(was_correct)

    # Keep only last 20 results per pattern
    if len(_llm_accuracy_history[pattern]) > 20:
        _llm_accuracy_history[pattern] = _llm_accuracy_history[pattern][-20:]

def get_historical_accuracy(query: str) -> float:
    """Get historical accuracy score for query pattern."""
    global _llm_accuracy_history

    pattern = _extract_query_pattern(query)
    if pattern in _llm_accuracy_history and _llm_accuracy_history[pattern]:
        # Return accuracy of last 10 predictions
        recent_results = _llm_accuracy_history[pattern][-10:]
        return sum(recent_results) / len(recent_results)
    return 0.5  # Default neutral score

def _extract_query_pattern(query: str) -> str:
    """Extract pattern category from query."""
    query_lower = query.lower()

    # Simple patterns
    simple_patterns = [
        r'son\s+\d+\s+gun', r'son\s+\d+\s+hafta', r'bu\s+ay',
        r'gecen\s+ay', r'bu\s+yil', r'gecen\s+yil'
    ]

    for pattern in simple_patterns:
        if re.search(pattern, query_lower):
            return 'simple'

    # Complex patterns
    complex_indicators = [
        'başındaki', 'sonundaki', 'arası', 'civarı', 'yaklaşık',
        'haftanın', 'ayın', 'yılın'
    ]

    for indicator in complex_indicators:
        if indicator in query_lower:
            return 'complex'

    return 'medium'

def _validate_date_consistency(start_date: str, end_date: str) -> float:
    """Validate date consistency and return confidence score."""
    try:
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        # Check 1: Start date should be before end date
        if start > end:
            return 0.0

        # Check 2: Reasonable date range
        date_range = (end - start).days

        if date_range < 0:
            return 0.0
        elif date_range > 400:  # More than a year
            return 0.3
        elif date_range > 100:  # More than 3 months
            return 0.6
        elif date_range > 30:   # More than a month
            return 0.8
        else:
            return 1.0

    except (ValueError, TypeError):
        return 0.0

def _compare_with_regex_fallback(query: str, llm_result: tuple) -> float:
    """Compare LLM result with regex fallback and return similarity score."""
    try:
        # Get regex result for comparison
        regex_result = _resolve_order_history_timeframe(query)
        if not regex_result:
            return 0.5  # No regex fallback available

        llm_start, llm_end, llm_label, llm_note = llm_result
        regex_start, regex_end, regex_label, regex_note = regex_result

        # Convert to comparable format
        llm_start_date = llm_start.date() if hasattr(llm_start, 'date') else llm_start
        llm_end_date = llm_end.date() if hasattr(llm_end, 'date') else llm_end
        regex_start_date = regex_start.date() if hasattr(regex_start, 'date') else regex_start
        regex_end_date = regex_end.date() if hasattr(regex_end, 'date') else regex_end

        # Calculate date similarity
        date_similarity = 0.0
        if llm_start_date == regex_start_date and llm_end_date == regex_end_date:
            date_similarity = 1.0
        elif abs((llm_end_date - llm_start_date).days - (regex_end_date - regex_start_date).days) <= 1:
            date_similarity = 0.8
        elif abs((llm_end_date - llm_start_date).days - (regex_end_date - regex_start_date).days) <= 3:
            date_similarity = 0.6
        else:
            date_similarity = 0.2

        return date_similarity

    except Exception:
        return 0.5  # Default score on error

def _evaluate_llm_confidence(query: str, llm_result: tuple) -> float:
    """Multi-factor confidence evaluation for LLM results."""
    if not llm_result:
        return 0.0

    try:
        start_date, end_date, label, note = llm_result

        # Factor 1: Base LLM confidence (if available in note)
        base_confidence = 0.7  # Default
        if note and isinstance(note, str):
            if 'yüksek güven' in note.lower() or 'high confidence' in note.lower():
                base_confidence = 0.9
            elif 'orta güven' in note.lower() or 'medium confidence' in note.lower():
                base_confidence = 0.6
            elif 'düşük güven' in note.lower() or 'low confidence' in note.lower():
                base_confidence = 0.3

        # Factor 2: Date consistency
        date_consistency = _validate_date_consistency(start_date, end_date)

        # Factor 3: Regex comparison
        regex_similarity = _compare_with_regex_fallback(query, llm_result)

        # Factor 4: Historical accuracy
        historical_score = get_historical_accuracy(query)

        # Factor 5: Query pattern complexity
        pattern_type = _extract_query_pattern(query)
        pattern_multiplier = {
            'simple': 1.1,
            'medium': 1.0,
            'complex': 0.9
        }.get(pattern_type, 1.0)

        # Calculate weighted final confidence
        final_confidence = (
            base_confidence * 0.25 +      # LLM'in kendi değerlendirmesi
            date_consistency * 0.30 +    # Tarih tutarlılığı
            regex_similarity * 0.25 +    # Regex karşılaştırması
            historical_score * 0.20      # Geçmiş doğruluk
        ) * pattern_multiplier

        # Cap between 0 and 1
        return max(0.0, min(1.0, final_confidence))

    except Exception:
        return 0.0

def _get_adaptive_threshold(query: str) -> float:
    """Get adaptive confidence threshold based on query pattern."""
    global _llm_confidence_thresholds

    pattern_type = _extract_query_pattern(query)
    return _llm_confidence_thresholds.get(pattern_type, _llm_confidence_thresholds['default'])

def cache_time_resolution(func):
    """Cache decorator for time resolution functions with statistics tracking."""
    @functools.lru_cache(maxsize=1000)
    def wrapper(query: str, *args, **kwargs):
        _cache_stats['hits'] += 1
        return func(query, *args, **kwargs)

    def inner(query: str, *args, **kwargs):
        if not isinstance(query, str):
            _cache_stats['misses'] += 1
            return func(query, *args, **kwargs)

        cache_key = f"{query}:{args}:{kwargs}"

        # Check if we have cached result
        if hasattr(wrapper, '_cache_info'):
            if cache_key in wrapper._cache:
                _cache_stats['hits'] += 1
                return wrapper._cache[cache_key]

        _cache_stats['misses'] += 1
        result = func(query, *args, **kwargs)
        wrapper._cache[cache_key] = result
        return result

    # Copy cache info to wrapper
    wrapper._cache = {}
    wrapper._cache_info = getattr(func, 'cache_info', lambda: None)()
    return inner


MONTH_NAMES_TR = {
    1: "Ocak",
    2: "Şubat",
    3: "Mart",
    4: "Nisan",
    5: "Mayıs",
    6: "Haziran",
    7: "Temmuz",
    8: "Ağustos",
    9: "Eylül",
    10: "Ekim",
    11: "Kasım",
    12: "Aralık",
}

_MONTH_SYNONYM_MAP = {
    1: ["ocak", "ocak ayi", "january", "jan"],
    2: ["şubat", "subat", "subat ayi", "february", "feb"],
    3: ["mart", "mart ayi", "march", "mar"],
    4: ["nisan", "nisan ayi", "april", "apr"],
    5: ["mayıs", "mayis", "mayis ayi", "may"],
    6: ["haziran", "haziran ayi", "june", "jun"],
    7: ["temmuz", "temmuz ayi", "july", "jul"],
    8: ["ağustos", "agustos", "agustos ayi", "august", "aug"],
    9: ["eylül", "eylul", "eylul ayi", "september", "sep"],
    10: ["ekim", "ekim ayi", "october", "oct"],
    11: ["kasım", "kasim", "kasim ayi", "november", "nov"],
    12: ["aralık", "aralik", "aralik ayi", "december", "dec"],
}

_MONTH_KEYWORDS: Dict[str, int] = {}
for _month, _synonyms in _MONTH_SYNONYM_MAP.items():
    for _synonym in _synonyms:
        normalized = _synonym.lower()
        replacements = {
            "ı": "i",
            "ğ": "g",
            "ü": "u",
            "ş": "s",
            "ö": "o",
            "ç": "c",
        }
        for src, dst in replacements.items():
            normalized = normalized.replace(src, dst)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        _MONTH_KEYWORDS[normalized] = _month


@functools.lru_cache(maxsize=500)
def _normalize_whatsapp_identifier(value: str | None) -> str | None:
    """Ensure WhatsApp identifiers use the @c.us chat ID format."""
    if not value:
        return value
    raw = str(value).strip()
    if not raw:
        return raw
    if raw.endswith('@c.us'):
        return raw

    digits = re.sub(r'\D', '', raw)
    if not digits:
        return raw

    if digits.startswith('90') and len(digits) >= 11:
        formatted = digits
    elif digits.startswith('0') and len(digits) >= 11:
        formatted = '9' + digits
    elif digits.startswith('5') and len(digits) >= 10:
        formatted = '90' + digits
    else:
        formatted = digits

    return formatted + '@c.us'


@functools.lru_cache(maxsize=1000)
def _normalize_timeframe_text(value: str) -> str:
    """Enhanced Turkish text normalization with comprehensive character support."""
    if not value:
        return value

    # Comprehensive Turkish character replacements (both cases)
    replacements = {
        # Lowercase mappings
        "ı": "i", "i̇": "i",  # dotted i and dotless ı
        "ğ": "g", "ğ": "g",
        "ü": "u", "ü": "u",
        "ş": "s", "ş": "s",
        "ö": "o", "ö": "o",
        "ç": "c", "ç": "c",
        # Uppercase mappings
        "İ": "i", "İ": "i",
        "Ğ": "g", "Ğ": "g",
        "Ü": "u", "Ü": "u",
        "Ş": "s", "Ş": "s",
        "Ö": "o", "Ö": "o",
        "Ç": "c", "Ç": "c",
        # Arabic characters (sometimes used in Turkish)
        "â": "a", "Â": "a",
        "î": "i", "Î": "i",
        "û": "u", "Û": "u",
        # Common typos and variations
        "ei": "ey", "Ei": "Ey", "eı": "eyi", "Eı": "Eyi",
        "ai": "ay", "Ai": "Ay", "aı": "ayi", "Aı": "Ayi",
        "oi": "oy", "Oi": "Oy", "oı": "oyi", "Oı": "Oyi",
        "ui": "uy", "Ui": "Uy", "uı": "uyi", "Uı": "Uyi",
        "ii": "iyi", "Ii": "Iyi", "ıı": "iyi", "İi": "Iyi",
    }

    normalized = value.lower()

    # Apply character replacements
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)

    # Handle special Turkish cases
    normalized = normalized.replace('-', ' ')
    normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)

    # Fix common Turkish word patterns
    normalized = re.sub(r'(^|\s)on(\s+\d+\s+gun)', lambda m: m.group(1) + 'son' + m.group(2), normalized)
    normalized = re.sub(r'(\d+)\s+hafta\s+once(?:ki)?', r'son \1 hafta', normalized)
    normalized = re.sub(r'son(\d+)', r'son \1', normalized)

    # Handle Turkish number words
    turkish_numbers = {
        'bir': '1', 'iki': '2', 'üç': '3', 'dört': '4', 'beş': '5',
        'altı': '6', 'yedi': '7', 'sekiz': '8', 'dokuz': '9', 'on': '10'
    }

    for turkish, digit in turkish_numbers.items():
        normalized = re.sub(rf'\b{re.escape(turkish)}\b', digit, normalized)

    return normalized.strip()



def _parse_user_date(value: str, *, is_start: bool) -> datetime:
    """Parse user-provided date string into datetime."""
    if value is None:
        raise ValueError('Tarih değeri bulunamadı')
    value_str = str(value).strip()
    if not value_str:
        raise ValueError('Boş tarih değeri')

    try:
        if len(value_str) == 10:
            base = datetime.strptime(value_str, '%Y-%m-%d')
        else:
            base = datetime.fromisoformat(value_str)
    except ValueError as exc:
        raise ValueError(f"Geçersiz tarih formatı: {value_str}") from exc

    if is_start:
        return base.replace(hour=0, minute=0, second=0, microsecond=0)
    if len(value_str) == 10:
        return base.replace(hour=23, minute=59, second=59, microsecond=999999)
    return base



@functools.lru_cache(maxsize=500)
def _resolve_order_history_timeframe(timeframe_text: str | None):
    """Resolve natural language timeframe via regex patterns with enhanced error handling."""
    from datetime import datetime, timedelta
    import calendar

    # Track regex calls
    global _cache_stats
    _cache_stats['regex_calls'] += 1

    logger.debug(f"Timeframe resolution starting: {timeframe_text}")

    now = datetime.now()
    default_start = datetime(now.year, now.month, 1)
    default_end = now
    default_label = f"{MONTH_NAMES_TR[now.month]} {now.year}"

    if not timeframe_text:
        return default_start, default_end, default_label, None

    original = timeframe_text.strip()
    normalized = _normalize_timeframe_text(original)
    if not normalized:
        return default_start, default_end, default_label, "Belirtilen zaman aralığı anlaşılamadı. Varsayılan olarak bu ay listeleniyor."

    if 'bu ay' in normalized or 'current month' in normalized or 'this month' in normalized:
        return default_start, default_end, default_label, None

    if 'gecen ay' in normalized or 'last month' in normalized or 'previous month' in normalized:
        year = now.year
        month = now.month - 1
        if month == 0:
            month = 12
            year -= 1
        start_prev = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end_prev = datetime(year, month, last_day, 23, 59, 59)
        label = f"{MONTH_NAMES_TR.get(month, f'Ay {month}')} {year}"
        return start_prev, end_prev, label, None

    if 'bu yil' in normalized or 'bu sene' in normalized or 'this year' in normalized or 'current year' in normalized:
        start_year = datetime(now.year, 1, 1)
        label = f"{now.year} (Bu Yıl)"
        return start_year, default_end, label, None

    if 'gecen yil' in normalized or 'gecen sene' in normalized or 'last year' in normalized or 'previous year' in normalized:
        year = now.year - 1
        start_year = datetime(year, 1, 1)
        end_year = datetime(year, 12, 31, 23, 59, 59)
        label = f"{year}"
        return start_year, end_year, label, None

    # Enhanced day patterns
    day_patterns = [
        (r'son\s+(\d+)\s+gun(?:luk)?', 'days'),
        (r'(\d+)\s+gun\s+once', 'days_ago'),
        (r'(\d+)\s+gunluk', 'days_period'),
    ]

    for pattern, pattern_type in day_patterns:
        day_match = re.search(pattern, normalized)
        if day_match:
            days = max(1, int(day_match.group(1)))
            if pattern_type == 'days_ago':
                start_range = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_range = (now - timedelta(days=days-1)).replace(hour=23, minute=59, second=59, microsecond=999999)
                label = f"{days} Gün Önce"
            else:
                start_range = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
                label = f"Son {days} Gün"
            return start_range, default_end, label, None

    # Enhanced week patterns
    week_patterns = [
        (r'son\s+(\d+)\s+hafta', 'weeks'),
        (r'(\d+)\s+hafta\s+once', 'weeks_ago'),
        (r'gecen\s+hafta', 'last_week'),
        (r'gecen\s+hafta(?:nin)?', 'last_week'),
        (r'onceki\s+hafta', 'previous_week'),
        (r'son\s+hafta', 'last_week'),
        (r'bu\s+hafta', 'this_week'),
    ]

    for pattern, pattern_type in week_patterns:
        week_match = re.search(pattern, normalized)
        if week_match:
            if pattern_type in ['last_week', 'previous_week', 'gecen']:
                # Geçen haftanın başlangıç ve bitişi
                days_since_monday = now.weekday()  # 0=Monday, 6=Sunday
                start_week = (now - timedelta(days=days_since_monday + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_week = (now - timedelta(days=days_since_monday + 1)).replace(hour=23, minute=59, second=59, microsecond=999999)
                label = "Geçen Hafta"
            elif pattern_type == 'this_week':
                # Bu haftanın başlangıç ve bitişi
                days_since_monday = now.weekday()
                start_week = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
                label = "Bu Hafta"
                end_week = default_end
            elif pattern_type == 'weeks_ago':
                weeks = max(1, int(week_match.group(1)))
                start_week = (now - timedelta(days=weeks * 7)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_week = (now - timedelta(days=(weeks-1) * 7)).replace(hour=23, minute=59, second=59, microsecond=999999)
                label = f"{weeks} Hafta Önce"
            else:
                weeks = max(1, int(week_match.group(1)))
                start_week = (now - timedelta(days=weeks * 7)).replace(hour=0, minute=0, second=0, microsecond=0)
                label = f"Son {weeks} Hafta"
                end_week = default_end

            return start_week, end_week, label, None

    if any(keyword in normalized for keyword in ['bugun', 'bugunku', 'bu gun']):
        start_range = datetime(now.year, now.month, now.day)
        label = 'Bugün'
        return start_range, default_end, label, None

    if any(keyword in normalized for keyword in ['dun', 'dunku', 'gecen gun']):
        yesterday = datetime(now.year, now.month, now.day) - timedelta(days=1)
        start_range = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end_range = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        label = 'Dün'
        return start_range, end_range, label, None

    if 'son ay' in normalized or 'son bir ay' in normalized or 'son 1 ay' in normalized:
        start_range = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        label = 'Son 1 Ay'
        return start_range, default_end, label, None

    # Enhanced period patterns (after Turkish normalization: ayın -> ayin)
    period_patterns = [
        (r'ayin\s+basi', 'month_start'),
        (r'ayin\s+sonu', 'month_end'),
        (r'ayin\s+orta', 'month_middle'),
        (r'hafta\s+sonu', 'weekend'),
        (r'hafta\s+ici', 'weekday'),
    ]

    for pattern, period_type in period_patterns:
        if re.search(pattern, normalized):
            if period_type == 'month_start':
                # Ayın ilk 10 günü
                start_range = datetime(now.year, now.month, 1)
                end_range = datetime(now.year, now.month, min(10, calendar.monthrange(now.year, now.month)[1]), 23, 59, 59)
                label = 'Ayın Başı'
            elif period_type == 'month_end':
                # Ayın son 10 günü
                last_day = calendar.monthrange(now.year, now.month)[1]
                start_range = datetime(now.year, now.month, max(1, last_day-9))
                end_range = default_end
                label = 'Ayın Sonu'
            elif period_type == 'weekend':
                # Bu hafta sonu (Cumartesi ve Pazar)
                days_to_saturday = (5 - now.weekday()) % 7  # 5=Cumartesi
                if days_to_saturday == 0:  # Zaten cumartesi
                    saturday = now
                else:
                    saturday = now + timedelta(days=days_to_saturday)
                start_range = saturday.replace(hour=0, minute=0, second=0, microsecond=0)
                sunday = saturday + timedelta(days=1)
                end_range = sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
                label = 'Hafta Sonu'
            else:
                continue
            return start_range, end_range, label, None

    month_window_match = re.search(r'son\s+(\d+)\s+ay', normalized)
    if month_window_match:
        months = max(1, int(month_window_match.group(1)))
        months = min(months, 24)
        target_year = now.year
        target_month = now.month - (months - 1)
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        start_range = datetime(target_year, target_month, 1)
        label = f"Son {months} Ay"
        return start_range, default_end, label, None

    year_match = re.search(r'(19|20)\d{2}', normalized)
    year_candidate = int(year_match.group(0)) if year_match else None
    if year_candidate is None:
        if 'gecen yil' in normalized or 'gecen sene' in normalized:
            year_candidate = now.year - 1
        elif 'bu yil' in normalized or 'bu sene' in normalized:
            year_candidate = now.year

    for keyword, month in _MONTH_KEYWORDS.items():
        if re.search(rf'\b{re.escape(keyword)}\b', normalized):
            year = year_candidate or now.year
            last_day = calendar.monthrange(year, month)[1]
            start_month = datetime(year, month, 1)
            end_month = datetime(year, month, last_day, 23, 59, 59)
            if year == now.year and month == now.month:
                end_month = default_end
            label = f"{MONTH_NAMES_TR.get(month, f'Ay {month}')} {year}"
            return start_month, end_month, label, None

    if year_candidate:
        year = year_candidate
        start_year = datetime(year, 1, 1)
        end_year = datetime(year, 12, 31, 23, 59, 59)
        if year == now.year:
            end_year = default_end
        label = f"{year}"
        return start_year, end_year, label, None

        fallback_note = f"Belirtilen zaman aralığı ('{original}') anlaşılamadı. Varsayılan olarak bu ay listelendi."
        logger.warning(f"Timeframe pattern not recognized: {original}")
        return default_start, default_end, default_label, fallback_note



def _extract_first_json_object(text: str) -> str | None:
    """Attempt to find the first JSON object within a model response."""
    if not text:
        return None
    text = text.strip()
    if not text:
        return None
    if text.startswith('{') and text.endswith('}'):
        return text
    stack = 0
    start_idx: int | None = None
    for idx, char in enumerate(text):
        if char == '{':
            if stack == 0:
                start_idx = idx
            stack += 1
        elif char == '}':
            if stack:
                stack -= 1
                if stack == 0 and start_idx is not None:
                    return text[start_idx:idx + 1]
    return None


def _llm_resolve_order_history_timeframe(timeframe_text: str | None):
    """Resolve natural language timeframe via LLM with enhanced error handling."""
    try:
        # Track LLM calls
        global _cache_stats
        _cache_stats['llm_calls'] += 1

        # Input validation
        if timeframe_text is None:
            return None
        if isinstance(timeframe_text, str):
            query = timeframe_text.strip()
            if not query:
                return None
            if query.isdigit():
                return None
        else:
            return None

        logger.debug(f"LLM timeframe resolution starting: {query}")

    except Exception as e:
        logger.error(f"LLM validation error: {e}")
        return None

    try:
        from swarm_config import openrouter_client, OPENROUTER_MODEL
    except ImportError:
        print('[LLM TIMEFRAME] swarm_config import edilemedi')
        return None

    if not openrouter_client:
        print('[LLM TIMEFRAME] OpenRouter client mevcut değil')
        return None

    reference_now = datetime.now()
    system_prompt = (
        'You are a date-range parser for a Turkish B2B order history system. '
        f"Reference datetime is {reference_now.strftime('%Y-%m-%dT%H:%M:%S')}. "
        'Interpret the customer message and respond with ONLY a JSON object containing '
        'start_date, end_date, label, confidence, note. Use ISO 8601 format. '
        'For single-day requests set start_date to 00:00:00 and end_date to 23:59:59. '
        'If unsure set confidence to 0. '
        'All JSON values must be written in Turkish (use short labels like "Geçen Cuma" and brief Turkish notes). '
        'Return strictly JSON with no extra text.'
    )
    user_prompt = (
        "Customer timeframe request:\n"
        f"{query}\n\n"
        "Return JSON only."
    )

    try:
        completion = openrouter_client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
        )
    except Exception as exc:
        print(f'[LLM TIMEFRAME] OpenRouter hatası: {exc}')
        return None

    try:
        content = (completion.choices[0].message.content or '').strip()
    except (AttributeError, IndexError):
        print('[LLM TIMEFRAME] Beklenmeyen LLM yanıt formatı')
        return None

    json_payload = _extract_first_json_object(content)
    if not json_payload:
        print(f"[LLM TIMEFRAME] JSON bulunamadı: {content[:120]}")
        return None

    try:
        data = json.loads(json_payload)
    except json.JSONDecodeError as exc:
        print(f'[LLM TIMEFRAME] JSON decode hatası: {exc}')
        return None

    start_raw = data.get('start_date') or data.get('start')
    end_raw = data.get('end_date') or data.get('end')
    label = data.get('label') or data.get('summary') or query
    note = data.get('note') or data.get('explanation')

    if not start_raw or not end_raw:
        print('[LLM TIMEFRAME] start_date veya end_date yok')
        return None

    try:
        start_dt = _parse_user_date(start_raw, is_start=True)
        end_dt = _parse_user_date(end_raw, is_start=False)
    except ValueError as exc:
        print(f'[LLM TIMEFRAME] Tarih parse hatası: {exc}')
        return None

    if start_dt > end_dt:
        print(f"[LLM TIMEFRAME] Başlangıç bitişten büyük: {query}")
        return None

    # Enhanced confidence evaluation
    raw_confidence = data.get('confidence', 0.7)
    llm_result = (start_dt, end_dt, str(label), str(note) if note else '')

    # Multi-factor confidence evaluation
    final_confidence = _evaluate_llm_confidence(query, llm_result)

    # Adaptive threshold based on query pattern
    threshold = _get_adaptive_threshold(query)

    print(f"[LLM TIMEFRAME] Query: {query}")
    print(f"[LLM TIMEFRAME] Raw confidence: {raw_confidence}")
    print(f"[LLM TIMEFRAME] Final confidence: {final_confidence:.3f}")
    print(f"[LLM TIMEFRAME] Threshold: {threshold}")

    if final_confidence < threshold:
        print(f"[LLM TIMEFRAME] Düşük güven ({final_confidence:.3f} < {threshold}) - fallback")
        return None

        # Track accuracy for future improvements
        track_llm_accuracy(query, llm_result, True)  # Assume correct for now

        note_text = str(note) if note else 'Zaman aralığı yapay zeka tarafından yorumlandı.'
        logger.info(f"LLM timeframe resolution completed: {query} -> {label}")
        return start_dt, end_dt, str(label), note_text


def handle_product_selection(whatsapp_number: str, selection_message: str) -> str:
    """Handle ÜRÜN_SEÇİLDİ intent - extract product details and ask for quantity"""
    try:
        # Parse the product selection message
        parsed = parse_product_selection_message(selection_message)
        
        if not parsed['success']:
            return f"[ERROR] Ürün seçim mesajı formatı hatalı: {parsed.get('error', 'Bilinmeyen hata')}"
        
        product_code = parsed['product_code']
        product_name = parsed['product_name']
        price = parsed['price']
        
        print(f"[PRODUCT SELECTION] {whatsapp_number}: {product_code} - {product_name} - {price} TL")
        
        # Verify product exists in database and get current stock info
        result = db.get_stock_info(product_code)
        if not result.get('success'):
            return f"[ERROR] ÜRÜN DOĞRULAMA HATASI: {product_code} - {result.get('error', 'Ürün bulunamadı')}"
        
        # Get actual database values
        db_name = result['product_name']
        db_price = result['price']
        available_stock = result['stock_quantity']
        
        # Store in context for next step (quantity input)
        product_data = {
            'product_code': product_code,
            'product_name': db_name,  # Use database name (more reliable)
            'price': db_price  # Use database price (more reliable)
        }
        store_selected_product_context(whatsapp_number, product_data)
        
        # Create product confirmation + quantity request message
        response = f" ÜRÜN SEÇİMİ ONAYLANDI!\n"
        response += "="*35 + "\n\n"
        response += f"[PRODUCT] Ürün: {db_name}\n"
        response += f" Kod: {product_code}\n"
        response += f"[PRICE] Fiyat: {db_price:.2f} TL\n"
        
        # Stock status
        if available_stock <= 0:
            response += f" STOKTA YOK - Temin süresi: 7-10 gün\n"
        elif available_stock <= 10:
            response += f" DÜŞÜK STOK: {available_stock} adet\n"
        else:
            response += f"[OK] Stokta: {available_stock} adet\n"
            
        response += "\n" + "-"*35 + "\n"
        response += " KAÇ ADET İSTİYORSUNUZ?\n\n"
        
        if available_stock > 0:
            response += f" 1-{min(available_stock, 999)} adet arası girin\n"
        else:
            response += f" 1-999 adet arası girin (temin edilecek)\n"
            
        response += " Örnek: '5' veya '10'\n\n"
        response += "[ERROR] İptal için: 'iptal' yazın"
        
        return response
        
    except Exception as e:
        return f"[ERROR] Ürün seçim işleme hatası: {str(e)}"

# ===================== TASK 2.5: ENHANCED QUANTITY INPUT DETECTION =====================


def generate_order_number() -> str:
    """Unique order number oluştur"""
    try:
        cursor = db.connection.cursor()
        cursor.execute("SELECT 'ORD-' || TO_CHAR(CURRENT_DATE, 'YYYY') || '-' || LPAD(nextval('order_number_seq')::text, 4, '0')")
        order_number = cursor.fetchone()[0]
        cursor.close()
        return order_number
    except Exception as e:
        return f"ORD-2025-ERR{random.randint(1000,9999)}"


def save_order(whatsapp_number: str, items_with_quantities: dict, total_amount: float) -> str:
    """Siparişi veritabanına kaydet - Single Product için optimize edildi"""
    try:
        cursor = db.connection.cursor()
        
        # Sipariş numarası oluştur
        order_number = generate_order_number()
        
        # Ana sipariş kaydı
        cursor.execute("""
            INSERT INTO orders (order_number, whatsapp_number, status, total_amount)
            VALUES (%s, %s, 'CONFIRMED', %s)
            RETURNING id
        """, [order_number, whatsapp_number, total_amount])
        
        order_id = cursor.fetchone()[0]
        
        # Sipariş detayları - Single product için
        for product_code, details in items_with_quantities.items():
            cursor.execute("""
                INSERT INTO order_items (order_id, product_code, product_name, quantity, unit_price, total_price)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, [
                order_id,
                product_code,
                details['product_name'],
                details['quantity'], 
                details['unit_price'],
                details['total_price']
            ])
        
        db.connection.commit()
        cursor.close()
        
        return f"SIPARIS KAYDEDILDI: {order_number} (ID: {order_id})"
        
    except Exception as e:
        db.connection.rollback()
        return f"SIPARIS KAYIT HATASI: {str(e)}"


def create_order_confirmation_message(order_number: str, order_data: dict, total_amount: float) -> str:
    """Enhanced order confirmation message oluştur - tek veya çoklu ürünleri destekler"""
    try:
        from datetime import datetime

        if not order_data:
            return f"[ERROR] Sipariş detayları oluşturulamadı: Ürün listesi boş"

        items_map = order_data.get('items') if isinstance(order_data, dict) and 'items' in order_data else order_data
        if not isinstance(items_map, dict) or not items_map:
            return f"[ERROR] Sipariş detayları oluşturulamadı: Ürün listesi hatalı"

        item_entries = list(items_map.items())
        product_count = len(item_entries)
        total_units = sum(int(details.get('quantity', 0) or 0) for _, details in item_entries)

        lines: list[str] = []
        lines.append(" SİPARİŞ ONAY MESAJI ")
        lines.append("=" * 35)
        lines.append("")
        lines.append(f" SİPARİŞ NO: {order_number}")
        lines.append(f" TARİH: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        lines.append("")
        lines.append(" SİPARİŞ DETAYI:")
        lines.append("-" * 35)

        for idx, (product_code, details) in enumerate(item_entries, 1):
            product_name = details.get('product_name', product_code)
            quantity = int(details.get('quantity', 0) or 0)
            unit_price = float(details.get('unit_price', 0) or 0)
            line_total = float(details.get('total_price', unit_price * quantity) or 0)

            stock_info = details.get('available_stock')
            try:
                stock_quantity = int(stock_info) if stock_info is not None else None
            except (TypeError, ValueError):
                stock_quantity = None

            if product_count > 1:
                lines.append(f"{idx}. {product_name}")
            else:
                lines.append(f"[PRODUCT] Ürün: {product_name}")
            lines.append(f"   [PRODUCT] Kod: {product_code}")
            lines.append(f"    Miktar: {quantity} adet")
            lines.append(f"   [PRICE] Birim Fiyat: {unit_price:.2f} TL")
            lines.append(f"    Toplam: {line_total:.2f} TL")

            if stock_quantity is not None:
                if stock_quantity <= 0:
                    lines.append("   ⚠️ Stokta yok - Tedarik süresi 7-10 gün")
                elif stock_quantity < quantity:
                    lines.append(f"   ⚠️ Yetersiz stok: {stock_quantity} adet mevcut")
                elif stock_quantity <= 10:
                    lines.append(f"   ⚠️ Düşük stok: {stock_quantity} adet kaldı")
                else:
                    lines.append(f"   [OK] Stokta: {stock_quantity} adet")

            lines.append("")

        lines.append("-" * 35)
        if product_count > 1:
            lines.append(f" KALEM SAYISI: {product_count}")
            lines.append(f" TOPLAM ADET: {total_units} adet")
            lines.append("-" * 35)
        lines.append(f" GENEL TOPLAM: {float(total_amount):.2f} TL")
        lines.append("-" * 35)
        lines.append("")
        lines.append("[OK] Siparişiniz başarıyla alınmıştır!")
        lines.append(" Bizi tercih ettiğiniz için teşekkür ederiz.")
        lines.append("")
        lines.append(" B2B Satış Merkezi")
        if product_count > 1:
            lines.append(" Çoklu Ürün Sipariş Sistemi")
        else:
            lines.append(" Tek Ürün Hızlı Sipariş Sistemi")

        return "\n".join(lines)

    except Exception as e:
        return f"SIPARIS ONAYLANDI: {order_number} - Detay mesajı oluşturulurken hata: {str(e)}"






def get_order_history(whatsapp_number: str, timeframe_text: str | None = None, limit: int | None = None, start_date: str | None = None, end_date: str | None = None) -> str:
    """Müşterinin sipariş geçmişini HTML tablo olarak getir."""
    try:
        normalized_whatsapp = _normalize_whatsapp_identifier(whatsapp_number)
        whatsapp_lookup = normalized_whatsapp or (str(whatsapp_number).strip() if whatsapp_number is not None else '')
        display_whatsapp = whatsapp_lookup

        if isinstance(limit, str):
            limit_str = limit.strip()
            limit = int(limit_str) if limit_str.isdigit() else None

        if isinstance(timeframe_text, int) and limit is None:
            limit = timeframe_text
            timeframe_text = None
        elif isinstance(timeframe_text, str):
            timeframe_digits = timeframe_text.strip()
            if timeframe_digits.isdigit() and limit is None:
                limit = int(timeframe_digits)
                timeframe_text = None

        if isinstance(limit, int) and limit <= 0:
            limit = None

        # If timeframe_text describes a date range (non-numeric), fetch full results
        if isinstance(timeframe_text, str):
            stripped_timeframe = timeframe_text.strip().lower()
            if stripped_timeframe and not stripped_timeframe.isdigit():
                limit = None

        if start_date or end_date:
            if not start_date or not end_date:
                return "[ERROR] start_date ve end_date birlikte gönderilmelidir."
            try:
                start_dt = _parse_user_date(start_date, is_start=True)
                end_dt = _parse_user_date(end_date, is_start=False)
            except ValueError as exc:
                return f"[ERROR] Tarih aralığı parse edilemedi: {exc}"
            if start_dt > end_dt:
                return "[ERROR] start_date end_date değerinden büyük olamaz."
            timeframe_label = f"{start_dt.strftime('%d/%m/%Y')} - {end_dt.strftime('%d/%m/%Y')}"
            timeframe_note = None
        else:
            llm_result = _llm_resolve_order_history_timeframe(timeframe_text)
            if llm_result:
                start_dt, end_dt, timeframe_label, timeframe_note = llm_result
            else:
                start_dt, end_dt, timeframe_label, timeframe_note = _resolve_order_history_timeframe(timeframe_text)

        cursor = db.connection.cursor()
        query = (
            "SELECT o.order_number, o.status, o.total_amount, "
            "COALESCE(o.order_date, o.created_at) AS order_timestamp, "
            "COUNT(oi.id) AS item_count "
            "FROM orders o "
            "LEFT JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.whatsapp_number = %s "
            "AND COALESCE(o.order_date, o.created_at) BETWEEN %s AND %s "
            "GROUP BY o.id, o.order_number, o.status, o.total_amount, COALESCE(o.order_date, o.created_at) "
            "ORDER BY COALESCE(o.order_date, o.created_at) DESC"
        )
        params = [whatsapp_lookup, start_dt, end_dt]

        if limit is not None:
            try:
                limit = int(limit)
                if limit > 0:
                    query += " LIMIT %s"
                    params.append(limit)
            except ValueError:
                # Invalid limit, ignore
                pass

        cursor.execute(query, params)
        orders = cursor.fetchall()
        cursor.close()

        if not orders:
            message = f"{timeframe_label} için sipariş bulunamadı."
            if timeframe_note:
                message += f"\n{timeframe_note}"
            return message

        orders_data = []
        for order_num, status, total, order_timestamp, item_count in orders:
            status_tr = {
                'confirmed': 'Onaylandı',
                'draft': 'Taslak',
                'cancelled': 'İptal Edildi'
            }.get(status.lower(), status)

            date_str = order_timestamp.strftime('%d/%m/%Y %H:%M') if order_timestamp else 'Bilinmiyor'

            orders_data.append({
                'order_number': order_num,
                'status': status,
                'status_tr': status_tr,
                'total_amount': float(total),
                'created_at': date_str,
                'item_count': item_count
            })

        timestamp = str(int(time.time() * 1000))
        whatsapp_clean = (display_whatsapp or '').replace('@c.us', '').replace('+', '')
        html_filename = f"order_history_{whatsapp_clean}_{timestamp}.html"
        html_path = f"{os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')}/{html_filename}"

        html_content = swarm_html.generate_order_history_html(
            orders_data,
            display_whatsapp,
            html_filename,
            timeframe_label,
            timeframe_note
        )

        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"[HTML CREATED] {html_path}")

        tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
        history_link = f"{tunnel_url}/products/{html_filename}"

        orders_count = len(orders)

        response = "🛒 SİPARİŞ GEÇMİŞİ\n"
        response += "=" * 25 + "\n\n"
        response += f"{timeframe_label} için {orders_count} sipariş bulundu.\n\n"
        response += f"{history_link}\n\n"
        if timeframe_note:
            response += f"{timeframe_note}\n\n"
        response += "Detaylı sipariş geçmişinizi görmek için linke tıklayın."

        return response

    except Exception as e:
        return f"SIPARIS GECMISI HATASI: {str(e)}"


def get_all_orders_for_customer(whatsapp_number: str) -> list:
    """Get all orders for a customer with items"""
    try:
        lookup_number = _normalize_whatsapp_identifier(whatsapp_number) or (str(whatsapp_number).strip() if whatsapp_number is not None else '')
        cursor = db.connection.cursor()

        # Get all orders
        cursor.execute("""
            SELECT id, order_number, status, total_amount, created_at
            FROM orders
            WHERE whatsapp_number = %s
            ORDER BY created_at DESC
        """, [lookup_number])

        orders = cursor.fetchall()

        result = []
        for order_row in orders:
            order_id, order_number, status, total_amount, created_at = order_row

            # Get order items
            cursor.execute("""
                SELECT product_code, product_name, quantity, unit_price, total_price
                FROM order_items
                WHERE order_id = %s
                ORDER BY id
            """, [order_id])

            items = cursor.fetchall()
            items_list = []
            for item in items:
                items_list.append({
                    'product_code': item[0],
                    'product_name': item[1],
                    'quantity': item[2],
                    'unit_price': float(item[3]),
                    'total_price': float(item[4])
                })

            result.append({
                'order_number': order_number,
                'status': status,
                'total_amount': float(total_amount),
                'created_at': created_at.strftime('%d/%m/%Y %H:%M') if created_at else 'Bilinmiyor',
                'items': items_list
            })

        cursor.close()
        return result

    except Exception as e:
        print(f"[ERROR] get_all_orders_for_customer: {str(e)}")
        return []


def show_order_details_html(whatsapp_number: str) -> str:
    """Generate order details HTML and return link"""
    try:
        orders = get_all_orders_for_customer(whatsapp_number)

        if not orders:
            return "Sipariş geçmişiniz bulunmuyor. Henüz hiç sipariş oluşturmadınız."

        # Generate HTML
        timestamp = str(int(time.time() * 1000))
        whatsapp_clean = (display_whatsapp or '').replace('@c.us', '').replace('+', '')
        html_filename = f"orders_{whatsapp_clean}_{timestamp}.html"
        html_path = f"{os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')}/{html_filename}"

        tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
        html_content = swarm_html.generate_order_details_html(orders, whatsapp_number, html_filename, tunnel_url)

        # Save HTML file
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        print(f"[HTML CREATED] {html_path}")

        # Return link
        tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
        order_link = f"{tunnel_url}/products/{html_filename}"

        response = f"🛒 SİPARİŞ DETAYLARI\n"
        response += "="*30 + "\n\n"
        response += f"Toplam Sipariş: {len(orders)} adet\n\n"
        response += f"{order_link}\n\n"
        response += "Siparişlerinizi görüntülemek ve yönetmek için linke tıklayın."

        return response

    except Exception as e:
        return f"Sipariş detayları oluşturulamadı: {str(e)}"


def get_order_details(whatsapp_number: str, order_number: str) -> str:
    """Belirli sipariş numarasının detaylarını getir"""
    try:
        lookup_number = _normalize_whatsapp_identifier(whatsapp_number) or (str(whatsapp_number).strip() if whatsapp_number is not None else '')
        cursor = db.connection.cursor()
        
        # Sipariş bilgilerini al
        cursor.execute("""
            SELECT id, order_number, status, total_amount, created_at
            FROM orders 
            WHERE whatsapp_number = %s AND order_number = %s
        """, [lookup_number, order_number])
        
        order = cursor.fetchone()
        if not order:
            return f"SİPARİŞ BULUNAMADI: {order_number} numaralı siparişiniz bulunamadı."
        
        order_id, order_num, status, total, created_at = order
        
        # Sipariş kalemlerini al
        cursor.execute("""
            SELECT product_code, product_name, quantity, unit_price, total_price
            FROM order_items
            WHERE order_id = %s
            ORDER BY id
        """, [order_id])
        
        items = cursor.fetchall()
        cursor.close()
        
        # Status'u Türkçe'ye çevir
        status_tr = {
            'confirmed': '[OK] Onaylandı',
            'draft': ' Taslak',
            'cancelled': '[ERROR] İptal'
        }.get(status, status)
        
        # Response oluştur
        response = f" SİPARİŞ DETAY: {order_num}\n"
        response += "="*40 + "\n\n"
        response += f" Tarih: {created_at.strftime('%d/%m/%Y %H:%M')}\n"
        response += f" Durum: {status_tr}\n"
        response += f"[PRICE] Toplam: {total:.2f} TL\n\n"
        
        response += " SİPARİŞ İÇERİĞİ:\n"
        response += "-"*40 + "\n"
        
        for i, (code, name, qty, unit_price, line_total) in enumerate(items, 1):
            response += f"{i}. {name}\n"
            response += f"   [PRODUCT] Kod: {code}\n"
            response += f"    Miktar: {qty} adet\n"
            response += f"   [PRICE] Birim: {unit_price:.2f} TL\n"
            response += f"    Toplam: {line_total:.2f} TL\n\n"
        
        return response
        
    except Exception as e:
        return f"SIPARIS DETAY HATASI: {str(e)}"


def cancel_order(whatsapp_number: str, order_number: str = "") -> str:
    """Sipariş iptal et - Single product workflow için basitleştirilmiş"""
    try:
        cursor = db.connection.cursor()
        
        if order_number:
            # Belirli sipariş numarasını iptal et
            cursor.execute("""
                SELECT id, status FROM orders 
                WHERE whatsapp_number = %s AND order_number = %s
            """, [whatsapp_number, order_number])
            
            order = cursor.fetchone()
            if not order:
                cursor.close()
                return f"SİPARİŞ BULUNAMADI: {order_number} numaralı siparişiniz bulunamadı."
            
            order_id, status = order
            
            if status == 'cancelled':
                cursor.close()
                return f"SİPARİŞ ZATEN İPTAL EDİLMİŞ: {order_number} numaralı sipariş zaten iptal edilmiş."
            
            # Siparişi iptal et
            cursor.execute("""
                UPDATE orders
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, [order_id])
            
            db.connection.commit()
            cursor.close()
            
            if status == 'confirmed':
                return f"[UYARI] SİPARİŞ İPTAL EDİLDİ: {order_number} numaralı onaylanmış siparişiniz iptal edildi. Lütfen dikkat, onaylanmış siparişlerin iptali için ek işlem gerekebilir."
            else:
                return f"[OK] SİPARİŞ İPTAL EDİLDİ: {order_number} numaralı siparişiniz başarıyla iptal edildi."
        
        else:
            # Genel iptal - sadece draft siparişleri iptal et (sepet sistemi yok)
            cursor.execute("""
                UPDATE orders 
                SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP
                WHERE whatsapp_number = %s AND status = 'draft'
            """, [whatsapp_number])
            
            cancelled_count = cursor.rowcount
            db.connection.commit()
            cursor.close()
            
            if cancelled_count > 0:
                return f"[OK] SİPARİŞ İPTAL EDİLDİ: {cancelled_count} taslak sipariş iptal edildi."
            else:
                return " İPTAL EDİLECEK SİPARİŞ YOK: Açık taslak siparişiniz bulunmuyor."
        
    except Exception as e:
        return f"İPTAL HATASI: {str(e)}"


def validate_quantity_input(user_input: str) -> tuple[bool, int | str]:
    """
    Validate quantity input with clear error messages.
    Returns (is_valid, quantity_or_error_message)
    """
    try:
        user_input = user_input.strip()
        
        # Check if empty
        if not user_input:
            return False, "[ERROR] Miktar boş olamaz. Lütfen 1-999 arası bir sayı girin."
        
        # Check if numeric
        if not user_input.isdigit():
            return False, "[ERROR] Geçersiz format. Lütfen sadece sayı girin (örn: 5)"
        
        quantity = int(user_input)
        
        # Check range
        if quantity < 1:
            return False, "[ERROR] Miktar en az 1 olmalıdır."
        elif quantity > 999:
            return False, "[ERROR] Miktar en fazla 999 olabilir."
        
        return True, quantity
        
    except ValueError:
        return False, "[ERROR] Geçersiz sayı formatı. Lütfen 1-999 arası bir sayı girin."
    except Exception as e:
        return False, f"[ERROR] Miktar doğrulama hatası: {str(e)}"


def validate_quantity_against_stock(product_code: str, requested_qty: int) -> tuple[bool, str]:
    """Enhanced stock validation for quantity control"""
    try:
        # Get product stock info
        result = db.get_stock_info(product_code)
        if not result.get('success'):
            return False, f"[ERROR] Ürün bilgisi alınamadı: {product_code}"
            
        product_name = result.get('product_name', product_code)
        available_stock = result.get('stock_quantity', 0)
        unit_price = result.get('price', 0)
        
        # Stock availability check
        if available_stock <= 0:
            return False, f"[ERROR] STOKTA YOK: {product_name}\n[PRODUCT] Kod: {product_code}\n Temin süresi: 7-10 gün"
            
        # Quantity vs stock comparison
        if requested_qty > available_stock:
            return False, f"[ERROR] YETERSİZ STOK: {product_name}\n[PRODUCT] Kod: {product_code}\n İstenen: {requested_qty} adet\n[PRODUCT] Mevcut: {available_stock} adet\n Öneri: {available_stock} adet seçebilirsiniz"
            
        # Success with stock info
        stock_status = "[OK] STOK UYGUN" if available_stock >= requested_qty * 2 else " DÜŞÜK STOK"
        line_total = unit_price * requested_qty
        
        confirmation = f"{stock_status}: {product_name}\n"
        confirmation += f"[PRODUCT] Kod: {product_code}\n"
        confirmation += f" Miktar: {requested_qty} adet\n"
        confirmation += f"[PRICE] Birim Fiyat: {unit_price:.2f} TL\n"
        confirmation += f" Ara Toplam: {line_total:.2f} TL\n"
        confirmation += f"[PRODUCT] Stokta: {available_stock} adet"
        
        return True, confirmation
        
    except Exception as e:
        return False, f"[ERROR] Stok kontrolü hatası: {str(e)}"


def prepare_multi_order_items(requested_quantities: dict[str, int]) -> tuple[dict[str, dict], list[str], float]:
    """Validate requested multi-product quantities against current stock and enrich order items."""
    validated_items: dict[str, dict] = {}
    errors: list[str] = []
    total_amount = 0.0

    for raw_code, raw_quantity in requested_quantities.items():
        code = (raw_code or '').strip().upper()
        if not code:
            errors.append("Ürün kodu eksik")
            continue

        try:
            quantity = int(raw_quantity)
        except (TypeError, ValueError):
            errors.append(f"{code}: Geçersiz miktar ({raw_quantity})")
            continue

        if quantity <= 0:
            errors.append(f"{code}: Miktar 1 veya daha büyük olmalıdır ({quantity})")
            continue

        result = db.get_stock_info(code)
        if not result.get('success'):
            errors.append(f"{code}: Ürün bulunamadı")
            continue

        product_name = result.get('product_name', code)
        price_raw = result.get('price')
        try:
            unit_price = float(price_raw)
        except (TypeError, ValueError):
            unit_price = 0.0

        stock_quantity_raw = result.get('stock_quantity')
        try:
            stock_quantity = int(stock_quantity_raw)
        except (TypeError, ValueError):
            stock_quantity = 0

        if stock_quantity <= 0:
            errors.append(f"{code}: Stokta yok")
            continue

        if quantity > stock_quantity:
            errors.append(f"{code}: Sadece {stock_quantity} adet stok var (istediniz: {quantity})")
            continue

        line_total = unit_price * quantity

        validated_items[code] = {
            'product_name': product_name,
            'quantity': quantity,
            'unit_price': unit_price,
            'total_price': line_total,
            'available_stock': stock_quantity
        }

        total_amount += line_total

    return validated_items, errors, total_amount


class ProductOrderItem(TypedDict):
    """Type definition for product order item"""
    code: str
    quantity: int


def create_multi_product_order(whatsapp_number: str, products: List[Dict[str, Any]]) -> str:
    """
    Create multi-product order directly from detected multi-product order request

    Args:
        whatsapp_number: Customer's WhatsApp number
        products: List of product order items, each containing 'code' and 'quantity'
                  Example: [{'code': 'ABC123', 'quantity': 10}, {'code': 'XYZ456', 'quantity': 5}]

    Returns:
        str: Order confirmation message or error message
    """
    try:
        print(f"[MULTI ORDER] Creating order for {whatsapp_number}: {len(products)} products")

        aggregated_requests: dict[str, int] = {}
        validation_errors: list[str] = []

        for product in products:
            raw_code = product.get('code', '') if isinstance(product, dict) else ''
            code = str(raw_code).strip().upper()
            raw_quantity = product.get('quantity', 0) if isinstance(product, dict) else 0

            if not code:
                validation_errors.append("Ürün kodu eksik")
                continue

            try:
                quantity = int(raw_quantity)
            except (TypeError, ValueError):
                validation_errors.append(f"{code}: Geçersiz miktar ({raw_quantity})")
                continue

            aggregated_requests[code] = aggregated_requests.get(code, 0) + quantity

        validated_items, item_errors, total_amount = prepare_multi_order_items(aggregated_requests)
        validation_errors.extend(item_errors)

        if validation_errors:
            unique_errors = list(dict.fromkeys(validation_errors))
            error_msg = "Sipariş oluşturulamadı:\n" + "\n".join(f"• {error}" for error in unique_errors)
            return error_msg

        if not validated_items:
            return "Geçerli ürün bulunamadı. Lütfen ürün kodlarını kontrol edin."

        order_result = save_order(whatsapp_number, validated_items, total_amount)

        if "SIPARIS KAYDEDILDI" not in order_result:
            return f"Sipariş oluşturma hatası: {order_result}"

        try:
            order_number = order_result.split(":")[1].split("(")[0].strip()
        except (IndexError, AttributeError):
            order_number = ""

        confirmation = create_order_confirmation_message(order_number or "BİLİNMİYOR", validated_items, total_amount)

        print(f"[MULTI ORDER] Order {order_number} created successfully for {whatsapp_number}")
        return confirmation

    except Exception as e:
        return f"Çoklu sipariş oluşturma hatası: {str(e)}"


def create_single_product_order(whatsapp_number: str, product_code: str, quantity: int) -> str:
    """Single product için hızlı sipariş oluşturma"""
    try:
        is_valid, qty_result = validate_quantity_input(str(quantity))
        if not is_valid:
            return qty_result

        stock_valid, stock_message = validate_quantity_against_stock(product_code, quantity)
        if not stock_valid:
            return stock_message

        result = db.get_stock_info(product_code)
        if not result.get('success'):
            return f"[ERROR] ÜRÜN BULUNAMADI: {product_code}"

        product_name = result.get('product_name', product_code)

        unit_price_raw = result.get('price')
        try:
            unit_price = float(unit_price_raw)
        except (TypeError, ValueError):
            unit_price = 0.0

        total_price = unit_price * quantity

        stock_quantity_raw = result.get('stock_quantity')
        try:
            available_stock = int(stock_quantity_raw)
        except (TypeError, ValueError):
            available_stock = 0

        order_data = {
            product_code: {
                'product_name': product_name,
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price,
                'available_stock': available_stock
            }
        }

        order_result = save_order(whatsapp_number, order_data, total_price)

        if "SIPARIS KAYDEDILDI" in order_result:
            order_number = order_result.split(":")[1].split("(")[0].strip()
            enhanced_message = create_order_confirmation_message(order_number, order_data, total_price)
            clear_selected_product_context(whatsapp_number)
            return enhanced_message
        else:
            return order_result

    except Exception as e:
        return f"TEK ÜRÜN SİPARİŞ HATASI: {str(e)}"


def process_context_quantity_input(whatsapp_number: str, user_message: str) -> str:
    """
    TASK 2.5: Main function for processing quantity input with context awareness
    Handles the complete MIKTAR_GİRİŞİ intent workflow
    """
    try:
        print(f"[TASK 2.5] Processing quantity input for {whatsapp_number}: {user_message}")
        
        # Step 1: Check if user has valid product context
        context_valid, context_info = is_quantity_context_valid(whatsapp_number)
        if not context_valid:
            return context_info
        
        print(f"[TASK 2.5] Context valid: {context_info}")
        
        # Step 2: Try to detect quantity from user input
        is_quantity, qty_result = detect_quantity_input(user_message)
        
        if not is_quantity:
            # Handle cancellation
            if qty_result == "CANCELLED":
                clear_selected_product_context(whatsapp_number)
                return "[ERROR] Sipariş iptal edildi. Ürün seçimi temizlendi.\n\n[SEARCH] Yeni ürün arayabilir veya listeden seçim yapabilirsiniz."
            
            # Return error message for invalid quantity
            return qty_result + "\n\n Lütfen sadece sayı girin (örn: 5) veya 'iptal' yazın."
        
        quantity = qty_result
        print(f"[TASK 2.5] Detected quantity: {quantity}")
        
        # Step 3: Get product context
        context = get_selected_product_context(whatsapp_number)
        product_code = context['product_code']
        product_name = context['product_name']
        unit_price = context['price']
        
        # Step 4: Create instant order
        result = create_single_product_order(whatsapp_number, product_code, quantity)
        
        print(f"[TASK 2.5] Order creation result: {result[:100]}...")
        
        return result
        
    except Exception as e:
        return f"[ERROR] MIKTAR İŞLEME HATASI: {str(e)}"


def ask_quantity_for_product(whatsapp_number: str, product_code: str) -> str:
    """Tek ürün için miktar sorusu sor"""
    try:
        # Ürün bilgilerini al
        result = db.get_stock_info(product_code)
        if not result.get('success'):
            return f"[ERROR] ÜRÜN BULUNAMADI: {product_code}"
            
        product_name = result['product_name']
        unit_price = result['price']
        available_stock = result['stock_quantity']
        
        # Stok durumu kontrolü
        if available_stock <= 0:
            return f"[ERROR] STOKTA YOK: {product_name}\n[PRODUCT] Kod: {product_code}\n Temin süresi: 7-10 gün\n\nBaşka ürün arayabilirsiniz."
        
        # Miktar sorusu
        response = f" ÜRÜN SEÇİLDİ!\n"
        response += "="*35 + "\n\n"
        response += f"[PRODUCT] Ürün: {product_name}\n"
        response += f" Kod: {product_code}\n"
        response += f"[PRICE] Birim Fiyat: {unit_price:.2f} TL\n"
        
        # Stok uyarısı
        if available_stock <= 10:
            response += f" DÜŞÜK STOK: Sadece {available_stock} adet mevcut!\n"
        else:
            response += f"[PRODUCT] Stokta: {available_stock} adet\n"
            
        response += "\n" + "-"*35 + "\n"
        response += " KAÇ ADET İSTİYORSUNUZ?\n\n"
        response += f" 1-{min(available_stock, 999)} adet arası girin\n"
        response += " Örnek: '5' veya '10'\n\n"
        response += "[ERROR] İptal için: 'iptal' yazın"
        
        return response
        
    except Exception as e:
        return f"MİKTAR SORMA HATASI: {str(e)}"


def confirm_single_product_order(whatsapp_number: str, product_code: str, quantity: int) -> str:
    """Single product siparişi için son onay"""
    try:
        # Stok ve fiyat bilgilerini tekrar kontrol et
        stock_valid, stock_message = validate_quantity_against_stock(product_code, quantity)
        if not stock_valid:
            return stock_message
            
        # Ürün bilgilerini al
        result = db.get_stock_info(product_code)
        if not result.get('success'):
            return f"[ERROR] ÜRÜN BULUNAMADI: {product_code}"
            
        product_name = result['product_name']
        unit_price = result['price']
        total_price = unit_price * quantity
        
        # Onay mesajı
        response = f"[OK] SİPARİŞ ONAY EKRANI\n"
        response += "="*35 + "\n\n"
        response += f"[PRODUCT] Ürün: {product_name}\n"
        response += f" Kod: {product_code}\n"
        response += f" Miktar: {quantity} adet\n"
        response += f"[PRICE] Birim Fiyat: {unit_price:.2f} TL\n"
        response += f" TOPLAM: {total_price:.2f} TL\n\n"
        response += "-"*35 + "\n"
        response += " SİPARİŞİ ONAYLIYOR MUSUNUZ?\n\n"
        response += "[OK] Onaylamak için: 'evet' veya 'onayla'\n"
        response += "[ERROR] İptal için: 'hayır' veya 'iptal'"
        
        return response
        
    except Exception as e:
        return f"ONAY EKRANI HATASI: {str(e)}"


def order_create_tool(customer_id: int, product_code: str, quantity: int) -> str:
    """Sipariş oluştur (Legacy - replaced by single product functions)"""
    return "Bu fonksiyon artık kullanılmıyor. Tek ürün sipariş sistemi aktif."

# ===================== HANDOFF FUNCTIONS =====================




