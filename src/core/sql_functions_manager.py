"""
SQL Functions Manager - Veritabanı fonksiyonlarını kontrol ve yükle
Program başladığında eksik fonksiyonları otomatik yükler
"""

import os
import psycopg2
from typing import List, Dict

class SQLFunctionsManager:
    """SQL fonksiyonlarını yönet"""
    
    # Kritik fonksiyonlar ve hangi SQL dosyasında bulundukları
    REQUIRED_FUNCTIONS = {
        'find_cylinder': 'cylinder_functions.sql',
        'find_cylinder_in_stock': 'cylinder_functions.sql',
        'find_cylinder_with_extras': 'cylinder_functions.sql',
        'valve_bul': 'valve_functions.sql',
        'valve_bul_in_stock': 'valve_functions.sql',
        'search_products_semantic': 'search_functions.sql',
        'search_products_smart': 'search_functions.sql',
        'find_air_preparation_units': 'sartlandirici_search_fixed.sql',
        'find_fry': 'sartlandirici_search_fixed.sql',
        'find_mr': 'sartlandirici_search_fixed.sql',
        'find_y': 'sartlandirici_search_fixed.sql',
        'cancel_order': 'order_cancellation_schema.sql',
        'get_cancellable_orders': 'order_cancellation_schema.sql',
    }
    
    def __init__(self, connection):
        self.connection = connection
        self.sql_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            'sql'
        )
    
    def check_function_exists(self, function_name: str) -> bool:
        """Fonksiyonun veritabanında var olup olmadığını kontrol et"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc 
                    WHERE proname = %s
                    AND pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                );
            """, (function_name,))
            exists = cursor.fetchone()[0]
            cursor.close()
            return exists
        except Exception as e:
            print(f"[SQL CHECK ERROR] {function_name}: {e}")
            return False
    
    def load_sql_file(self, filename: str) -> bool:
        """SQL dosyasını yükle"""
        filepath = os.path.join(self.sql_dir, filename)
        
        if not os.path.exists(filepath):
            print(f"[SQL WARNING] Dosya bulunamadı: {filepath}")
            return False
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            cursor = self.connection.cursor()
            cursor.execute(sql_content)
            self.connection.commit()
            cursor.close()
            print(f"[SQL] {filename} başarıyla yüklendi")
            return True
            
        except Exception as e:
            print(f"[SQL ERROR] {filename} yüklenirken hata: {e}")
            try:
                self.connection.rollback()
            except:
                pass
            return False
    
    def check_and_load_all_functions(self) -> Dict[str, bool]:
        """Tüm gerekli fonksiyonları kontrol et ve eksik olanları yükle"""
        print("[SQL] Veritabanı fonksiyonları kontrol ediliyor...")
        
        results = {}
        missing_functions = []
        loaded_files = set()
        
        # Her fonksiyonu kontrol et
        for func_name, sql_file in self.REQUIRED_FUNCTIONS.items():
            if self.check_function_exists(func_name):
                results[func_name] = True
                print(f"[SQL] OK {func_name} mevcut")
            else:
                results[func_name] = False
                missing_functions.append((func_name, sql_file))
                print(f"[SQL] X {func_name} EKSIK!")
        
        # Eksik fonksiyonları yükle
        if missing_functions:
            print(f"[SQL] {len(missing_functions)} eksik fonksiyon bulundu, yükleniyor...")
            
            # Her SQL dosyasını sadece bir kez yükle
            for func_name, sql_file in missing_functions:
                if sql_file not in loaded_files:
                    if self.load_sql_file(sql_file):
                        loaded_files.add(sql_file)
                        # Bu dosyadaki fonksiyonları tekrar kontrol et
                        for check_func, check_file in self.REQUIRED_FUNCTIONS.items():
                            if check_file == sql_file:
                                if self.check_function_exists(check_func):
                                    results[check_func] = True
                                    print(f"[SQL] OK {check_func} yuklendi")
        
        # Özet
        success_count = sum(1 for v in results.values() if v)
        total_count = len(results)
        
        if success_count == total_count:
            print(f"[SQL] TÜM FONKSİYONLAR HAZIR ({success_count}/{total_count})")
        else:
            print(f"[SQL] UYARI: Bazı fonksiyonlar eksik ({success_count}/{total_count})")
        
        return results
    
    def get_all_functions(self) -> List[str]:
        """Veritabanındaki tüm fonksiyonları listele"""
        try:
            cursor = self.connection.cursor()
            cursor.execute("""
                SELECT proname 
                FROM pg_proc 
                WHERE pronamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'public')
                ORDER BY proname;
            """)
            functions = [row[0] for row in cursor.fetchall()]
            cursor.close()
            return functions
        except Exception as e:
            print(f"[SQL ERROR] Fonksiyon listesi alınamadı: {e}")
            return []

# Kullanım örneği
if __name__ == "__main__":
    # Test bağlantısı
    import os
    from dotenv import load_dotenv
    
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    load_dotenv(env_path)
    
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        database=os.getenv('DB_NAME', 'eticaret_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'masterkey'),
        port=os.getenv('DB_PORT', 5432)
    )
    
    manager = SQLFunctionsManager(conn)
    
    # Tüm fonksiyonları kontrol et ve yükle
    results = manager.check_and_load_all_functions()
    
    # Mevcut fonksiyonları listele
    print("\n[SQL] Veritabanındaki tüm fonksiyonlar:")
    functions = manager.get_all_functions()
    for func in functions:
        print(f"  - {func}")
    
    conn.close()