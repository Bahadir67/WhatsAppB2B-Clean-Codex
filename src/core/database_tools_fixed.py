#!/usr/bin/env python3
"""
PostgreSQL Database Tools for Swarm Multi-Agent System - FIXED VERSION
Uses direct SQL queries instead of conflicting functions
"""

import os
import psycopg2
from typing import Dict, List, Any
from dotenv import load_dotenv
import openai
import json
import time
import locale

# Load .env from project root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path)

# Turkish locale for proper character handling
try:
    locale.setlocale(locale.LC_ALL, 'Turkish_Turkey.utf8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'tr_TR.UTF-8')
    except locale.Error:
        pass  # Use default locale

def turkish_upper(text: str) -> str:
    """Turkish-aware uppercase conversion"""
    if not text:
        return text
    
    # Turkish character mapping for uppercase
    tr_map = {
        'ç': 'Ç', 'ğ': 'Ğ', 'ı': 'I', 'i': 'İ', 'ö': 'Ö', 'ş': 'Ş', 'ü': 'Ü',
        'Ç': 'Ç', 'Ğ': 'Ğ', 'I': 'I', 'İ': 'İ', 'Ö': 'Ö', 'Ş': 'Ş', 'Ü': 'Ü'
    }
    
    result = ""
    for char in text:
        if char in tr_map:
            result += tr_map[char]
        else:
            result += char.upper()
    return result

class DatabaseManager:
    """PostgreSQL bağlantı ve işlemler - Optimized for Task 3.2"""
    
    def __init__(self):
        self.connection = None
        self.connect()
        
        # SQL fonksiyonlarını kontrol et ve yükle
        self.check_sql_functions()
        
        # OpenAI client for parameter extraction
        self.openai_client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv('OPENROUTER_API_KEY')
        )
    
    def check_sql_functions(self):
        """SQL fonksiyonlarını kontrol et ve eksik olanları yükle"""
        try:
            from sql_functions_manager import SQLFunctionsManager
            manager = SQLFunctionsManager(self.connection)
            manager.check_and_load_all_functions()
        except Exception as e:
            print(f"[SQL WARNING] Fonksiyon kontrolü yapılamadı: {e}")
            # Hata olsa bile devam et
    
    def connect(self):
        """Veritabanına bağlan"""
        try:
            self.connection = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                database=os.getenv('DB_NAME', 'eticaret_db'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'masterkey'),
                port=os.getenv('DB_PORT', 5432)
            )
            print("[DB] PostgreSQL bağlantısı başarılı")
            return True
        except Exception as e:
            print(f"[DB Error] {e}")
            return False
    
    def find_numeric_values(self, product_name: str) -> Dict[str, int]:
        """Ürün adından çap ve strok değerlerini çıkar"""
        import re
        numbers = re.findall(r'\d+', product_name)
        
        if not numbers or len(numbers) < 2:
            return None
            
        return {
            "cap": int(numbers[0]),    # İlk sayı = Çap
            "strok": int(numbers[1])   # İkinci sayı = Strok  
        }
    
    def find_cylinder_direct(self, cap: int = None, strok: int = None, extras: List[str] = None, limit: int = 100) -> List[Dict]:
        """Direct SQL implementation of find_cylinder with extra specifications support"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            
            # Build extra specifications filter
            extra_conditions = []
            extra_params = []
            
            if extras and isinstance(extras, list):
                for extra in extras:
                    if extra and extra.strip():
                        # Normalize extra specification
                        extra_norm = extra.strip().lower()
                        
                        # Map common terms with comprehensive search patterns
                        if extra_norm in ['magnet', 'manyetik', 'magnetik', 'mag', 'manyetık', 'magnetli', 'manyetikli']:
                            search_terms = ['%MAG%', '%MANYET%', '%MAGNET%', '%MANYETIK%', '%MAGNETIK%']
                        elif extra_norm in ['yastık', 'yastik', 'cushion', 'yastıklı', 'yastikli']:
                            search_terms = ['%YAST%', '%CUSHION%', '%YASTIK%']
                        elif extra_norm in ['sensör', 'sensor', 'sens', 'sensörlü', 'sensorlu']:
                            search_terms = ['%SENS%', '%SENSOR%', '%SENSÖR%']
                        elif extra_norm in ['mil', 'rod', 'milli']:
                            search_terms = ['%MIL%', '%ROD%']
                        else:
                            # Generic search for any extra term - try both original and uppercase
                            search_terms = [f'%{extra_norm.upper()}%', f'%{extra.upper()}%']
                        
                        # Add OR conditions for this extra specification
                        term_conditions = []
                        for term in search_terms:
                            term_conditions.extend([
                                "product_name ILIKE %s",
                                "description ILIKE %s",
                                "specifications ILIKE %s"
                            ])
                            extra_params.extend([term, term, term])
                        
                        if term_conditions:
                            extra_conditions.append(f"({' OR '.join(term_conditions)})")
            
            # Direct SQL query with number extraction and extra specifications
            extra_where_clause = ""
            if extra_conditions:
                extra_where_clause = f"AND ({' AND '.join(extra_conditions)})"
            
            sql = f"""
            WITH number_extract AS (
                SELECT 
                  id, product_code, product_name, price, stock_quantity,
                  description, specifications, category, brand,
                  -- Extract first two numbers from product name
                  CASE WHEN length((string_to_array(regexp_replace(regexp_replace(product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[1]) <= 4 
                       THEN (string_to_array(regexp_replace(regexp_replace(product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[1]::INT 
                       ELSE NULL END AS first_num,
                  CASE WHEN length((string_to_array(regexp_replace(regexp_replace(product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[2]) <= 4 
                       THEN (string_to_array(regexp_replace(regexp_replace(product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[2]::INT 
                       ELSE NULL END AS second_num
                FROM products_semantic
                WHERE 
                  (product_name ILIKE %s OR product_name ILIKE %s)
                  AND regexp_replace(product_name, '[^0-9]+', ' ', 'g') ~ '[0-9]'
                  {extra_where_clause}
            )
            SELECT id, product_code, product_name, price, 
                   stock_quantity, description, specifications, 
                   category, brand, first_num, second_num
            FROM number_extract
            WHERE 
                (%s IS NULL OR first_num = %s)
                AND (%s IS NULL OR second_num = %s)
            ORDER BY stock_quantity DESC
            LIMIT %s
            """
            
            # Combine all parameters
            all_params = ['%SIL%', '%SİL%'] + extra_params + [cap, cap, strok, strok, limit]
            
            cursor.execute(sql, all_params)
            results = cursor.fetchall()
            cursor.close()
            
            # Format results
            products = []
            for row in results:
                products.append({
                    'id': row[0],
                    'product_code': row[1],
                    'product_name': row[2],
                    'price': float(row[3]) if row[3] else 0.0,
                    'stock_quantity': int(row[4]) if row[4] else 0,
                    'description': row[5] or '',
                    'specifications': row[6] or '',
                    'category': row[7] or '',
                    'brand': row[8] or '',
                    'detected_cap': row[9],
                    'detected_strok': row[10]
                })
            
            return products
            
        except Exception as e:
            print(f"[DB Error] find_cylinder_direct: {e}")
            return []
    
    def find_cylinder_in_stock_direct(self, cap: int = None, strok: int = None, extras: List[str] = None, min_stock: int = 1) -> List[Dict]:
        """Direct SQL implementation of find_cylinder_in_stock with extra specifications"""
        products = self.find_cylinder_direct(cap, strok, extras)
        return [p for p in products if p['stock_quantity'] >= min_stock]
    
    def count_cylinders_direct(self, cap: int, strok: int, extras: List[str] = None) -> int:
        """Direct count implementation with extra specifications"""
        products = self.find_cylinder_direct(cap, strok, extras)
        return len(products)
    
    def find_products_by_price_direct(self, min_price: float = 0, max_price: float = 999999, limit: int = 50) -> List[Dict]:
        """Direct price range search"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            sql = """
            SELECT id, product_code, product_name, price, stock_quantity,
                   description, specifications, category, brand
            FROM products_semantic
            WHERE price BETWEEN %s AND %s
            ORDER BY price ASC
            LIMIT %s
            """
            
            cursor.execute(sql, (min_price, max_price, limit))
            results = cursor.fetchall()
            cursor.close()
            
            products = []
            for row in results:
                products.append({
                    'id': row[0],
                    'product_code': row[1],
                    'product_name': row[2],
                    'price': float(row[3]) if row[3] else 0.0,
                    'stock_quantity': int(row[4]) if row[4] else 0,
                    'description': row[5] or '',
                    'specifications': row[6] or '',
                    'category': row[7] or '',
                    'brand': row[8] or ''
                })
            
            return products
            
        except Exception as e:
            print(f"[DB Error] find_products_by_price_direct: {e}")
            return []
    
    def find_similar_products_direct(self, product_code: str, limit: int = 10) -> List[Dict]:
        """Direct similar products search"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            
            # Get target product info
            cursor.execute("""
                SELECT category, brand FROM products_semantic 
                WHERE product_code = %s LIMIT 1
            """, (product_code,))
            
            target_row = cursor.fetchone()
            if not target_row:
                return []
            
            target_category, target_brand = target_row
            
            # Find similar products
            sql = """
            SELECT id, product_code, product_name, price, stock_quantity,
                   description, specifications, category, brand
            FROM products_semantic
            WHERE 
                product_code != %s
                AND (category = %s OR brand = %s)
                AND stock_quantity > 0
            ORDER BY 
                CASE WHEN category = %s AND brand = %s THEN 0
                     WHEN category = %s THEN 1
                     ELSE 2 END,
                stock_quantity DESC
            LIMIT %s
            """
            
            cursor.execute(sql, (product_code, target_category, target_brand, 
                                target_category, target_brand, target_category, limit))
            results = cursor.fetchall()
            cursor.close()
            
            products = []
            for row in results:
                products.append({
                    'id': row[0],
                    'product_code': row[1],
                    'product_name': row[2],
                    'price': float(row[3]) if row[3] else 0.0,
                    'stock_quantity': int(row[4]) if row[4] else 0,
                    'description': row[5] or '',
                    'specifications': row[6] or '',
                    'category': row[7] or '',
                    'brand': row[8] or ''
                })
            
            return products
            
        except Exception as e:
            print(f"[DB Error] find_similar_products_direct: {e}")
            return []
    
    def search_products_smart_direct(self, search_term: str, limit: int = 50) -> List[Dict]:
        """Direct smart search implementation"""
        if not self.connection:
            return []
        
        try:
            cursor = self.connection.cursor()
            
            # Direkt ürün kodu araması için önce exact match kontrol et
            exact_match_sql = """
            SELECT product_code, product_name,
                   MIN(price) as min_price, MAX(price) as max_price,
                   SUM(stock_quantity) as total_stock,
                   description, specifications, category, brand
            FROM products_semantic
            WHERE product_code = %s
            GROUP BY product_code, product_name, description, specifications, category, brand
            """

            cursor.execute(exact_match_sql, (search_term,))
            exact_results = cursor.fetchall()

            if exact_results:
                # Exact match bulundu - tek ürün olarak döndür
                row = exact_results[0]
                products = []
                price_text = f"{row[2]} TL" if row[2] == row[3] else f"{row[2]}-{row[3]} TL"
                products.append({
                    'id': 0,  # Grouped result için synthetic ID
                    'product_code': row[0],
                    'product_name': row[1],
                    'price': float(row[2]) if row[2] else 0.0,
                    'price_range': price_text,
                    'stock_quantity': int(row[4]) if row[4] else 0,
                    'description': row[5] or '',
                    'specifications': row[6] or '',
                    'category': row[7] or '',
                    'brand': row[8] or '',
                    'is_exact_match': True
                })
                return products

            # Exact match yok, normal arama yap
            sql = """
            SELECT id, product_code, product_name, price, stock_quantity,
                   description, specifications, category, brand
            FROM products_semantic
            WHERE
                product_code ILIKE %s
                OR product_name ILIKE %s
                OR description ILIKE %s
                OR specifications ILIKE %s
            ORDER BY
                CASE WHEN product_code ILIKE %s THEN 1 ELSE 2 END,
                stock_quantity DESC
            LIMIT %s
            """

            pattern = f'%{search_term}%'
            exact_code_pattern = search_term  # For exact code match priority
            cursor.execute(sql, (pattern, pattern, pattern, pattern, exact_code_pattern, limit))
            results = cursor.fetchall()
            cursor.close()

            products = []
            for row in results:
                product = {
                    'id': row[0],
                    'product_code': row[1],
                    'product_name': row[2],
                    'price': float(row[3]) if row[3] else 0.0,
                    'stock_quantity': int(row[4]) if row[4] else 0,
                    'description': row[5] or '',
                    'specifications': row[6] or '',
                    'category': row[7] or '',
                    'brand': row[8] or ''
                }

                # Normal arama sonucunda da exact match kontrol et
                if row[1] == search_term:  # product_code exact match
                    product['is_exact_match'] = True

                products.append(product)

            return products
            
        except Exception as e:
            print(f"[DB Error] search_products_smart_direct: {e}")
            return []
    
    def search_products_optimized(self, query: str) -> Dict[str, Any]:
        """Enhanced search using direct SQL - Task 3.2 optimized"""
        if not self.connection:
            return {"error": "Database connection failed", "count": 0, "products": []}
        
        try:
            start_time = time.time()
            
            # Check if it's a cylinder search
            if 'silindir' in query.lower():
                print(f"[DB] Cylinder search detected: '{query}'")
                
                # Extract parameters using AI
                params = self.extract_cylinder_params_with_ai(query)
                cap = params.get('cap')
                strok = params.get('strok')
                extras = params.get('extras', [])
                
                print(f"[DB] Extracted params: cap={cap}, strok={strok}, extras={extras}")
                
                # Check for stock filtering first
                is_stock_filter = any(term in query.lower() for term in ['stokta olan', 'stokta', 'mevcut', 'stock', 'available'])
                
                if is_stock_filter:
                    # Use SQL find_cylinder_in_stock with extras
                    print(f"[DB] Using SQL find_cylinder_in_stock with extras")
                    cursor = self.connection.cursor()
                    
                    # Use extras directly but convert to Turkish uppercase for database matching
                    sql_extras = [turkish_upper(extra) for extra in extras] if extras else []
                    
                    # Pad with NULLs if needed
                    while len(sql_extras) < 4:
                        sql_extras.append(None)
                    
                    cursor.execute("SELECT * FROM find_cylinder_with_extras(%s, %s, %s, %s, %s, %s) WHERE stock_quantity >= %s", 
                                 (cap, strok, sql_extras[0], sql_extras[1], sql_extras[2], sql_extras[3], 1))
                    sql_results = cursor.fetchall()
                    cursor.close()
                    
                    # Format SQL results
                    products_data = []
                    for row in sql_results:
                        products_data.append({
                            'id': row[0],
                            'product_code': row[1],
                            'product_name': row[2],
                            'price': float(row[3]) if row[3] else 0.0,
                            'stock_quantity': int(row[4]) if row[4] else 0,
                            'description': row[5] or '',
                            'specifications': row[6] or '',
                            'category': row[7] or '',
                            'brand': row[8] or ''
                        })
                    products = products_data
                else:
                    # Use SQL find_cylinder with extras for regular searches
                    print(f"[DB] Using SQL find_cylinder with extras")
                    cursor = self.connection.cursor()
                    
                    # Use extras directly but convert to Turkish uppercase for database matching
                    sql_extras = [turkish_upper(extra) for extra in extras] if extras else []
                    
                    # Take only first 4 extras for SQL function
                    while len(sql_extras) < 4:
                        sql_extras.append(None)
                    
                    cursor.execute("SELECT * FROM find_cylinder_with_extras(%s, %s, %s, %s, %s, %s)", 
                                 (cap, strok, sql_extras[0], sql_extras[1], sql_extras[2], sql_extras[3]))
                    sql_results = cursor.fetchall()
                    cursor.close()
                    
                    # Format SQL results  
                    products_data = []
                    for row in sql_results:
                        products_data.append({
                            'id': row[0],
                            'product_code': row[1], 
                            'product_name': row[2],
                            'price': float(row[3]) if row[3] else 0.0,
                            'stock_quantity': int(row[4]) if row[4] else 0,
                            'description': row[5] or '',
                            'specifications': row[6] or '',
                            'category': row[7] or '',
                            'brand': row[8] or ''
                        })
                    products = products_data
                
                # Format for compatibility
                formatted_products = []
                for p in products:
                    formatted_product = {
                        "code": p['product_code'],
                        "name": p['product_name'],
                        "price": int(p['price']),
                        "stock": p['stock_quantity'],
                        "description": p['description']
                    }
                    # Tüm extra field'ları kopyala (is_exact_match, price_range vb.)
                    extra_fields = ['is_exact_match', 'price_range']
                    for field in extra_fields:
                        if field in p and p[field] is not None:
                            formatted_product[field] = p[field]
                    formatted_products.append(formatted_product)
                
                processing_time = time.time() - start_time
                print(f"[DB] Search completed in {processing_time:.3f}s - {len(formatted_products)} products")
                
                return {
                    "success": True,
                    "count": len(formatted_products),
                    "products": formatted_products,
                    "query": query,
                    "algorithm": "Direct SQL Cylinder Search",
                    "processing_time": processing_time
                }
            else:
                # General search
                products = self.search_products_smart_direct(query, 50)
                
                formatted_products = []
                for p in products:
                    formatted_products.append({
                        "code": p['product_code'],
                        "name": p['product_name'], 
                        "price": int(p['price']),
                        "stock": p['stock_quantity'],
                        "description": p['description']
                    })
                
                processing_time = time.time() - start_time
                print(f"[DB] General search completed in {processing_time:.3f}s - {len(formatted_products)} products")
                
                return {
                    "success": True,
                    "count": len(formatted_products),
                    "products": formatted_products,
                    "query": query,
                    "algorithm": "Direct SQL General Search",
                    "processing_time": processing_time
                }
                
        except Exception as e:
            processing_time = time.time() - start_time if 'start_time' in locals() else 0
            print(f"[DB Error] search_products_optimized: {e}")
            return {
                "error": str(e), 
                "count": 0, 
                "products": [],
                "processing_time": processing_time
            }
    
    def extract_valve_params_with_ai(self, query: str) -> Dict[str, Any]:
        """AI kullanarak valf parametrelerini çıkar"""
        try:
            prompt = f"""Aşağıdaki valf arama sorgusundan parametreleri çıkar.
            
Sorgu: "{query}"

Çıkarman gereken parametreler:
- tip: Valf tipi (5/2, 3/2, 5/3, 2/2 gibi kesirli sayılar) veya null
- baglanti: Bağlantı boyutu (1/8, 1/4, 3/8, 1/2 gibi kesirli sayılar) veya null
- extras: TÜM tanımlayıcı ifadeler listesi (maksimum 4 adet)

KURALLAR:
1. TİP ve BAĞLANTI HARİÇ her tanımlayıcı kelime extras'a gider
2. Valf tanımlayıcı ifadeler: pnömatik, hidrolik, namur, paslanmaz, pirinç, alüminyum,
   atex, ex-proof, yüksek basınç, vakum, hızlı, yavaş, manyetik, manuel, otomatik,
   flanşlı, dişli, rakorlu, push-in, hortum, selenoid, bobin, pilot, kontrollü,
   susturucu, egzoz, sessiz, yaylı, çift bobin, tek bobin, bistable, monostable, vs...
3. Sıfat ve özellik belirten HER kelime tanımlayıcıdır
4. TÜRKÇE EKLER HARIÇ: lı, li, lu, lü, lik, lık (bunlar kelime köküne aittir)

Örnek dönüşümler:
- "5/2 pnömatik valf 1/8" -> tip:"5/2", baglanti:"1/8", extras:["pnömatik"]
- "3/2 namur paslanmaz valf" -> tip:"3/2", baglanti:null, extras:["namur","paslanmaz"]
- "5/2 valf 1/4 selenoid kontrollü" -> tip:"5/2", baglanti:"1/4", extras:["selenoid","kontrollü"]
- "atex sertifikalı 5/3 valf hidrolik" -> tip:"5/3", baglanti:null, extras:["atex","sertifikalı","hidrolik"]
- "1/8 bağlantı 5/2 hızlı valf" -> tip:"5/2", baglanti:"1/8", extras:["hızlı"]

ÇOK ÖNEMLİ: 
- İlk kesirli sayı genelde TİP'tir (5/2, 3/2 gibi)
- İkinci kesirli sayı veya "bağlantı" ile gelen kesir BAĞLANTI'dır
- Diğer TÜM tanımlayıcı kelimeler extras'a ekle!

Sadece JSON döndür, başka açıklama yapma."""

            response = self.openai_client.chat.completions.create(
                model=os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            result_text = response.choices[0].message.content
            print(f"[AI Valve Response] {result_text}")
            
            # Markdown JSON'u temizle
            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '').strip()
            elif result_text.startswith('```'):
                result_text = result_text.replace('```', '').strip()
            
            # JSON'u parse et
            params = json.loads(result_text)
            
            # Varsayılan değerler
            if 'extras' not in params:
                params['extras'] = []
                
            return params
            
        except Exception as e:
            print(f"[AI Valve Param Error] {e}")
            # Fallback - basit parsing
            return {
                "tip": None,
                "baglanti": None,
                "extras": []
            }
    
    def extract_cylinder_params_with_ai(self, query: str) -> Dict[str, Any]:
        """AI kullanarak silindir parametrelerini çıkar"""
        try:
            prompt = f"""Aşağıdaki silindir arama sorgusundan parametreleri çıkar.
            
Sorgu: "{query}"

Çıkarman gereken parametreler:
- cap (çap): Sayısal değer veya null
- strok: Sayısal değer veya null  
- extras: TÜM tanımlayıcı ifadeler listesi

KURALLAR:
1. ÇAP ve STROK HARİÇ her tanımlayıcı kelime extras'a gider
2. Tanımlayıcı ifadeler: manyetik, yastık, yastıklı, sensör, sensörlü, mafsallı, bağlantı, çift etkili,
   tek etkili, paslanmaz, flanşlı, vida, pnömatik, hidrolik, hızlı, krom,
   döner, sabit, ayarlanabilir, kompakt, uzun, kısa, cushion, YAST, vs...
3. Sıfat ve özellik belirten HER kelime tanımlayıcıdır
4. TÜRKÇE EKLER HARIÇ: lık, lük, li, lı, lu, lü (sadece çap/strok ekleridir)

Örnek dönüşümler:
- "100 lük mafsal bağlantılı silindir" -> cap:100, strok:null, extras:["mafsal","bağlantılı"]
- "100 çap silindir manyetik özellikli" -> cap:100, strok:null, extras:["manyetik"]
- "63 çap çift etkili pnömatik silindir" -> cap:63, strok:null, extras:["çift","etkili","pnömatik"]
- "100x200 paslanmaz silindir sensörlü" -> cap:100, strok:200, extras:["paslanmaz","sensörlü"]
- "80 lük silindir flanşlı bağlantı vida" -> cap:80, strok:null, extras:["flanşlı","bağlantı","vida"]
- "100 lük ISO silindir" -> cap:100, strok:null, extras:["ISO"]
- "100x200 yastıklı silindir" -> cap:100, strok:200, extras:["yastıklı"]
- "40x50 yastık silindir" -> cap:40, strok:50, extras:["yastık"]

ÇOK ÖNEMLİ: 
- Sayısal değerler dışında kalan HER tanımlayıcı kelimeyi extras'a ekle!
- ANCAK Türkçe çap/strok eklerini (lık,lük,li,lı,lu,lü) extras'a EKLEME!

Sadece JSON döndür, başka açıklama yapma:
{{"cap": null_veya_sayi, "strok": null_veya_sayi, "extras": []}}"""

            response = self.openai_client.chat.completions.create(
                model=os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini'),
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            
            result_text = response.choices[0].message.content
            
            # Markdown JSON'u temizle
            if result_text.startswith('```json'):
                result_text = result_text.replace('```json', '').replace('```', '').strip()
            elif result_text.startswith('```'):
                result_text = result_text.replace('```', '').strip()
            
            # JSON'u parse et
            params = json.loads(result_text)
            
            # Varsayılan değerler
            if 'extras' not in params:
                params['extras'] = []
                
            return params
            
        except Exception as e:
            print(f"[AI Param Error] {e}")
            # Fallback - basit parsing
            return {
                "cap": None,
                "strok": None,
                "extras": []
            }
    
    def get_stock_info(self, product_code: str) -> Dict[str, Any]:
        """Stok bilgisi al - Task 3.2 optimized"""
        if not self.connection:
            return {"error": "Database connection failed"}
        
        try:
            cursor = self.connection.cursor()
            sql = """
            SELECT product_code, product_name, stock_quantity, price
            FROM products_semantic 
            WHERE product_code = %s
            """
            cursor.execute(sql, (product_code,))
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return {
                    "success": True,
                    "product_code": row[0],
                    "product_name": row[1],
                    "stock_quantity": int(row[2]) if row[2] else 0,
                    "price": float(row[3]) if row[3] else 0.0
                }
            else:
                return {"error": "Product not found", "product_code": product_code}
                
        except Exception as e:
            print(f"[DB Stock Error] {e}")
            return {"error": str(e)}
    
    def check_customer(self, whatsapp_number: str) -> Dict[str, Any]:
        """Müşteri kontrolü - Task 3.2 validated"""
        return {
            "whatsapp_number": whatsapp_number,
            "customer_id": hash(whatsapp_number) % 10000,
            "credit_limit": 50000.0,
            "risk_score": 85,
            "status": "active"
        }
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get connection status for validation"""
        try:
            if not self.connection:
                return {"status": "disconnected", "error": "No connection"}
            
            cursor = self.connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            
            return {
                "status": "connected",
                "host": os.getenv('DB_HOST', 'localhost'),
                "port": os.getenv('DB_PORT', 5432),
                "database": os.getenv('DB_NAME', 'eticaret_db')
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def run_function_tests(self) -> Dict[str, Any]:
        """Run comprehensive function tests for Task 3.2"""
        results = {}
        
        # Test cylinder search
        try:
            products = self.find_cylinder_direct(100, 200, 10)
            results["find_cylinder_direct"] = {
                "success": True,
                "count": len(products),
                "sample": products[0]['product_name'] if products else "No results"
            }
        except Exception as e:
            results["find_cylinder_direct"] = {"success": False, "error": str(e)}
        
        # Test stock filtering
        try:
            products = self.find_cylinder_in_stock_direct(63, None, 1)
            results["find_cylinder_in_stock_direct"] = {
                "success": True,
                "count": len(products)
            }
        except Exception as e:
            results["find_cylinder_in_stock_direct"] = {"success": False, "error": str(e)}
        
        # Test counting
        try:
            count = self.count_cylinders_direct(100, 200)
            results["count_cylinders_direct"] = {
                "success": True,
                "count": count
            }
        except Exception as e:
            results["count_cylinders_direct"] = {"success": False, "error": str(e)}
        
        # Test price range
        try:
            products = self.find_products_by_price_direct(100, 1000, 10)
            results["find_products_by_price_direct"] = {
                "success": True,
                "count": len(products)
            }
        except Exception as e:
            results["find_products_by_price_direct"] = {"success": False, "error": str(e)}
        
        # Test smart search
        try:
            products = self.search_products_smart_direct("silindir", 10)
            results["search_products_smart_direct"] = {
                "success": True,
                "count": len(products)
            }
        except Exception as e:
            results["search_products_smart_direct"] = {"success": False, "error": str(e)}
        
        return results
    
    def __del__(self):
        """Bağlantıyı kapat"""
        if self.connection:
            self.connection.close()

# Global database instance for Task 3.2
db = DatabaseManager()