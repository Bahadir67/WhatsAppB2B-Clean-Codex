"""Shared context helpers for the Swarm B2B runtime."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


current_whatsapp_context: Dict[str, Any] = {}
selected_product_context: Dict[str, Dict[str, Any]] = {}
product_list_sessions: Dict[str, Dict[str, Any]] = {}


def set_current_whatsapp_number(whatsapp_number: str | None) -> None:
    """Persist the active WhatsApp number for downstream tools."""
    if whatsapp_number:
        current_whatsapp_context['whatsapp_number'] = whatsapp_number
    else:
        current_whatsapp_context.pop('whatsapp_number', None)


def get_current_whatsapp_number() -> str | None:
    """Return the active WhatsApp number if one has been stored."""
    return current_whatsapp_context.get('whatsapp_number')


def register_product_session(session_id: str, data: Dict[str, Any]) -> None:
    """Attach catalog data to an HTML session identifier."""
    product_list_sessions[session_id] = data


def get_product_session(session_id: str) -> Dict[str, Any] | None:
    """Look up previously stored catalog session details."""
    return product_list_sessions.get(session_id)


def remove_product_session(session_id: str) -> None:
    """Remove a catalog session when it expires."""
    product_list_sessions.pop(session_id, None)


def parse_product_selection_message(message: str) -> Dict[str, Any]:
    """Parse the 'ÜRÜN_SEÇİLDİ' notification emitted by the HTML catalog."""
    try:
        if not (message.startswith("ÜRÜN_SEÇİLDİ:") or message.startswith("URUN_SECILDI:")):
            return {'success': False, 'error': 'Invalid format'}

        if message.startswith("ÜRÜN_SEÇİLDİ:"):
            content = message.replace("ÜRÜN_SEÇİLDİ:", "").strip()
        else:
            content = message.replace("URUN_SECILDI:", "").strip()

        parts = content.split(" - ")
        if len(parts) < 3:
            return {'success': False, 'error': 'Insufficient parts'}

        product_code = parts[0].strip()
        product_name = parts[1].strip()
        price_part = parts[2].strip()

        price_str = price_part.replace(" TL", "").replace("TL", "").strip()
        price = float(price_str)

        return {
            'success': True,
            'product_code': product_code,
            'product_name': product_name,
            'price': price
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {'success': False, 'error': f'Parse error: {exc}'}


def store_selected_product_context(whatsapp_number: str, product_data: Dict[str, Any]) -> None:
    """Persist the product context until quantity has been provided."""
    selected_product_context[whatsapp_number] = {
        'product_code': product_data['product_code'],
        'product_name': product_data['product_name'],
        'price': product_data['price'],
        'timestamp': 'now',
        'step': 'product_selected'
    }
    print(f"[CONTEXT] Stored product selection for {whatsapp_number}: {product_data['product_code']}")


def get_selected_product_context(whatsapp_number: str) -> Dict[str, Any]:
    """Read the stored product selection for a user."""
    return selected_product_context.get(whatsapp_number, {})


def clear_selected_product_context(whatsapp_number: str) -> None:
    """Remove the stored product context after the flow completes."""
    if whatsapp_number in selected_product_context:
        del selected_product_context[whatsapp_number]
        print(f"[CONTEXT] Cleared product context for {whatsapp_number}")


def detect_multi_product_order(message: str) -> Tuple[bool, Dict[str, Any]]:
    """Detect multi-product order requests expressed in free text."""
    try:
        message = message.strip().lower()
        print(f"[DEBUG] Processing message: '{message}'")

        pattern1 = r'([A-Z0-9,\s]+?)\s+ten\s+(\d+)\s+(?:er|şer|çar|er)\s+adet'
        match1 = re.search(pattern1, message, re.IGNORECASE)
        if match1:
            codes_str = match1.group(1).strip().upper()
            quantity = int(match1.group(2))
            codes = [code.strip() for code in codes_str.split(',') if code.strip()]
            if len(codes) > 1 and len(codes) <= 10:
                products = [{'code': code, 'quantity': quantity} for code in codes]
                print(f"[MULTI ORDER DETECT] Pattern 1: {len(codes)} products, {quantity} each")
                return True, {'products': products}

        pattern2 = r'([A-Z0-9,\s]+?)\s+ten\s+(\d+)\s+adet'
        match2 = re.search(pattern2, message, re.IGNORECASE)
        if match2:
            codes_str = match2.group(1).strip().upper()
            quantity = int(match2.group(2))
            codes = [code.strip() for code in codes_str.split(',') if code.strip()]
            if len(codes) > 1 and len(codes) <= 10:
                products = [{'code': code, 'quantity': quantity} for code in codes]
                print(f"[MULTI ORDER DETECT] Pattern 2: {len(codes)} products, {quantity} each")
                return True, {'products': products}

        pattern3 = r'([A-Z0-9]+)\s+(\d+)\s+adet'
        matches3 = re.findall(pattern3, message, re.IGNORECASE)
        if len(matches3) > 1 and len(matches3) <= 10:
            products = [{'code': code.upper(), 'quantity': int(qty)} for code, qty in matches3]
            print(f"[MULTI ORDER DETECT] Pattern 3: {len(products)} individual products")
            return True, {'products': products}

        print('[DEBUG] No pattern matched')
        return False, {}
    except Exception as exc:  # pragma: no cover - defensive
        print(f"[MULTI ORDER DETECT ERROR] {exc}")
        return False, {}


def detect_quantity_input(message: str) -> Tuple[bool, int | str]:
    """Detect whether a message contains a valid quantity expression."""
    try:
        message = message.strip().lower()

        cancellation_keywords = ['iptal', 'cancel', 'vazgeçtim', 'hayır', 'istemiyorum', 'çıkış']
        if any(keyword in message for keyword in cancellation_keywords):
            return False, 'CANCELLED'

        if message.isdigit():
            quantity = int(message)
            if 1 <= quantity <= 999:
                return True, quantity
            return False, f"[ERROR] Miktar 1-999 arası olmalıdır. Girilen: {quantity}"

        quantity_patterns = [
            (r'(\d+)\s*adet', 'adet'),
            (r'(\d+)\s*tane', 'tane'),
            (r'(\d+)\s*piece', 'piece'),
            (r'(\d+)\s*pcs', 'pcs'),
            (r'(\d+)\s*ad', 'ad'),
        ]

        for pattern, unit_type in quantity_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    quantity = int(match.group(1))
                except ValueError:
                    continue
                if 1 <= quantity <= 999:
                    print(f"[QUANTITY DETECT] Found {quantity} via pattern '{unit_type}'")
                    return True, quantity
                return False, f"[ERROR] Miktar 1-999 arası olmalıdır. Girilen: {quantity} {unit_type}"

        turkish_numbers = {
            'bir': 1, 'iki': 2, 'üç': 3, 'dört': 4, 'beş': 5,
            'altı': 6, 'yedi': 7, 'sekiz': 8, 'dokuz': 9, 'on': 10,
            'onbir': 11, 'oniki': 12, 'onüç': 13, 'ondört': 14, 'onbeş': 15,
            'onaltı': 16, 'onyedi': 17, 'onsekiz': 18, 'ondokuz': 19, 'yirmi': 20,
            'yirmibeş': 25, 'otuz': 30, 'elli': 50, 'yüz': 100
        }

        for turkish_word, number in turkish_numbers.items():
            patterns_with_turkish = [
                f'{turkish_word} adet',
                f'{turkish_word} tane',
                f'{turkish_word}',
            ]
            if any(pattern in message for pattern in patterns_with_turkish):
                if 1 <= number <= 999:
                    print(f"[QUANTITY DETECT] Found {number} via Turkish number '{turkish_word}'")
                    return True, number
                return False, f"[ERROR] Miktar 1-999 arası olmalıdır. Turkish: {turkish_word} = {number}"

        range_match = re.search(r'(\d+)\s*[-]\s*(\d+)', message)
        if range_match:
            start, _ = int(range_match.group(1)), int(range_match.group(2))
            if 1 <= start <= 999:
                return True, start

        approx_patterns = [
            r'yaklaşık\s*(\d+)',
            r'tahminen\s*(\d+)',
            r'around\s*(\d+)',
            r'about\s*(\d+)',
        ]

        for pattern in approx_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    quantity = int(match.group(1))
                except ValueError:
                    continue
                if 1 <= quantity <= 999:
                    print(f"[QUANTITY DETECT] Found approximate {quantity}")
                    return True, quantity

        return False, "[ERROR] Geçersiz miktar formatı. Lütfen sadece sayı girin (örn: 5) veya 'iptal' yazın"
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"[ERROR] Miktar analiz hatası: {exc}"


def is_quantity_context_valid(whatsapp_number: str) -> Tuple[bool, str]:
    """Verify that we have a product context before processing quantity input."""
    try:
        context = get_selected_product_context(whatsapp_number)
        if not context:
            return False, "[ERROR] Önce bir ürün seçmelisiniz! Ürün listesinden seçim yapın."
        if 'product_code' not in context:
            return False, "[ERROR] Ürün bilgisi eksik. Lütfen tekrar ürün seçimi yapın."

        product_info = f"[OK] Context OK: {context['product_name']} ({context['product_code']}) - {context['price']:.2f} TL"
        return True, product_info
    except Exception as exc:  # pragma: no cover - defensive
        return False, f"[ERROR] Context kontrolü hatası: {exc}"
