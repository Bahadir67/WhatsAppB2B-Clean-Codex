#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI Swarm Multi-Agent B2B System
4 Agents + Handoff + Single-Product Instant Workflow
Cart System Removed - Single Product Selection Only
Task 2.4: ÜRÜN_SEÇİLDİ Intent Implementation Added
Task 2.5: MIKTAR_GİRİŞİ Intent Implementation Enhanced
"""

import os
import sys
import json
import random
import re
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
from swarm import Swarm, Agent
from flask import Flask, request, jsonify

# Fix Windows encoding issues
if sys.platform == "win32":
    import locale
    # Set encoding to handle Turkish characters and emojis
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    try:
        # Windows için UTF-8 encoding
        locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.utf8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.utf8')
        except locale.Error:
            pass  # Use default locale

# Load environment variables
try:
    from dotenv import load_dotenv
    # Load .env from project root
    import os
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    load_dotenv(env_path)
    print(f"[ENV] TUNNEL_URL: {os.getenv('TUNNEL_URL', 'Not set')}")
except ImportError:
    print(" python-dotenv not found, using system environment variables")
    pass

# Database imports
from database_tools_fixed import db

# ===================== CONFIGURATION =====================

# Global context for WhatsApp number and selected product
current_whatsapp_context = {}
selected_product_context = {}
product_list_sessions = {}  # Product list sessions for HTML generation

# OpenRouter Custom Client - Swarm ile uyumlu
import openai

# OpenRouter client oluştur (OpenAI SDK ile)
openai_client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv('OPENROUTER_API_KEY')
)

# Swarm client - Custom OpenRouter client ile
client = Swarm(client=openai_client)

OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')

print(f"[Swarm] Model: {OPENROUTER_MODEL}")

# ===================== TASK 2.4: ÜRÜN_SEÇİLDİ CONTEXT MANAGEMENT =====================

def parse_product_selection_message(message: str) -> dict:
    """
    Parse ÜRÜN_SEÇİLDİ/URUN_SECILDI message format: 'ÜRÜN_SEÇİLDİ: [code] - [name] - [price] TL'
    Returns: {'success': bool, 'product_code': str, 'product_name': str, 'price': float}
    """
    try:
        # Expected format: "ÜRÜN_SEÇİLDİ: 17A0040 - Hidrolik Silindir 100x200 - 1250.00 TL"
        # Also accept: "URUN_SECILDI: 17A0040 - Hidrolik Silindir 100x200 - 1250.00 TL"
        if not (message.startswith("ÜRÜN_SEÇİLDİ:") or message.startswith("URUN_SECILDI:")):
            return {'success': False, 'error': 'Invalid format'}
            
        # Remove prefix and strip
        if message.startswith("ÜRÜN_SEÇİLDİ:"):
            content = message.replace("ÜRÜN_SEÇİLDİ:", "").strip()
        else:
            content = message.replace("URUN_SECILDI:", "").strip()
        
        # Split by " - " to get [code, name, price_with_TL]
        parts = content.split(" - ")
        
        if len(parts) < 3:
            return {'success': False, 'error': 'Insufficient parts'}
        
        product_code = parts[0].strip()
        product_name = parts[1].strip()
        price_part = parts[2].strip()
        
        # Extract price (remove "TL" suffix)
        price_str = price_part.replace(" TL", "").replace("TL", "").strip()
        price = float(price_str)
        
        return {
            'success': True,
            'product_code': product_code,
            'product_name': product_name,
            'price': price
        }
        
    except Exception as e:
        return {'success': False, 'error': f'Parse error: {str(e)}'}

def store_selected_product_context(whatsapp_number: str, product_data: dict):
    """Store selected product in context for next step (quantity input)"""
    global selected_product_context
    selected_product_context[whatsapp_number] = {
        'product_code': product_data['product_code'],
        'product_name': product_data['product_name'],
        'price': product_data['price'],
        'timestamp': 'now',
        'step': 'product_selected'
    }
    print(f"[CONTEXT] Stored product selection for {whatsapp_number}: {product_data['product_code']}")

def get_selected_product_context(whatsapp_number: str) -> dict:
    """Get stored product context for quantity processing"""
    global selected_product_context
    return selected_product_context.get(whatsapp_number, {})

def clear_selected_product_context(whatsapp_number: str):
    """Clear product context after order completion"""
    global selected_product_context
    if whatsapp_number in selected_product_context:
        del selected_product_context[whatsapp_number]
        print(f"[CONTEXT] Cleared product context for {whatsapp_number}")

# ===================== TASK 2.4: PRODUCT CONFIRMATION TOOLS =====================

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

def detect_quantity_input(message: str) -> tuple[bool, int | str]:
    """
    TASK 2.5: Enhanced quantity input detection for MIKTAR_GİRİŞİ intent
    Handles various Turkish quantity formats with robust parsing
    Returns (is_quantity, quantity_or_error)
    """
    try:
        message = message.strip().lower()
        
        # Check for cancellation first
        cancellation_keywords = ['iptal', 'cancel', 'vazgeçtim', 'hayır', 'istemiyorum', 'çıkış']
        if any(keyword in message for keyword in cancellation_keywords):
            return False, "CANCELLED"
        
        # Method 1: Pure numeric input (most common)
        if message.isdigit():
            quantity = int(message)
            if 1 <= quantity <= 999:
                return True, quantity
            else:
                return False, f"[ERROR] Miktar 1-999 arası olmalıdır. Girilen: {quantity}"
        
        # Method 2: Turkish quantity expressions
        quantity_patterns = [
            (r'(\d+)\s*adet', 'adet'),           # "5 adet", "10adet"
            (r'(\d+)\s*tane', 'tane'),           # "3 tane", "7tane"
            (r'(\d+)\s*piece', 'piece'),         # "5 piece"
            (r'(\d+)\s*pcs', 'pcs'),             # "10 pcs"
            (r'(\d+)\s*ad', 'ad'),               # "5 ad"
        ]
        
        for pattern, unit_type in quantity_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    quantity = int(match.group(1))
                    if 1 <= quantity <= 999:
                        print(f"[QUANTITY DETECT] Found {quantity} via pattern '{unit_type}'")
                        return True, quantity
                    else:
                        return False, f"[ERROR] Miktar 1-999 arası olmalıdır. Girilen: {quantity} {unit_type}"
                except ValueError:
                    continue
        
        # Method 3: Written Turkish numbers (expanded)
        turkish_numbers = {
            'bir': 1, 'iki': 2, 'üç': 3, 'dört': 4, 'beş': 5,
            'altı': 6, 'yedi': 7, 'sekiz': 8, 'dokuz': 9, 'on': 10,
            'onbir': 11, 'oniki': 12, 'onüç': 13, 'ondört': 14, 'onbeş': 15,
            'onaltı': 16, 'onyedi': 17, 'onsekiz': 18, 'ondokuz': 19, 'yirmi': 20,
            'yirmibeş': 25, 'otuz': 30, 'elli': 50, 'yüz': 100
        }
        
        # Try to find Turkish written numbers with unit
        for turkish_word, number in turkish_numbers.items():
            patterns_with_turkish = [
                f'{turkish_word} adet',
                f'{turkish_word} tane',
                f'{turkish_word}',  # Just the number
            ]
            for pattern in patterns_with_turkish:
                if pattern in message:
                    if 1 <= number <= 999:
                        print(f"[QUANTITY DETECT] Found {number} via Turkish number '{turkish_word}'")
                        return True, number
                    else:
                        return False, f"[ERROR] Miktar 1-999 arası olmalıdır. Turkish: {turkish_word} = {number}"
        
        # Method 4: Handle ranges or complex expressions
        range_match = re.search(r'(\d+)\s*[-]\s*(\d+)', message)  # "5-10", "1015"
        if range_match:
            start, end = int(range_match.group(1)), int(range_match.group(2))
            if 1 <= start <= 999 and 1 <= end <= 999:
                # Take the start of range as quantity
                return True, start
        
        # Method 5: Handle "approximately" expressions
        approx_patterns = [
            r'yaklaşık\s*(\d+)',     # "yaklaşık 10"
            r'tahminen\s*(\d+)',     # "tahminen 5"
            r'around\s*(\d+)',       # "around 7"
            r'about\s*(\d+)',        # "about 8"
        ]
        
        for pattern in approx_patterns:
            match = re.search(pattern, message)
            if match:
                try:
                    quantity = int(match.group(1))
                    if 1 <= quantity <= 999:
                        print(f"[QUANTITY DETECT] Found approximate {quantity}")
                        return True, quantity
                except ValueError:
                    continue
        
        # If none of the patterns match, it's not a valid quantity
        return False, f"[ERROR] Geçersiz miktar formatı. Lütfen sadece sayı girin (örn: 5) veya 'iptal' yazın"
        
    except Exception as e:
        return False, f"[ERROR] Miktar analiz hatası: {str(e)}"

def generate_product_html(products, query, html_filename):
    """Generate HTML content for product list"""
    html = f"""<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ürün Listesi - {query}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }}
        .header {{ text-align: center; margin-bottom: 20px; color: #333; }}
        .product {{ border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px; background: #fff; cursor: pointer; }}
        .product:hover {{ background: #f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .product-name {{ font-weight: bold; color: #2c5aa0; margin-bottom: 5px; }}
        .product-code {{ color: #666; font-size: 0.9em; }}
        .product-price {{ color: #d9534f; font-weight: bold; margin: 5px 0; }}
        .product-stock {{ color: #5cb85c; font-size: 0.9em; }}
        .out-of-stock {{ opacity: 0.6; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>Urun Listesi</h2>
            <p>Arama: "<strong>{query}</strong>"</p>
            <p>Toplam {len(products)} ürün bulundu</p>
        </div>
        
        {"".join([f'''
            <div class="product {"out-of-stock" if p["stock"] <= 0 else ""}" onclick="selectProduct('{p["code"]}', '{p["name"]}', {p["price"]})">
                <div class="product-name">{p["name"]}</div>
                <div class="product-code">Kod: {p["code"]}</div>
                <div class="product-price">{p["price"]} TL</div>
                <div class="product-stock">Stok: {p["stock"]} adet</div>
            </div>
        ''' for p in products[:50]])}
    </div>
    
    <script>
        function selectProduct(code, name, price) {{
            // Create WhatsApp message
            var whatsappMsg = "URUN_SECILDI: " + code + " - " + name + " - " + price + " TL";
            
            // Try to send via fetch
            fetch('/select-product', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ 
                    message: whatsappMsg,
                    sessionId: '{html_filename}',
                    productCode: code,
                    productName: name,
                    productPrice: price
                }})
            }}).then(response => {{
                // Fetch success - do nothing here, let clipboard handle it
            }}).catch(error => {{
                // Fetch blocked by ad blocker - show copy dialog
                console.log('Fetch blocked, showing copy dialog');
            }});
            
            // Silent clipboard copy and show overlay popup
            navigator.clipboard.writeText(whatsappMsg).then(function() {{
                showSuccessOverlay();
            }}).catch(function(err) {{
                showSuccessOverlay();
            }});
        }}

        function showSuccessOverlay() {{
            // Create overlay background
            var overlay = document.createElement('div');
            overlay.style.position = 'fixed';
            overlay.style.top = '0';
            overlay.style.left = '0';
            overlay.style.width = '100%';
            overlay.style.height = '100%';
            overlay.style.backgroundColor = 'rgba(0,0,0,0.7)';
            overlay.style.zIndex = '10000';
            overlay.style.display = 'flex';
            overlay.style.alignItems = 'center';
            overlay.style.justifyContent = 'center';
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.3s ease';
            
            // Create popup box
            var popup = document.createElement('div');
            popup.style.backgroundColor = 'white';
            popup.style.borderRadius = '12px';
            popup.style.padding = '30px';
            popup.style.maxWidth = '350px';
            popup.style.width = '90%';
            popup.style.textAlign = 'center';
            popup.style.boxShadow = '0 10px 30px rgba(0,0,0,0.3)';
            popup.style.transform = 'scale(0.9)';
            popup.style.transition = 'transform 0.3s ease';
            
            // Create success icon
            var icon = document.createElement('div');
            icon.innerHTML = 'OK';
            icon.style.fontSize = '48px';
            icon.style.marginBottom = '15px';
            
            // Create title
            var title = document.createElement('h3');
            title.innerHTML = 'Ürün Seçildi!';
            title.style.color = '#2c5aa0';
            title.style.margin = '0 0 15px 0';
            title.style.fontSize = '22px';
            title.style.fontWeight = 'bold';
            
            // Create message
            var message = document.createElement('p');
            message.innerHTML = '👆 Back tuşuna basarak<br>WhatsApp\\'a dönebilirsiniz';
            message.style.color = '#666';
            message.style.margin = '0 0 20px 0';
            message.style.fontSize = '16px';
            message.style.lineHeight = '1.5';
            
            // Create close button
            var closeBtn = document.createElement('button');
            closeBtn.innerHTML = 'Tamam';
            closeBtn.style.backgroundColor = '#2c5aa0';
            closeBtn.style.color = 'white';
            closeBtn.style.border = 'none';
            closeBtn.style.borderRadius = '6px';
            closeBtn.style.padding = '12px 24px';
            closeBtn.style.fontSize = '16px';
            closeBtn.style.cursor = 'pointer';
            closeBtn.style.fontWeight = 'bold';
            closeBtn.style.transition = 'background-color 0.2s ease';
            
            // Hover effect for button
            closeBtn.onmouseover = function() {{ this.style.backgroundColor = '#1a4480'; }};
            closeBtn.onmouseout = function() {{ this.style.backgroundColor = '#2c5aa0'; }};
            
            // Assemble popup
            popup.appendChild(icon);
            popup.appendChild(title);
            popup.appendChild(message);
            popup.appendChild(closeBtn);
            overlay.appendChild(popup);
            
            // Add to page
            document.body.appendChild(overlay);
            
            // Animate in
            setTimeout(function() {{
                overlay.style.opacity = '1';
                popup.style.transform = 'scale(1)';
            }}, 50);
            
            // Close button functionality
            closeBtn.onclick = function() {{
                overlay.style.opacity = '0';
                popup.style.transform = 'scale(0.9)';
                setTimeout(function() {{
                    if (document.body.contains(overlay)) {{
                        document.body.removeChild(overlay);
                    }}
                }}, 300);
            }};
            
            // Close on overlay click
            overlay.onclick = function(e) {{
                if (e.target === overlay) {{
                    closeBtn.onclick();
                }}
            }};
        }}
    </script>
</body>
</html>"""
    return html

def is_quantity_context_valid(whatsapp_number: str) -> tuple[bool, str]:
    """
    TASK 2.5: Check if user has a valid product context for quantity input
    Returns (context_valid, context_info_or_error)
    """
    try:
        context = get_selected_product_context(whatsapp_number)
        
        if not context:
            return False, "[ERROR] Önce bir ürün seçmelisiniz! Ürün listesinden seçim yapın."
        
        if 'product_code' not in context:
            return False, "[ERROR] Ürün bilgisi eksik. Lütfen tekrar ürün seçimi yapın."
        
        # Context valid - return product info
        product_info = f"[OK] Context OK: {context['product_name']} ({context['product_code']}) - {context['price']:.2f} TL"
        return True, product_info
        
    except Exception as e:
        return False, f"[ERROR] Context kontrolü hatası: {str(e)}"

# ===================== TOOLS (PostgreSQL Integration) =====================

def customer_check_tool(whatsapp_number: str) -> str:
    """Müşteri bilgilerini kontrol et"""
    return f"Müşteri {whatsapp_number} - Kredi limiti: 50.000 TL, Risk skoru: 85/100, Aktif müşteri"

def valve_search_tool(query: str) -> str:
    """Valve (valf) ürün arama - SQL valve_bul fonksiyonunu kullanır - AI ile parametre çıkarma"""
    try:
        # Global context'ten WhatsApp numarasını al
        global current_whatsapp_context
        
        # AI ile parametreleri çıkar (silindir gibi)
        params = db.extract_valve_params_with_ai(query)
        valve_tip = params.get('tip')
        baglanti_boyutu = params.get('baglanti')
        extras = params.get('extras', [])
        
        print(f"[VALVE SEARCH] Query: '{query}'")
        print(f"[VALVE AI] Extracted - Tip: {valve_tip}, Bağlantı: {baglanti_boyutu}, Extras: {extras}")
        
        # PostgreSQL valve_bul fonksiyonunu çağır
        cursor = db.connection.cursor()
        
        # Extras'ı SQL için hazırla - Türkçe büyük harfe çevir (DB'de her şey büyük harf)
        from database_tools_fixed import turkish_upper
        sql_extras = [turkish_upper(extra) for extra in extras[:4]] if extras else []  # İlk 4 extra'yı al ve büyük harfe çevir
        while len(sql_extras) < 4:
            sql_extras.append(None)  # 4'e tamamla
        
        # Stok kontrolü
        is_stock_filter = any(term in query.lower() for term in ['stokta olan', 'stokta', 'mevcut'])
        
        if is_stock_filter:
            cursor.execute("SELECT * FROM valve_bul_in_stock(%s, %s, %s, %s, %s, %s)", 
                         (valve_tip, baglanti_boyutu, sql_extras[0], sql_extras[1], sql_extras[2], sql_extras[3]))
        else:
            cursor.execute("SELECT * FROM valve_bul(%s, %s, %s, %s, %s, %s)", 
                         (valve_tip, baglanti_boyutu, sql_extras[0], sql_extras[1], sql_extras[2], sql_extras[3]))
        
        results = cursor.fetchall()
        cursor.close()
        
        # Sonuçları formatla
        products = []
        for row in results:
            products.append({
                "code": row[1],
                "name": row[2],
                "price": int(row[3]) if row[3] else 0,
                "stock": int(row[4]) if row[4] else 0,
                "description": row[5] or ""
            })
        
        count = len(products)
        print(f"[VALVE SQL] Found {count} valves with valve_bul({valve_tip}, {baglanti_boyutu}, extras={sql_extras})")
        
        if count > 0:
            # Session ID oluştur
            import hashlib
            import random
            import time
            session_id = hashlib.md5(f"{query}_{random.randint(1000,9999)}".encode()).hexdigest()[:8]
            
            # WhatsApp number'ı global context'ten al
            actual_whatsapp = current_whatsapp_context.get('whatsapp_number', 'unknown')
            
            # HTML dosyası oluştur - PLAN'A GÖRE
            import os
            html_dir = os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')
            os.makedirs(html_dir, exist_ok=True)
            
            # Dosya adı formatı: products_{whatsapp}_{session}_{timestamp}.html
            timestamp = str(int(time.time() * 1000))
            whatsapp_clean = actual_whatsapp.replace('@c.us', '').replace('+', '')
            html_filename = f"products_{whatsapp_clean}_{session_id}_{timestamp}.html"
            html_path = f"{html_dir}/{html_filename}"
            
            # HTML içeriği oluştur (products değişkenini kullan, all_products değil)
            html_content = generate_product_html(products, query, html_filename)
            
            # Dosyaya yaz
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"[HTML CREATED] {html_path}")
            
            # Stokta olan ürünleri say (products değişkenini kullan)
            in_stock_count = len([p for p in products if p['stock'] > 0])
            
            # Liste linki response (Tunnel URL kullan)
            tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
            response = f"💼 {count} valf - {in_stock_count} stokta\n\n"
            response += f"{tunnel_url}/products/{html_filename}\n\n"
            response += "Ürünleri seçmek için linke tıklayın."
            
            print(f"[VALVE SEARCH] Found {count} valves, created session: {session_id}")
            return response
        else:
            return f"'{query}' icin valf bulunamadi."
        
    except Exception as e:
        return f"Valf arama hatasi: {str(e)}"


def air_preparation_search_tool(query: str) -> str:
    """Şartlandırıcı, Regülatör, Yağlayıcı arama - 4 parametreli SQL fonksiyonu kullanır"""
    import uuid
    import re
    
    try:
        global current_whatsapp_context, product_list_sessions
        
        # Query'yi Türkçe büyük harfe çevir
        query_upper = query.upper().replace('İ', 'I').replace('Ğ', 'G')
        
        # Parametreleri parse et
        unit_type = None
        connection_size = None
        keywords = None
        
        # 1. Bağlantı boyutu algılama (1/8, 1/4, 1/2, 3/8, 3/4)
        size_patterns = ['1/8', '1/4', '1/2', '3/8', '3/4', '1"']
        for size in size_patterns:
            if size in query_upper:
                connection_size = size
                # Query'den boyutu çıkar
                query_upper = query_upper.replace(size, '').strip()
                break
        
        # 2. Tip algılama (MR, FRY, MFRY, Y vb.)
        if re.search(r'\bMR\b', query_upper):
            unit_type = 'MR'
            query_upper = re.sub(r'\bMR\b', '', query_upper).strip()
        elif 'FRY' in query_upper:
            unit_type = 'FRY'
            query_upper = query_upper.replace('FRY', '').strip()
        elif 'MFRY' in query_upper or re.search(r'M\(FR\)Y', query_upper):
            unit_type = 'MFRY'
            query_upper = re.sub(r'MFRY|M\(FR\)Y', '', query_upper).strip()
        elif 'MFR' in query_upper or re.search(r'M\(FR\)', query_upper):
            unit_type = 'MFR'
            query_upper = re.sub(r'MFR|M\(FR\)', '', query_upper).strip()
        elif re.search(r'\bY\b', query_upper):
            unit_type = 'Y'
            query_upper = re.sub(r'\bY\b', '', query_upper).strip()
        
        # 3. Anahtar kelime algılama (REGÜLATÖR, YAĞLAYICI vb.)
        if 'REGULATOR' in query_upper or 'REGULATÖR' in query_upper or 'REGÜLATOR' in query_upper or 'REGÜLATÖR' in query_upper:
            keywords = 'REGÜLATÖR'
        elif 'YAGLAYICI' in query_upper or 'YAĞLAYICI' in query_upper:
            keywords = 'YAĞLAYICI'
        elif 'SARTLANDIRICI' in query_upper or 'ŞARTLANDIRICI' in query_upper:
            keywords = 'ŞARTLANDIRICI'
        elif 'FILTRE' in query_upper or 'FILTER' in query_upper:
            keywords = 'FILTRE'
        elif query_upper and not unit_type:  # Geriye kalan kelime varsa
            keywords = query_upper
        
        print(f"[AIR_SEARCH] Query: {query} -> Type: {unit_type}, Size: {connection_size}, Keywords: {keywords}")
        
        # SQL fonksiyonunu 4 parametreyle çağır
        # find_air_preparation_units(p_query, p_unit_type, p_connection_size, p_keywords)
        sql_query = """
        SELECT * FROM find_air_preparation_units(%s, %s, %s, %s)
        """
        
        cursor = db.connection.cursor()
        cursor.execute(sql_query, (query, unit_type, connection_size, keywords))
        products = cursor.fetchall()
        cursor.close()
        
        if products:
            count = len(products)
            in_stock = sum(1 for p in products if p[4] > 0)  # stock_quantity index
            
            # Session'a kaydet
            session_id = str(uuid.uuid4())[:8]
            product_list_sessions[session_id] = {
                'products': [
                    {
                        'id': p[0],
                        'code': p[1],
                        'name': p[2],
                        'price': float(p[3]) if p[3] else 0,
                        'stock': p[4],
                        'unit_type': p[5],
                        'connection_size': p[6],
                        'description': p[7]
                    }
                    for p in products[:50]  # İlk 50 ürün
                ],
                'query': query,
                'whatsapp_number': current_whatsapp_context.get('whatsapp_number', 'unknown')
            }
            
            # HTML dosyası oluştur
            whatsapp_number = current_whatsapp_context.get('whatsapp_number', 'unknown').replace('@c.us', '')
            timestamp = int(time.time() * 1000)
            filename = f"products_{whatsapp_number}_{session_id}_{timestamp}.html"
            
            # HTML içeriği oluştur
            # generate_product_html kullan (onclick versiyonu - buton yok)
            formatted_products = [
                {
                    "code": p[1],
                    "name": p[2],
                    "price": p[3],
                    "stock": p[4]
                }
                for p in products
            ]
            html_content = generate_product_html(formatted_products, query, filename)
            
            # HTML dosyasını kaydet
            product_pages_dir = os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')
            os.makedirs(product_pages_dir, exist_ok=True)
            filepath = os.path.join(product_pages_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"[HTML] Created: {filename}")
            
            # HTML listesi için URL (env'den al)
            tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
            list_url = f"{tunnel_url}/products/{filename}"
            
            response = f"💼 {count} ürün - {in_stock} stokta\n\n"
            response += f"{list_url}\n\n"
            response += "Ürünleri seçmek için linke tıklayın."
            
            return response
        else:
            return f"'{query}' için şartlandırıcı/regülatör/yağlayıcı bulunamadı."
            
    except Exception as e:
        print(f"[ERROR] air_preparation_search_tool: {e}")
        return f"Şartlandırıcı arama hatası: {str(e)}"

def product_search_tool(query: str) -> str:
    """OPTIMIZE Ürün ara - Session'a kaydet ve liste linki oluştur"""
    import uuid, re
    try:
        # Global context'ten WhatsApp numarasını al
        global current_whatsapp_context

        # Direkt ürün kodu kontrolü - örn: 13B0099, ABC123, XYZ-456 gibi
        # Pattern: 3+ karakter, harf/rakam/tire kombinasyonu, boşluk yok
        direct_code_pattern = r'^[A-Za-z0-9\-]{3,}$'
        is_direct_code = re.match(direct_code_pattern, query.strip()) and ' ' not in query.strip()

        # Optimize search kullan
        result = db.search_products_optimized(query)
        if result.get('success'):
            count = result['count']
            all_products = result['products']  # Tüm ürünleri al

            if count > 0:
                # DIREKT ÜRÜN KODU: Exact match kontrolü
                if is_direct_code and count == 1:
                    exact_product = all_products[0]
                    # is_exact_match flag'ini kontrol et
                    if exact_product.get('is_exact_match', False):
                        # Fiyat aralığı varsa onu göster
                        price_display = exact_product.get('price_range', f"{exact_product['price']} TL")
                        # Direkt satış akışına geç
                        return f"[URUN BULUNDU] TAM ESLESME!\n\nUrun: {exact_product['name']}\nFiyat: {price_display}\nKod: {exact_product['code']}\nStok: {exact_product['stock']} adet\n\nBu urunu almak ister misiniz? Siparis vermek icin Sales Expert'e yonlendiriliyorsunuz..."
                # Session ID oluştur
                session_id = str(uuid.uuid4())[:8]
                
                # PostgreSQL'a session kaydet
                from psycopg2 import sql
                cursor = db.connection.cursor()
                
                # Session verisini hazırla
                session_data = {
                    "products": all_products,
                    "query": query,
                    "timestamp": "NOW()",
                    "algorithm": result.get('algorithm', 'Optimize')
                }
                
                # WhatsApp number'ı global context'ten al
                actual_whatsapp = current_whatsapp_context.get('whatsapp_number', 'unknown')
                
                # HTML dosyası oluştur - PLAN'A GÖRE
                import os
                html_dir = os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')
                os.makedirs(html_dir, exist_ok=True)
                
                # Dosya adı formatı: products_{whatsapp}_{session}_{timestamp}.html
                timestamp = str(int(time.time() * 1000))
                whatsapp_clean = actual_whatsapp.replace('@c.us', '').replace('+', '')
                html_filename = f"products_{whatsapp_clean}_{session_id}_{timestamp}.html"
                html_path = f"{html_dir}/{html_filename}"
                
                # HTML içeriği oluştur
                html_content = generate_product_html(all_products, query, html_filename)
                
                # Dosyaya yaz
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                print(f"[HTML CREATED] {html_path}")
                
                # Stokta olan ürünleri say
                in_stock_count = len([p for p in all_products if p['stock'] > 0])
                
                # Liste linki response (Tunnel URL kullan)
                tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
                response = f"💼 {count} ürün - {in_stock_count} stokta\n\n"
                response += f"{tunnel_url}/products/{html_filename}\n\n"
                response += "Ürünleri seçmek için linke tıklayın."
                
                print(f"[PRODUCT SEARCH] Found {count} products, created session: {session_id}")
                return response
            else:
                return f"'{query}' icin urun bulunamadi."
                
        else:
            return f"'{query}' icin arama hatasi: {result.get('error', 'Bilinmeyen hata')}"
            
    except Exception as e:
        return f"Sistem hatasi: {str(e)}"

def stock_check_tool(product_code: str) -> str:
    """Stok kontrol et - PostgreSQL'dan gerçek stok bilgisi"""
    try:
        result = db.get_stock_info(product_code)
        if result.get('success'):
            name = result['product_name']
            stock = result['stock_quantity']
            price = result['price']
            
            if stock > 0:
                return f"STOK VAR: {name} (Kod: {product_code})\nStokta: {stock} adet\nFiyat: {price:.2f} TL\nTeslimat: 1-2 gun"
            else:
                return f"STOK YOK: {name} (Kod: {product_code})\nStokta YOK\nFiyat: {price:.2f} TL\nTemin suresi: 7-10 gun"
        else:
            return f"URUN BULUNAMADI: {product_code}\nHata: {result.get('error', 'Bilinmeyen hata')}"
            
    except Exception as e:
        return f"STOK KONTROL HATASI: {str(e)}"

def price_quote_tool(product_code: str, quantity: int) -> str:
    """Fiyat teklifi hesapla"""
    try:
        result = db.get_stock_info(product_code)
        if result.get('success'):
            unit_price = result['price']
            total_price = unit_price * quantity
            
            # Miktar indirimi
            discount = 0
            if quantity > 10:
                discount = 0.05  # %5 indirim
            elif quantity > 50: 
                discount = 0.10  # %10 indirim
                
            final_price = total_price * (1 - discount)
            
            response = f"FIYAT TEKLIFI: {result['product_name']}\n"
            response += f"Miktar: {quantity} adet\n"
            response += f"Birim fiyat: {unit_price:.2f} TL\n"
            response += f"Toplam: {total_price:.2f} TL\n"
            
            if discount > 0:
                response += f"Indirim: %{discount*100:.0f}\n"
                response += f"Final fiyat: {final_price:.2f} TL\n"
            
            return response
        else:
            return f"Urun bulunamadi: {product_code}"
    except Exception as e:
        return f"Fiyat hesaplama hatasi: {str(e)}"

# ===================== TASK 2.5: ENHANCED ORDER MANAGER TOOLS =====================

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
    """Enhanced order confirmation message oluştur - Single Product için"""
    try:
        from datetime import datetime
        
        # Header
        confirmation = " SİPARİŞ ONAY MESAJI \n"
        confirmation += "="*35 + "\n\n"
        
        # Order details
        confirmation += f" SİPARİŞ NO: {order_number}\n"
        confirmation += f" TARİH: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        
        # Single product order details
        confirmation += " SİPARİŞ DETAYI:\n"
        confirmation += "-" * 35 + "\n"
        
        # Single product - should only be one item
        product_code, details = next(iter(order_data.items()))
        product_name = details['product_name']
        quantity = details['quantity']
        unit_price = details['unit_price']
        line_total = details['total_price']
        
        # Get stock status for this quantity
        stock_valid, stock_info = validate_quantity_against_stock(product_code, quantity)
        stock_indicator = "[OK] Stok Uygun" if stock_valid else " Stok Sorunu"
        
        confirmation += f"[PRODUCT] Ürün: {product_name}\n"
        confirmation += f" Kod: {product_code}\n"
        confirmation += f" Miktar: {quantity} adet\n"
        confirmation += f"[PRICE] Birim Fiyat: {unit_price:.2f} TL\n"
        confirmation += f" Toplam Tutar: {line_total:.2f} TL\n"
        confirmation += f" {stock_indicator}\n\n"
        
        # Summary section  
        confirmation += "-" * 35 + "\n"
        confirmation += f" GENEL TOPLAM: {total_amount:.2f} TL\n"
        confirmation += "-" * 35 + "\n\n"
        
        # Delivery info removed per user request
        
        # Contact info removed per user request - unnecessary on WhatsApp
        
        # Footer
        confirmation += "[OK] Siparişiniz başarıyla alınmıştır!\n"
        confirmation += " Bizi tercih ettiğiniz için teşekkür ederiz.\n\n"
        confirmation += " B2B Satış Merkezi\n"
        confirmation += " Tek Ürün Hızlı Sipariş Sistemi"
        
        return confirmation
        
    except Exception as e:
        return f"SIPARIS ONAYLANDI: {order_number} - Detay mesajı oluşturulurken hata: {str(e)}"

def get_order_history(whatsapp_number: str, limit: int = 5) -> str:
    """Müşterinin sipariş geçmişini getir"""
    try:
        cursor = db.connection.cursor()
        cursor.execute("""
            SELECT o.order_number, o.status, o.total_amount, o.created_at,
                   COUNT(oi.id) as item_count
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            WHERE o.whatsapp_number = %s
            GROUP BY o.id, o.order_number, o.status, o.total_amount, o.created_at
            ORDER BY o.created_at DESC
            LIMIT %s
        """, [whatsapp_number, limit])
        
        orders = cursor.fetchall()
        cursor.close()
        
        if not orders:
            return "SIPARIS GECMISI BOS - Henüz hiç siparişiniz bulunmuyor."
        
        response = f" SON {len(orders)} SİPARİŞ GEÇMİŞİ:\n"
        response += "="*40 + "\n\n"
        
        for i, (order_num, status, total, date, item_count) in enumerate(orders, 1):
            # Status'u Türkçe'ye çevir
            status_tr = {
                'confirmed': '[OK] Onaylandı',
                'draft': ' Taslak', 
                'cancelled': '[ERROR] İptal'
            }.get(status, status)
            
            # Tarih formatı
            date_str = date.strftime('%d/%m/%Y %H:%M') if date else 'Bilinmiyor'
            
            response += f"{i}. {order_num}\n"
            response += f"    Tarih: {date_str}\n"
            response += f"    Durum: {status_tr}\n"
            response += f"    Ürün: {item_count} adet\n"
            response += f"   [PRICE] Tutar: {total:.2f} TL\n\n"
        
        response += "[SEARCH] Detay için sipariş numarası gönderebilirsiniz"
        return response
        
    except Exception as e:
        return f"SIPARIS GECMISI HATASI: {str(e)}"

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

def create_single_product_order(whatsapp_number: str, product_code: str, quantity: int) -> str:
    """Single product için hızlı sipariş oluşturma"""
    try:
        # 1. Miktar validasyonu
        is_valid, qty_result = validate_quantity_input(str(quantity))
        if not is_valid:
            return qty_result
            
        # 2. Stok validasyonu
        stock_valid, stock_message = validate_quantity_against_stock(product_code, quantity)
        if not stock_valid:
            return stock_message
            
        # 3. Ürün bilgilerini al
        result = db.get_stock_info(product_code)
        if not result.get('success'):
            return f"[ERROR] ÜRÜN BULUNAMADI: {product_code}"
            
        product_name = result['product_name']
        unit_price = result['price']
        total_price = unit_price * quantity
        
        # 4. Order data hazırla
        order_data = {
            product_code: {
                'product_name': product_name,
                'quantity': quantity,
                'unit_price': unit_price,
                'total_price': total_price
            }
        }
        
        # 5. Siparişi kaydet
        order_result = save_order(whatsapp_number, order_data, total_price)
        
        if "SIPARIS KAYDEDILDI" in order_result:
            # Order number'ı extract et
            order_number = order_result.split(":")[1].split("(")[0].strip()
            
            # Enhanced confirmation message oluştur
            enhanced_message = create_order_confirmation_message(order_number, order_data, total_price)
            
            # Clear context after successful order
            clear_selected_product_context(whatsapp_number)
            
            return enhanced_message
        else:
            return order_result
            
    except Exception as e:
        return f"TEK ÜRÜN SİPARİŞ HATASI: {str(e)}"

# ===================== TASK 2.5: CONTEXT-AWARE INSTANT ORDER FLOW =====================

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

def transfer_to_customer_manager():
    """Intent Analyzer'dan Customer Manager'a geçiş"""
    print("[HANDOFF] Intent Analyzer -> Customer Manager")
    return customer_manager

def transfer_to_product_specialist():
    """Intent Analyzer'dan Product Specialist'e gecis (Urun Arama icin)"""
    print("[HANDOFF] Intent Analyzer -> Product Specialist (Urun Arama)")
    return product_specialist

def transfer_to_sales_expert():
    """Product Specialist'ten Sales Expert'e geçiş (Ürün Seçimi için)"""
    print("[HANDOFF] Product Specialist -> Sales Expert (Satış)")
    return sales_expert

def transfer_to_order_manager():
    """Sales Expert/Product Specialist'ten Order Manager'a geçiş (Sipariş için)"""
    print("[HANDOFF] -> Order Manager (Single Product Order)")
    return order_manager

def transfer_from_product_to_order():
    """Product Specialist'ten Order Manager'a geçiş (Ürün seçildikten sonra)"""
    print("[HANDOFF] Product Specialist -> Order Manager (Single Product Selected)")
    return order_manager

def transfer_back_to_intent_analyzer():
    """Diğer agent'lardan Intent Analyzer'a geri dön"""
    print("[HANDOFF] -> Intent Analyzer (Yeni mesaj analizi)")
    return intent_analyzer

# ===================== 5 AGENT DEFINITION =====================

# 1. Intent Analyzer - TASK 2.5: Enhanced MIKTAR_GİRİŞİ intent detection
intent_analyzer = Agent(
    name="Intent Analyzer",
    model=OPENROUTER_MODEL,
    instructions="""Sen bir Niyet Analizcisisin. Müşteri mesajlarını kategorize et:

**ÖNCELIK SIRASI (Çakışma durumunda)**:
1. 🔥 MIKTAR_GİRİŞİ (En yüksek - her şeyi geçersiz kılar; saf sayılarda önce aktif miktar istemi/contexti var mı kontrol et)
2. ⚡ ÜRÜN_SEÇİLDİ (HTML tetikleyicisi - kesin kalıp)
3. 🎯 DİREKT_ÜRÜN_KODU (Regex eşleşmesi)
4. 📋 Diğer kategoriler (context'e göre)

**Kategoriler**:
- URUN_ARAMA: "100x200 silindir", "filtre ariyorum", "ürün arıyorum", "valf arıyorum", "5/2 valf", "3/2 valf", "pnömatik valf", "şartlandırıcı", "regülatör", "yağlayıcı", "FRY", "MFRY", "MFR", "MR", "Y 1/2", "hava hazırlayıcı", "13B0099", "10A0003" (DİREKT ÜRÜN KODLARI), "[ALFASAYISAL KOD] stokta var mı?", "[ÜRÜN KODU] fiyatı?", boşluksuz alfasayısal kodlar -> transfer_to_product_specialist()
- ÜRÜN_SEÇİLDİ: "ÜRÜN_SEÇİLDİ: [kod] - [isim] - [fiyat] TL" veya "URUN_SECILDI: [kod] - [isim] - [fiyat] TL" (HTML'den gelen) -> transfer_to_sales_expert()
- URUN_SECIMI: "3. ürünü seç", "bu ürünün fiyatı", "ürünü seçtim", "Kod XXX seçtim", "fiyat nedir" -> transfer_to_sales_expert()
- MIKTAR_GİRİŞİ: **TASK 2.5 - ENHANCED** Çok çeşitli miktar formatları:
   Pure sayı: "5", "10", "25" (⚠️ Sadece bir önceki asistan mesajı açıkça miktar istemişse veya aktif miktar girişi adımı/context'i varsa MIKTAR_GİRİŞİ olarak yorumla; aksi durumda bu saf sayıları potansiyel ürün kodu olabileceği için Product Specialist'e yönlendirme seçeneğini kullanabilirsin.)
   Turkish units: "5 adet", "10 tane", "3 piece", "7 pcs"
   Turkish yazılı: "beş adet", "iki tane", "on", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz", "on"
   Yaklaşık: "yaklaşık 5", "around 10", "5-6 tane"
   Range: "5-10", "beş altı tane", "3 ya da 4 adet"
   Belirsiz: "birkaç", "az", "çok", "biraz"
  -> transfer_to_order_manager()
- SIPARIS: "sipariş ver", "satın al", "siparişimi tamamla", "onaylıyorum", "siparis vermek istiyorum", "order", "satın almak istiyorum", "EVET", "evet", "tamam", "onayla" -> transfer_to_order_manager()
- SIPARIS_IPTAL: "iptal", "cancel", "vazgeçtim", "hayır", "istemiyorum" -> transfer_to_order_manager()
- SIPARIS_GECMIS: "siparişlerim", "geçmiş siparişler", "order history", "son siparişlerim", "ORD-2025-", "sipariş durumu", "sipariş detayı" -> transfer_to_sales_expert()
- TESEKKUR: "teşekkürler", "teşekkür", "sağol", "sağolun", "thanks", "thank you", "çok güzel", "harika", "mükemmel" -> transfer_to_customer_manager()
- SELAMLAMA: "merhaba", "selam", "günaydın", "iyi günler", "nasılsınız", "hello", "hi" -> transfer_to_customer_manager()
- GENEL_SORU: "teslimat süresi", "ödeme koşulları" -> transfer_to_sales_expert()
- TEKNIK_SORU: "ürün özellikleri", "uyumluluk" -> transfer_to_sales_expert()
- HESAP_SORU: "bakiye", "kredi limiti", "müşteri bilgisi" -> transfer_to_customer_manager()

**ÇAKIŞMA ÇÖZÜMÜ**: Birden fazla kategori uyarsa, yukarıdaki öncelik sırasına göre ilkini seç!

**TASK 2.5 WORKFLOW**:
- HTML listesinden "ÜRÜN_SEÇİLDİ: [kod] - [isim] - [fiyat] TL" gelirse -> transfer_to_sales_expert()
- Sales Expert ürünü onaylar, miktar sorar
- Müşteri, Sales Expert'in miktar isteğine yanıt olarak miktar girerse ("5", "10 adet", "beş tane", vb.) veya aktif miktar girişi adımı varsa -> Intent Analyzer MIKTAR_GİRİŞİ algılar -> transfer_to_order_manager(); aktif miktar isteği yoksa gelen saf sayıları ürün kodu ihtimali olarak Product Specialist'e yönlendirebilirsin
- Order Manager context-aware olarak direkt sipariş oluşturur

**KRİTİK KURALLAR**:
1. 🔥 MIKTAR_GİRİŞİ algılandığında mutlaka transfer_to_order_manager() çağır!
2. 🎯 **DİREKT ÜRÜN KODU ALGıLAMA**: Boşluksuz alfasayısal kod görürsen (13B0099, 10A0003, ABC123 gibi) -> MUTLAKA transfer_to_product_specialist() çağır! "stokta var mı", "fiyatı", "ürünü arıyorum" gibi ifadeler olmasına gerek yok.
3. ⚡ **PURE SAYI KONTROLÜ**: Sadece rakam olan mesajlar ("2", "5", "10") -> Ancak bir önceki asistan mesajı açıkça miktar istemişse veya mevcut bağlamda aktif miktar girişi adımı varsa MIKTAR_GİRİŞİ olarak algılayıp transfer_to_order_manager() çağır; bu şartlar yoksa potansiyel ürün kodu olabileceğinden Product Specialist'e yönlendirmeyi değerlendir!
4. 📋 **ÖNCELİK KONTROLÜ**: Her karar verirken öncelik sırasını kontrol et!
5. 🚫 **SADECE FONKSİYON ÇAĞIR**: Kategori analizi açıklaması YAPMA! Direkt uygun agent'a yönlendir.
6. **SESİZ TRANSFER**: Müşteriye açıklama yapma, sadece doğru agent'a transfer et!""",
    functions=[transfer_to_customer_manager, transfer_to_product_specialist, transfer_to_sales_expert, transfer_to_order_manager]
)

# 2. Customer Manager - Musteri islemleri
customer_manager = Agent(
    name="Customer Manager",
    model=OPENROUTER_MODEL,
    instructions="""Sen Customer Manager'sın. Müşteri karşılama ve genel işlemlerden sorumlusun.

**Görevlerin**:
1. **SELAMLAMA**: Merhaba, selam gibi karşılama mesajlarına sıcak karşılama yap
2. **TEŞEKKÜR**: Teşekkür mesajlarına kibarca cevap ver ve yardıma hazır olduğunu belirt
3. **MÜŞTERİ BİLGİ**: Müşteri bilgilerini kontrol et (customer_check_tool)
4. **KREDİ LİMİTİ**: Kredi limiti ve risk skoru raporla
5. **UYARILAR**: Müşteri pasifse uyar

**TÜRKÇE Yanıtlar**:
- Selamlama: "Merhaba! Size nasıl yardımcı olabilirim?"
- Teşekkür: "Rica ederim! Başka bir şey için yardıma ihtiyacınız olursa çekinmeden sorabilirsiniz."
- Genel: Profesyonel ve dostane yaklaşım

Sadece müşteri işlemleri, ürün arama yapmıyorsun!""",
    functions=[customer_check_tool, transfer_back_to_intent_analyzer]
)

# 3. Product Specialist - Urun arama ve HTML liste olustur
product_specialist = Agent(
    name="Product Specialist",
    model=OPENROUTER_MODEL,
    instructions="""You are Product Specialist. RESPOND IN TURKISH.

**ARAMA ARAÇLARI**:
- valve_search_tool: VALF aramaları için kullan (5/2 valf, 3/2 valf, 1/4 valf gibi)
- air_preparation_search_tool: Şartlandırıcı, Regülatör, Yağlayıcı aramaları için kullan (FRY, MFRY, MFR, MR, Y gibi)
- product_search_tool: Diğer tüm ürünler için kullan (silindir dahil)

**KULLANIM KURALI**:
1. Eğer mesajda "valf" kelimesi geçiyorsa -> valve_search_tool kullan
2. Eğer mesajda şu kelimelerden biri geçiyorsa -> air_preparation_search_tool kullan:
   - şartlandırıcı, sartlandırıcı
   - regülatör, regulator
   - yağlayıcı, yaglayıcı
   - filtre (FR kombinasyonları ile)
   - FRY, MFRY, MFR, MR (tek başına regülatör)
   - Y (tek başına yağlayıcı)
   - hava hazırlayıcı
3. Diğer tüm durumlarda -> product_search_tool kullan

**DIREKT ÜRÜN KODU AKIŞI**:
- Eger search tool "[URUN BULUNDU] TAM ESLESME!" mesaji donerse:
- Bu direkt ürün kodu demektir (örn: 13B0099, ABC123)
- OTOMATIK olarak transfer_to_sales_expert() fonksiyonunu çağır
- Müşteriyi direkt Sales Expert'e yönlendir
- Liste oluşturma, HTML sayfa üretme gerekmez!

**CRITICAL RESPONSE RULE**:
When a tool returns a response with a URL, you MUST return EXACTLY what the tool returns.
DO NOT add ANY text before or after.
DO NOT translate.
DO NOT explain.
DO NOT add context.
JUST COPY THE EXACT TOOL OUTPUT.

Example:
If tool returns:
💼 57 ürün - 5 stokta

http://localhost:3005/products/products_xxx.html

You MUST return EXACTLY:
💼 57 ürün - 5 stokta

http://localhost:3005/products/products_xxx.html

**NEW WORKFLOW**: When product selected from HTML list, customer goes directly to Sales Expert via ÜRÜN_SEÇİLDİ intent!""",
    functions=[product_search_tool, valve_search_tool, air_preparation_search_tool, stock_check_tool, transfer_from_product_to_order, transfer_to_sales_expert]
)

# 4. Sales Expert - TASK 2.4: Product confirmation + pricing + order history
sales_expert = Agent(
    name="Sales Expert",
    model=OPENROUTER_MODEL, 
    instructions="""Sen Sales Expert'sin. **TASK 2.4: ÜRÜN_SEÇİLDİ Intent Handling + Single-Product Workflow**

**Görevlerin**:
1. **DİREKT ÜRÜN KODU AKIŞI**: Product Specialist'ten direkt transfer edildiğinde ürün zaten seçili sayılır
2. **ÜRÜN_SEÇİLDİ İntent İşleme**: HTML'den gelen "ÜRÜN_SEÇİLDİ: [kod] - [isim] - [fiyat] TL" mesajını işle
3. **Product Confirmation**: handle_product_selection() ile ürün onayı + miktar sorusu
4. **Fiyat Teklifi**: Seçilen ürün için fiyat teklifi (price_quote_tool)
5. **Sipariş Geçmişi**: get_order_history(), get_order_details() ile geçmiş siparişler
6. **Genel Sorular**: Teslimat, ödeme koşulları hakkında bilgi

**YENİ WORKFLOW - DİREKT ÜRÜN KODU**:
- Product Specialist'ten transfer edildiğinde: Ürün bilgilerini göster + direkt miktar sor
- Kullanıcıdan teknik format (ÜRÜN_SEÇİLDİ:...) isteme!
- Miktar gelince otomatik Order Manager'a yönlendir

**ESKI WORKFLOW - HTML LİSTE**:
- "ÜRÜN_SEÇİLDİ:" ile başlayan mesaj gelirse -> handle_product_selection()
- Bu fonksiyon ürünü doğrular, context'e kaydeder, miktar sorar

**MESAJ FORMATI - KISA VE NET**:
Ürün onaylandığında şu mesajı gönder:
"Seçiminiz: [ürün adı]
Fiyat: [fiyat] TL
Kaç adet? (1-[max_stok] arası)"

**Diğer Komutlar**:
- "siparişlerim", "geçmiş siparişler" -> get_order_history()
- "ORD-2025-XXXX durumu" -> get_order_details()
- "sipariş ver", "satın al" -> transfer_to_order_manager()

**ÖNEMLİ**: 
- Ürün arama YAPMA! Sadece seçilen ürünlerle çalış
- ÜRÜN_SEÇİLDİ mesajları için handle_product_selection() kullan
- Miktar sorulduktan sonra müşteri rakam girerse Intent Analyzer MIKTAR_GİRİŞİ algılayıp Order Manager'a gönderir
- Türkçe konuş ve net talimatlar ver!""",
    functions=[handle_product_selection, price_quote_tool, get_order_history, get_order_details, transfer_to_order_manager, transfer_back_to_intent_analyzer]
)

# 5. Order Manager - TASK 2.5: Enhanced context-aware quantity processing and instant ordering
order_manager = Agent(
    name="Order Manager",
    model=OPENROUTER_MODEL,
    instructions="""Sen Order Manager'sın. **TASK 2.5: ENHANCED Context-Aware Quantity Processing & Instant Ordering**

**YENİ TASK 2.5 WORKFLOW**:
1. **Context + Quantity Processing**: process_context_quantity_input() ile gelişmiş miktar işleme
2. **Enhanced Quantity Detection**: Çok çeşitli format desteği ("5", "5 adet", "beş tane", "yaklaşık 10")
3. **Instant Order Creation**: Context + quantity ile direkt sipariş oluştur
4. **Smart Error Handling**: Stok kontrolü, format validation, context management

**ANA FONKSİYON**:
- **process_context_quantity_input()**: Ana miktar işleme fonksiyonu
   Context kontrolü
   Gelişmiş miktar algılama 
   Stok validasyonu
   Direkt sipariş oluşturma
   Error handling

**IŞLEM AKIŞI**:
1. Mesaj geldiğinde önce process_context_quantity_input() çalıştır
2. Bu fonksiyon her şeyi handle eder:
   - Context var mı? -> is_quantity_context_valid()
   - Miktar geçerli mi? -> detect_quantity_input()  
   - Stok uygun mu? -> validate_quantity_against_stock()
   - Sipariş oluştur -> create_single_product_order()
   - Context temizle -> clear_selected_product_context()

**TASK 2.5 ÖZELLİKLERİ**:
- [OK] Çoklu format desteği ("5", "5 adet", "beş adet", "yaklaşık 5")
- [OK] Context-aware processing
- [OK] Smart stock validation
- [OK] Instant order creation
- [OK] Automatic context cleanup
- [OK] Turkish quantity expressions
- [OK] Error handling for all edge cases

**KRITIK**:
- İlk önce process_context_quantity_input() çalıştır!
- Bu fonksiyon başarılı sipariş sonrası transfer_back_to_intent_analyzer()
- Hata durumlarında kullanıcıya net bilgi ver
- Türkçe konuş ve detaylı feedback ver""",
    functions=[process_context_quantity_input, get_selected_product_context, detect_quantity_input, create_single_product_order, ask_quantity_for_product, confirm_single_product_order, cancel_order, clear_selected_product_context, transfer_back_to_intent_analyzer]
)

# ===================== SWARM SYSTEM =====================

class SwarmB2BSystem:
    """OpenAI Swarm Single-Product B2B System with Conversation Memory"""

    def __init__(self):
        self.client = client

        # Conversation Memory System - Store last 5 messages per user, 30-minute timeout, FIFO
        self.conversation_memory = {}  # {whatsapp_number: {"messages": [...], "last_activity": datetime, "timeout_minutes": 30}}
        self.memory_settings = {
            "max_messages": 5,  # Store last 5 messages (FIFO)
            "timeout_minutes": 30,  # 30-minute timeout
            "cleanup_on_message": True,  # Cleanup expired conversations after each message
            "extract_context": True  # Auto-extract search context from messages
        }

        # Auto-extracted context for better continuity
        self.extracted_context = {}  # {whatsapp_number: {"product_type": str, "dimensions": str, "features": []}}


        print("[Swarm] Single-Product B2B System initialized")
        print("Agents: Intent Analyzer -> Customer/Product/Sales/Order")
        print("Workflow: Single-Product Instant Ordering (Cart Removed)")
        print("TASK 2.4: ÜRÜN_SEÇİLDİ intent handling enabled")
        print("TASK 2.5: Enhanced MIKTAR_GİRİŞİ intent implemented")
        print(f"[Memory] Conversation memory enabled: {self.memory_settings['max_messages']} messages, {self.memory_settings['timeout_minutes']}min timeout, FIFO cleanup")

    def cleanup_expired_conversations(self):
        """Cleanup expired conversations based on timeout_minutes"""
        if not self.memory_settings['cleanup_on_message']:
            return

        current_time = datetime.now()
        timeout_delta = timedelta(minutes=self.memory_settings['timeout_minutes'])
        expired_numbers = []

        for whatsapp_number, memory_data in self.conversation_memory.items():
            last_activity = memory_data.get('last_activity')
            if last_activity and (current_time - last_activity) > timeout_delta:
                expired_numbers.append(whatsapp_number)

        # Remove expired conversations
        for number in expired_numbers:
            del self.conversation_memory[number]
            print(f"[Memory] Expired conversation cleanup: {number}")

        if expired_numbers:
            print(f"[Memory] Cleaned up {len(expired_numbers)} expired conversations")

    def extract_search_context(self, message: str, whatsapp_number: str):
        """Auto-extract and accumulate search context from messages"""
        if whatsapp_number not in self.extracted_context:
            self.extracted_context[whatsapp_number] = {
                "product_type": None,
                "dimensions": None,
                "features": [],
                "last_search": None
            }

        context = self.extracted_context[whatsapp_number]
        message_lower = message.lower()

        # Extract product type
        product_types = ["silindir", "valf", "filtre", "regülatör", "şartlandırıcı", "yağlayıcı"]
        for ptype in product_types:
            if ptype in message_lower:
                context["product_type"] = ptype
                context["last_search"] = message
                print(f"[Context] Extracted product type: {ptype}")

        # Extract dimensions (e.g., 100x200, 50x100)
        import re
        dimension_match = re.search(r'(\d+)\s*[xX]\s*(\d+)', message)
        if dimension_match:
            context["dimensions"] = dimension_match.group(0)
            print(f"[Context] Extracted dimensions: {context['dimensions']}")

        # Extract features
        feature_keywords = ["yastıklı", "manyetik", "çift etkili", "tek etkili", "5/2", "3/2", "paslanmaz"]
        for feature in feature_keywords:
            if feature in message_lower and feature not in context["features"]:
                context["features"].append(feature)
                print(f"[Context] Added feature: {feature}")

    def add_message_to_memory(self, whatsapp_number: str, role: str, content: str):
        """Add message to conversation memory with FIFO management and context extraction"""
        current_time = datetime.now()

        # Initialize conversation memory if not exists
        if whatsapp_number not in self.conversation_memory:
            self.conversation_memory[whatsapp_number] = {
                "messages": [],
                "last_activity": current_time
            }

        memory_data = self.conversation_memory[whatsapp_number]
        messages = memory_data["messages"]

        # Auto-extract context from user messages
        if role == "user" and self.memory_settings.get("extract_context", False):
            self.extract_search_context(content, whatsapp_number)

        # Add new message
        new_message = {
            "role": role,
            "content": content,
            "timestamp": current_time.isoformat()
        }
        messages.append(new_message)

        # FIFO: Keep only last max_messages
        max_messages = self.memory_settings['max_messages']
        if len(messages) > max_messages:
            messages[:] = messages[-max_messages:]  # Keep last N messages

        # Update last activity
        memory_data["last_activity"] = current_time

        print(f"[Memory] Added {role} message for {whatsapp_number}, total: {len(messages)}/{max_messages}")

    def get_conversation_history(self, whatsapp_number: str) -> List[Dict[str, str]]:
        """Get conversation history for Swarm client (format: [{"role": str, "content": str}])"""
        if whatsapp_number not in self.conversation_memory:
            return []

        messages = self.conversation_memory[whatsapp_number]["messages"]
        # Convert to Swarm format (remove timestamp)
        swarm_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]

        print(f"[Memory] Retrieved {len(swarm_messages)} messages for {whatsapp_number}")
        return swarm_messages

    def get_memory_status(self, whatsapp_number: str = None) -> Dict[str, Any]:
        """Get memory status for debugging"""
        if whatsapp_number:
            if whatsapp_number in self.conversation_memory:
                memory_data = self.conversation_memory[whatsapp_number]
                return {
                    "user": whatsapp_number,
                    "message_count": len(memory_data["messages"]),
                    "last_activity": memory_data["last_activity"].isoformat(),
                    "age_minutes": (datetime.now() - memory_data["last_activity"]).total_seconds() / 60
                }
            else:
                return {"user": whatsapp_number, "status": "no_memory"}
        else:
            return {
                "total_conversations": len(self.conversation_memory),
                "settings": self.memory_settings,
                "users": list(self.conversation_memory.keys())
            }
    
    def process_message(self, customer_message: str, whatsapp_number: str) -> str:
        """Ana mesaj işleme fonksiyonu - Conversation Memory enabled"""

        # Cleanup expired conversations first
        self.cleanup_expired_conversations()

        # Global context'e WhatsApp numarasını kaydet
        global current_whatsapp_context
        current_whatsapp_context['whatsapp_number'] = whatsapp_number

        print(f"[Swarm] Processing: {customer_message[:50]}... from {whatsapp_number}")

        # Add user message to conversation memory
        self.add_message_to_memory(whatsapp_number, "user", customer_message)

        # Get conversation history for context
        conversation_history = self.get_conversation_history(whatsapp_number)

        # TASK 2.4: ÜRÜN_SEÇİLDİ/URUN_SECILDI mesaj detection
        if customer_message.startswith("ÜRÜN_SEÇİLDİ:") or customer_message.startswith("URUN_SECILDI:"):
            print(f"[TASK 2.4] ÜRÜN_SEÇİLDİ/URUN_SECILDI intent detected: {customer_message[:100]}")

        # TASK 2.5: MIKTAR_GİRİŞİ pre-detection for logging
        is_quantity_input, _ = detect_quantity_input(customer_message)
        if is_quantity_input:
            print(f"[TASK 2.5] MIKTAR_GİRİŞİ intent potential: {customer_message[:100]}")

        # If we have conversation history, use it; otherwise start fresh
        if conversation_history:
            # Add current message to the history
            messages_for_swarm = conversation_history + [{"role": "user", "content": f"Customer: {whatsapp_number}\nMessage: {customer_message}"}]
            print(f"[Memory] Using conversation history: {len(conversation_history)} previous messages")
        else:
            # Fresh conversation
            messages_for_swarm = [{"role": "user", "content": f"Customer: {whatsapp_number}\nMessage: {customer_message}"}]
            print(f"[Memory] Fresh conversation started for {whatsapp_number}")

        # Swarm'ı çalıştır - Intent Analyzer ile başla
        try:
            # Get extracted context if available
            extracted_ctx = self.extracted_context.get(whatsapp_number, {})

            response = self.client.run(
                agent=intent_analyzer,
                messages=messages_for_swarm,
                context_variables={
                    "whatsapp_number": whatsapp_number,
                    "extracted_context": extracted_ctx  # Pass accumulated context
                },
                debug=True  # Debug açık - handoff'ları görmek için
            )
            
            # Debug: Tüm mesajları göster
            print(f"[DEBUG] Total messages: {len(response.messages)}")
            for i, msg in enumerate(response.messages[-5:]):  # Son 5 mesaj
                print(f"[DEBUG] Message {i}: role={msg.get('role', 'unknown')}, content={str(msg.get('content', ''))[:200]}")
            
            # Assistant response'unu bul ve memory'ye ekle
            final_message = None
            for msg in reversed(response.messages):
                content = str(msg.get("content", ""))
                # Sadece assistant role'ündeki mesajları kontrol et (tool responses ignore)
                if msg.get("role") == "assistant" and content and content not in ["Product Specialist", "Customer Manager", "Sales Expert", "Intent Analyzer", "Order Manager"]:
                    final_message = content
                    break
            
            # Hiçbir şey bulamazsan son mesajı al
            if not final_message:
                final_message = response.messages[-1]["content"]

            # Add assistant response to conversation memory
            self.add_message_to_memory(whatsapp_number, "assistant", final_message)

            print(f"[Swarm] Final response: {final_message[:100]}...")
            print(f"[Memory] Conversation updated for {whatsapp_number}")

            return final_message
            
        except Exception as e:
            print(f"[Swarm Error] {e}")
            error_msg = f"Sistem hatası: {str(e)}"
            # Add error to memory too
            self.add_message_to_memory(whatsapp_number, "assistant", error_msg)
            return error_msg

# ===================== HTTP SERVER =====================

app = Flask(__name__)
system_instance = None

@app.route('/process-message', methods=['POST'])
def process_whatsapp_message():
    """WhatsApp mesajlarını işleyen endpoint - TASK 2.5 compatible"""
    global system_instance
    
    try:
        # JSON data al
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400
        
        message = data.get('message', '')
        whatsapp_number = data.get('whatsapp_number', '')
        
        if not message or not whatsapp_number:
            return jsonify({"error": "message and whatsapp_number required"}), 400
        
        print(f"[HTTP] Processing: {message[:50]}... from {whatsapp_number}")
        
        # System instance oluştur (ilk çağrıda)
        if system_instance is None:
            print("[HTTP] Initializing Swarm Single-Product system with TASK 2.5...")
            system_instance = SwarmB2BSystem()
        
        # Swarm sistemini çalıştır
        result = system_instance.process_message(message, whatsapp_number)
        
        return jsonify({
            "success": True,
            "response": str(result),
            "agent_count": 5,
            "message": message[:100],
            "whatsapp_number": whatsapp_number,
            "framework": "OpenAI Swarm Single-Product",
            "workflow": "Cart-Free Instant Ordering",
            "task_2_4": "ÜRÜN_SEÇİLDİ intent enabled",
            "task_2_5": "Enhanced MIKTAR_GİRİŞİ intent implemented"
        })
        
    except Exception as e:
        print(f"[HTTP Error] {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "OK",
        "agents": 5,
        "system": "OpenAI Swarm Single-Product B2B",
        "framework": "Swarm",
        "workflow": "Single-Product Instant Ordering",
        "task_2_4": "ÜRÜN_SEÇİLDİ intent handling",
        "task_2_5": "Enhanced MIKTAR_GİRİŞİ intent processing",
        "conversation_memory": "enabled"
    })

@app.route('/memory-status', methods=['GET'])
def memory_status():
    """Get conversation memory status for debugging"""
    global system_instance

    if system_instance is None:
        return jsonify({"error": "System not initialized"}), 400

    # Get whatsapp_number from query params if provided
    whatsapp_number = request.args.get('whatsapp_number')

    try:
        status = system_instance.get_memory_status(whatsapp_number)
        return jsonify({
            "success": True,
            "memory_status": status
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/clear-memory', methods=['POST'])
def clear_memory():
    """Clear conversation memory for specific user or all users"""
    global system_instance

    if system_instance is None:
        return jsonify({"error": "System not initialized"}), 400

    try:
        data = request.json or {}
        whatsapp_number = data.get('whatsapp_number')

        if whatsapp_number:
            # Clear specific user
            if whatsapp_number in system_instance.conversation_memory:
                del system_instance.conversation_memory[whatsapp_number]
                return jsonify({
                    "success": True,
                    "message": f"Memory cleared for {whatsapp_number}"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": f"No memory found for {whatsapp_number}"
                })
        else:
            # Clear all memory
            count = len(system_instance.conversation_memory)
            system_instance.conversation_memory.clear()
            return jsonify({
                "success": True,
                "message": f"All memory cleared ({count} conversations)"
            })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

# ===================== TEST & SERVER START =====================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test mode
        print("="*60)
        print("OpenAI Swarm Single-Product B2B System - TEST MODE")
        print("5 Agents: Intent -> Customer/Product/Sales/Order") 
        print("Workflow: Single-Product Instant Ordering")
        print("TASK 2.4: ÜRÜN_SEÇİLDİ intent testing")
        print("TASK 2.5: Enhanced MIKTAR_GİRİŞİ intent testing")
        print("="*60)
        
        # Test initialization
        system = SwarmB2BSystem()
        
        # Test TASK 2.4: ÜRÜN_SEÇİLDİ intent
        print("\n--- TASK 2.4 TEST ---")
        test_message_1 = "ÜRÜN_SEÇİLDİ: 17A0040 - Hidrolik Silindir 100x200 - 1250.00 TL"
        result_1 = system.process_message(test_message_1, "905306897885")
        print("TASK 2.4 SONUCU:")
        print(result_1)
        
        # Test TASK 2.5: MIKTAR_GİRİŞİ intent (various formats)
        print("\n--- TASK 2.5 TEST ---")
        test_quantities = ["5", "10 adet", "beş tane", "yaklaşık 7", "cancel"]
        
        for qty_input in test_quantities:
            print(f"\n> Testing quantity: '{qty_input}'")
            result = system.process_message(qty_input, "905306897885")
            print(f"MIKTAR TEST SONUCU ({qty_input}): {result[:200]}...")
        
        print("="*60)
        
    else:
        # HTTP Server mode
        print("="*60)
        print("OpenAI Swarm Single-Product B2B HTTP Server")
        print("5 Agents: Intent -> Customer/Product/Sales/Order")
        print("Workflow: Single-Product Instant Ordering (Cart Removed)")
        print("TASK 2.4: ÜRÜN_SEÇİLDİ intent implementation")
        print("TASK 2.5: Enhanced MIKTAR_GİRİŞİ intent implementation")
        print("Port: 3007 (Swarm)")
        print("Endpoints:")
        print("  POST /process-message - WhatsApp mesaj işleme")
        print("  GET  /health - System health check")
        print("="*60)
        
        # Flask server başlat
        app.run(
            host="0.0.0.0",
            port=3007,  # CrewAI'dan farklı port
            debug=True,
            threaded=True
        )