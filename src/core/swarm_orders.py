"""Order handling helpers extracted from the legacy Swarm module."""
from __future__ import annotations

import os
import random
import time
import calendar
from datetime import datetime, timedelta
import re
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


def _normalize_timeframe_text(value: str) -> str:
    replacements = {
        "ı": "i",
        "ğ": "g",
        "ü": "u",
        "ş": "s",
        "ö": "o",
        "ç": "c",
        "â": "a",
        "î": "i",
        "û": "u",
    }
    normalized = value.lower()
    for src, dst in replacements.items():
        normalized = normalized.replace(src, dst)
    normalized = normalized.replace('-', ' ')
    normalized = re.sub(r'[^a-z0-9\s]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized)
    normalized = re.sub(r'(^|\s)on(\s+\d+\s+gun)', lambda m: m.group(1) + 'son' + m.group(2), normalized)
    normalized = re.sub(r'son(\d+)', r'son \1', normalized)
    return normalized.strip()


def _resolve_order_history_timeframe(timeframe_text: str | None):
    from datetime import datetime, timedelta
    import calendar

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

    day_match = re.search(r'son\s+(\d+)\s+gun(?:luk)?', normalized)
    if day_match:
        days = max(1, int(day_match.group(1)))
        start_range = (now - timedelta(days=days)).replace(hour=0, minute=0, second=0, microsecond=0)
        label = f"Son {days} Gün"
        return start_range, default_end, label, None

    week_match = re.search(r'son\s+(\d+)\s+hafta', normalized)
    if week_match:
        weeks = max(1, int(week_match.group(1)))
        start_range = (now - timedelta(days=weeks * 7)).replace(hour=0, minute=0, second=0, microsecond=0)
        label = f"Son {weeks} Hafta"
        return start_range, default_end, label, None

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
    return default_start, default_end, default_label, fallback_note

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






def get_order_history(whatsapp_number: str, timeframe_text: str | None = None, limit: int | None = None) -> str:
    """Müşterinin sipariş geçmişini HTML tablo olarak getir."""
    try:
        if isinstance(timeframe_text, int) and limit is None:
            limit = timeframe_text
            timeframe_text = None

        start_dt, end_dt, timeframe_label, timeframe_note = _resolve_order_history_timeframe(timeframe_text)

        cursor = db.connection.cursor()
        query = (
            "SELECT o.order_number, o.status, o.total_amount, o.created_at, "
            "COUNT(oi.id) AS item_count "
            "FROM orders o "
            "LEFT JOIN order_items oi ON o.id = oi.order_id "
            "WHERE o.whatsapp_number = %s "
            "AND o.created_at BETWEEN %s AND %s "
            "GROUP BY o.id, o.order_number, o.status, o.total_amount, o.created_at "
            "ORDER BY o.created_at DESC"
        )
        params = [whatsapp_number, start_dt, end_dt]

        if limit and limit > 0:
            query += " LIMIT %s"
            params.append(limit)

        cursor.execute(query, params)
        orders = cursor.fetchall()
        cursor.close()

        if not orders:
            message = f"{timeframe_label} için sipariş bulunamadı."
            if timeframe_note:
                message += f"\n{timeframe_note}"
            return message

        orders_data = []
        for order_num, status, total, date, item_count in orders:
            status_tr = {
                'confirmed': 'Onaylandı',
                'draft': 'Taslak',
                'cancelled': 'İptal Edildi'
            }.get(status.lower(), status)

            date_str = date.strftime('%d/%m/%Y %H:%M') if date else 'Bilinmiyor'

            orders_data.append({
                'order_number': order_num,
                'status': status,
                'status_tr': status_tr,
                'total_amount': float(total),
                'created_at': date_str,
                'item_count': item_count
            })

        timestamp = str(int(time.time() * 1000))
        whatsapp_clean = whatsapp_number.replace('@c.us', '').replace('+', '')
        html_filename = f"order_history_{whatsapp_clean}_{timestamp}.html"
        html_path = f"{os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')}/{html_filename}"

        html_content = swarm_html.generate_order_history_html(
            orders_data,
            whatsapp_number,
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
        cursor = db.connection.cursor()

        # Get all orders
        cursor.execute("""
            SELECT id, order_number, status, total_amount, created_at
            FROM orders
            WHERE whatsapp_number = %s
            ORDER BY created_at DESC
        """, [whatsapp_number])

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
        whatsapp_clean = whatsapp_number.replace('@c.us', '').replace('+', '')
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
        cursor = db.connection.cursor()
        
        # Sipariş bilgilerini al
        cursor.execute("""
            SELECT id, order_number, status, total_amount, created_at
            FROM orders 
            WHERE whatsapp_number = %s AND order_number = %s
        """, [whatsapp_number, order_number])
        
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




