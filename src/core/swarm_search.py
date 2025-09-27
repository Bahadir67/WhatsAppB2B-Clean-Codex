"""Search and catalog helper tools extracted from the legacy Swarm module."""
from __future__ import annotations

import hashlib
import os
import random
import re
import time
import uuid
from typing import Any, Dict, List

from database_tools_fixed import db
from database_tools_fixed import turkish_upper

import swarm_html
from swarm_context import (
    get_current_whatsapp_number,
    register_product_session,
)
def customer_check_tool(whatsapp_number: str) -> str:
    """Müşteri bilgilerini kontrol et"""
    try:
        # Get customer data from database
        result = db.check_customer(whatsapp_number)
        
        if not result.get('success'):
            return f"❌ **HATA**\n{result.get('error', 'Bilinmeyen hata')}"
        
        response = f"🏢 **ŞİRKET BİLGİLERİNİZ**\n"
        response += "="*35 + "\n\n"
        
        if result.get('is_existing_customer'):
            # Existing customer
            company_name = result.get('company_name', 'Belirtilmemiş')
            credit_limit = result.get('credit_limit', 0.0)
            risk_score = result.get('risk_score', 50)
            customer_type = result.get('customer_type', 'PERAKENDE')
            status = result.get('status', 'ACTIVE')
            
            response += f"🏢 Şirket: {company_name}\n"
            response += f"📱 WhatsApp: {whatsapp_number}\n"
            response += f"💰 Kredi Limiti: {credit_limit:,.0f} TL\n"
            
            # Risk score with description
            if risk_score >= 80:
                risk_desc = "Mükemmel"
            elif risk_score >= 60:
                risk_desc = "İyi"
            elif risk_score >= 40:
                risk_desc = "Orta"
            else:
                risk_desc = "Düşük"
            
            response += f"⭐ Risk Puanı: {risk_score}/100 ({risk_desc})\n"
            response += f"👤 Müşteri Tipi: {customer_type}\n"
            response += f"✅ Durum: {status}\n\n"
            response += "="*35 + "\n"
            
            # Status-based advice
            if credit_limit > 10000:
                response += "🔹 Yüksek kredi limitiniz mevcuttur\n"
            elif credit_limit > 0:
                response += "🔹 Kredi limitiniz mevcuttur\n"
            else:
                response += "🔹 Kredi limiti henüz belirlenmemiş\n"
                
            if risk_score >= 70:
                response += "🔹 Risk puanınız çok iyidir\n"
            elif risk_score >= 50:
                response += "🔹 Risk puanınız iyidir\n"
            else:
                response += "🔹 Risk puanınızı iyileştirmek için düzenli ödeme yapın\n"
                
            if status.upper() == 'ACTIVE':
                response += "🔹 Hesabınız aktif durumdadır\n\n"
                response += "💡 Sipariş verebilir ve tüm hizmetlerden yararlanabilirsiniz!"
            else:
                response += "🔹 Hesabınız pasif durumdadır\n\n"
                response += "⚠️ Lütfen müşteri temsilcisiyle iletişime geçin"
                
        else:
            # New customer
            response += f"📱 WhatsApp: {whatsapp_number}\n"
            response += f"👤 Durum: Yeni Müşteri\n\n"
            response += "="*35 + "\n"
            response += "🔹 Henüz sistemimizde kayıtlı değilsiniz\n"
            response += "🔹 Kayıt olmak için müşteri temsilcisiyle görüşün\n"
            response += "🔹 Kayıt sonrası kredi limiti belirlenecektir\n\n"
            response += "📞 Kayıt için lütfen satış temsilcisiyle iletişime geçin"
        
        return response
        
    except Exception as e:
        return f"❌ **HATA**\nMüşteri kontrolü yapılamadı: {str(e)}"


def valve_search_tool(query: str) -> str:
    """Valve (valf) ürün arama - SQL valve_bul fonksiyonunu kullanır - AI ile parametre çıkarma"""
    try:
        # Global context'ten WhatsApp numarasını al
        
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
            session_id = hashlib.md5(f"{query}_{random.randint(1000,9999)}".encode()).hexdigest()[:8]
            
            # WhatsApp number'ı global context'ten al
            actual_whatsapp = get_current_whatsapp_number() or 'unknown'
            
            # HTML dosyası oluştur - PLAN'A GÖRE
            html_dir = os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')
            os.makedirs(html_dir, exist_ok=True)
            
            # Dosya adı formatı: products_{whatsapp}_{session}_{timestamp}.html
            timestamp = str(int(time.time() * 1000))
            whatsapp_clean = actual_whatsapp.replace('@c.us', '').replace('+', '')
            html_filename = f"products_{whatsapp_clean}_{session_id}_{timestamp}.html"
            html_path = f"{html_dir}/{html_filename}"
            
            # HTML içeriği oluştur (products değişkenini kullan, all_products değil)
            html_content = swarm_html.generate_product_html(products, query, html_filename)
            
            # Dosyaya yaz
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f"[HTML CREATED] {html_path}")
            
            # Stokta olan ürünleri say (products değişkenini kullan)
            in_stock_count = len([p for p in products if int(p.get('stock', 0) or 0) > 0])
            
            # Liste linki response (Tunnel URL kullan)
            tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
            response = f"💼 {count} valf - {in_stock_count} stokta\n\n"
            response += f"{tunnel_url}/products/{html_filename}\n\n"
            response += "Aradığınız ürünleri buldum: Linkten seçim yapabilirsiniz."
            
            print(f"[VALVE SEARCH] Found {count} valves, created session: {session_id}")
            return response
        else:
            return f"'{query}' icin valf bulunamadi."
        
    except Exception as e:
        return f"Valf arama hatasi: {str(e)}"


def air_preparation_search_tool(query: str) -> str:
    """Şartlandırıcı, Regülatör, Yağlayıcı arama - 4 parametreli SQL fonksiyonu kullanır"""
    
    try:
        
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
            session_payload = {
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
                'whatsapp_number': get_current_whatsapp_number() or 'unknown'
            }
            register_product_session(session_id, session_payload)
            
            # HTML dosyası oluştur
            raw_whatsapp = get_current_whatsapp_number() or 'unknown'
            whatsapp_number = raw_whatsapp.replace('@c.us', '').replace('+', '')
            timestamp = int(time.time() * 1000)
            filename = f"products_{whatsapp_number}_{session_id}_{timestamp}.html"
            
            # HTML içeriği oluştur
            # swarm_html.generate_product_html kullan (onclick versiyonu - buton yok)
            formatted_products = [
                {
                    "code": p[1],
                    "name": p[2],
                    "price": p[3],
                    "stock": p[4]
                }
                for p in products
            ]
            html_content = swarm_html.generate_product_html(formatted_products, query, filename)
            
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
            response += "Aradığınız ürünleri buldum: Linkten seçim yapabilirsiniz."
            
            return response
        else:
            return f"'{query}' için şartlandırıcı/regülatör/yağlayıcı bulunamadı."
            
    except Exception as e:
        print(f"[ERROR] air_preparation_search_tool: {e}")
        return f"Şartlandırıcı arama hatası: {str(e)}"


def product_search_tool(query: str) -> str:
    """OPTIMIZE Ürün ara - Session'a kaydet ve liste linki oluştur"""
    try:
        # Global context'ten WhatsApp numarasını al

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
                cursor = db.connection.cursor()
                
                # Session verisini hazırla
                session_data = {
                    "products": all_products,
                    "query": query,
                    "timestamp": "NOW()",
                    "algorithm": result.get('algorithm', 'Optimize')
                }
                
                # WhatsApp number'ı global context'ten al
                actual_whatsapp = get_current_whatsapp_number() or 'unknown'
                
                # HTML dosyası oluştur - PLAN'A GÖRE
                html_dir = os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')
                os.makedirs(html_dir, exist_ok=True)
                
                # Dosya adı formatı: products_{whatsapp}_{session}_{timestamp}.html
                timestamp = str(int(time.time() * 1000))
                whatsapp_clean = actual_whatsapp.replace('@c.us', '').replace('+', '')
                html_filename = f"products_{whatsapp_clean}_{session_id}_{timestamp}.html"
                html_path = f"{html_dir}/{html_filename}"
                
                # HTML içeriği oluştur
                html_content = swarm_html.generate_product_html(all_products, query, html_filename)
                
                # Dosyaya yaz
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                print(f"[HTML CREATED] {html_path}")
                
                # Stokta olan ürünleri say
                in_stock_count = len([p for p in all_products if int(p.get('stock', 0) or 0) > 0])
                
                # Liste linki response (Tunnel URL kullan)
                tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
                response = f"💼 {count} ürün - {in_stock_count} stokta\n\n"
                response += f"{tunnel_url}/products/{html_filename}\n\n"
                response += "Aradığınız ürünleri buldum: Linkten seçim yapabilirsiniz."
                
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

            stock_int = int(stock) if stock is not None else 0
            if stock_int > 0:
                return f"STOK VAR: {name} (Kod: {product_code})\nStokta: {stock} adet\nFiyat: {price:.2f} TL\nTeslimat: 1-2 gun"
            else:
                return f"STOK YOK: {name} (Kod: {product_code})\nStokta YOK\nFiyat: {price:.2f} TL\nTemin suresi: 7-10 gun"
        else:
            return f"URUN BULUNAMADI: {product_code}\nHata: {result.get('error', 'Bilinmeyen hata')}"

    except Exception as e:
        return f"STOK KONTROL HATASI: {str(e)}"


def multi_stock_check_tool(product_codes: str) -> str:
    """Çoklu ürün stok kontrolü - virgülle ayrılmış ürün kodları"""
    try:
        # Virgülle ayrılmış kodları parse et
        codes = [code.strip() for code in product_codes.split(',') if code.strip()]

        if not codes:
            return "HATA: Geçerli ürün kodu bulunamadı. Örnek: 17A0040, 17A0041, 17A0042"

        # Çok fazla ürün kontrolü (performans için)
        MAX_PRODUCTS = 10
        if len(codes) > MAX_PRODUCTS:
            return f"HATA: Çok fazla ürün sorgulandı ({len(codes)} adet). Lütfen en fazla {MAX_PRODUCTS} ürün için stok kontrolü yapın.\n\n" + \
                   f"Örnek: {', '.join(codes[:3])}... (ve diğerleri)"

        results = []
        valid_products = []

        for code in codes:
            result = db.get_stock_info(code)
            if result.get('success'):
                name = result['product_name']
                stock = result['stock_quantity']
                price = result['price']

                stock_int = int(stock) if stock is not None else 0
                status = "VAR" if stock_int > 0 else "YOK"
                stock_info = f"{stock_int} adet" if stock_int > 0 else "YOK"

                results.append(f"{code}: {name} - {status} ({stock_info}) - {price:.2f} TL")

                # Geçerli ürünleri listeye ekle (HTML fonksiyonu için gerekli format)
                valid_products.append({
                    'code': code,
                    'name': name,
                    'stock': stock,
                    'price': price
                })
            else:
                results.append(f"{code}: Ürün bulunamadı")

        # Eğer geçerli ürünler varsa HTML interface oluştur
        if valid_products:
            # HTML dosyasını kaydet
            timestamp = str(int(time.time() * 1000))
            html_filename = f"multi_order_{timestamp}.html"
            html_path = f"{os.getenv('PRODUCT_PAGES_DIR', 'C:/projects/WhatsAppB2B-Clean-Codex/product-pages')}/{html_filename}"

            # HTML oluştur
            html_content = swarm_html.generate_multi_product_order_html(valid_products, product_codes, html_filename)

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            tunnel_url = os.getenv('TUNNEL_URL', 'http://localhost:3005')
            order_link = f"{tunnel_url}/products/{html_filename}"

            response = f"📊 STOK DURUMLARI:\n"
            response += "="*30 + "\n\n"
            response += "\n".join(results)
            response += f"\n\n🛒 SİPARİŞ ARAYÜZÜ:\n{order_link}\n\n"
            response += "Ürünler için miktar girip sipariş verebilirsiniz."

            return response
        else:
            return "HATA: Hiçbir geçerli ürün bulunamadı.\n\n" + "\n".join(results)

    except Exception as e:
        return f"ÇOKLU STOK KONTROL HATASI: {str(e)}"


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





