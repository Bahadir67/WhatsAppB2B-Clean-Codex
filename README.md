# WhatsApp B2B AI Satış Asistanı - OpenAI Swarm Edition

## 🚀 Proje Özeti
OpenAI Swarm Multi-Agent sistemi ile WhatsApp üzerinden B2B ürün sorgulama, sipariş yönetimi ve satış desteği sağlayan akıllı asistan.

## 🔄 Hızlı Kurulum (Clone & Run)

```bash
# 1. Projeyi klonla
git clone https://github.com/Bahadir67/B2B_Agent.git
cd B2B_Agent

# 2. Python sanal ortam oluştur (önerilen)
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Python bağımlılıkları yükle
pip install -r requirements.txt

# 4. Node.js bağımlılıkları yükle
npm install

# 5. Environment dosyasını ayarla
copy .env.example .env
# .env dosyasını düzenle (API keys, DB credentials)

# 6. PostgreSQL veritabanını hazırla
psql -U postgres -c "CREATE DATABASE eticaret_db;"
# SQL migration'ları çalıştır:
psql -U postgres -d eticaret_db -f migrations/001_create_order_tables.sql
psql -U postgres -d eticaret_db -f migrations/002_remove_cart_system.sql
psql -U postgres -d eticaret_db -f migrations/003_valve_bul_extras.sql

# 7. Servisleri başlat
start_services.bat  # Windows
# bash start_services.sh  # Linux/Mac (yakında)
```

## 🏗️ Sistem Mimarisi

```
WhatsApp → WhatsApp Bot → OpenAI Swarm System → PostgreSQL → Response
             (3001)           (3007)
                                ↓
                    5-Agent Multi-Agent Processing
                    ┌─────────────────────────────────┐
                    │ Intent Analyzer                 │
                    │ Product Specialist              │
                    │ Sales Expert                    │
                    │ Order Manager                   │
                    │ Technical Support               │
                    └─────────────────────────────────┘
```

## ✨ Özellikler

### 1. OpenAI Swarm Multi-Agent Sistemi
- **Intent Analyzer Agent**: Müşteri mesajlarını kategorilendirme ve yönlendirme
- **Product Specialist Agent**: Akıllı ürün arama, filtreleme ve listeleme
- **Sales Expert Agent**: Satış desteği, sipariş geçmişi ve müşteri hizmetleri
- **Order Manager Agent**: Sipariş yönetimi, sepet işlemleri ve onay süreçleri
- **Technical Support Agent**: Teknik sorular ve ürün detayları

### 2. Akıllı Ürün Arama
- Çap/Strok/Uzunluk parametreleri ile filtreleme
- Ekstra parametreler (manyetik, yastık, hidrolik, ISO)
- Duplicate kayıt yönetimi
- PostgreSQL veritabanı entegrasyonu
- Intent-based akıllı arama

### 3. Web Tabanlı Ürün Listesi
- Modern responsive tasarım
- Tıklanabilir ürün kartları
- Arama ve filtreleme
- Session bazlı saklama
- Otomatik Cloudflare tunnel linki

### 4. Gelişmiş Sipariş Sistemi
- Ürün seçimi algılama
- Sepet yönetimi (ekleme/çıkarma/güncelleme)
- Miktar ve stok kontrolü
- Otomatik toplam hesaplama
- Sipariş onay ve kaydetme
- Sipariş geçmişi sorgulama

## 🛠️ Kurulum

### Gereksinimler
- Python 3.8+
- Node.js 18+
- PostgreSQL
- OpenAI API anahtarı

### Adımlar

1. **Python bağımlılıklarını yükleyin:**
```bash
pip install openai-swarm flask psycopg2-binary python-dotenv
```

2. **Node.js bağımlılıklarını yükleyin:**
```bash
npm install
```

3. **Environment değişkenlerini ayarlayın:**
```bash
cp .env.example .env
# .env dosyasını düzenleyin
```

4. **Veritabanını hazırlayın:**
```sql
CREATE DATABASE eticaret_db;
-- SQL schema'yı import edin (products_semantic, orders, order_items tabloları)
```

5. **Servisleri başlatın:**
```bash
# Terminal 1 - OpenAI Swarm System
python swarm_b2b_system.py

# Terminal 2 - WhatsApp Bot
node whatsapp-webhook-sender.js

# Terminal 3 (isteğe bağlı) - Cloudflare Tunnel
./cloudflared.exe tunnel --url http://localhost:3007
```

## 📱 Kullanım

### WhatsApp Komutları

#### Sistem Durumu
```
/status  - Sistem durumu ve aktif agent bilgisi
```

#### Ürün Arama (Otomatik Agent Routing)
```
"100 çap 200 strok silindir var mı?"
"hidrolkik silindir"
"ISO 32x160 pnömatik silindir"
```

#### Sipariş İşlemleri
```
"sipariş vermek istiyorum"
"sepetimi göster"
"sipariş geçmişim"
"siparişimi iptal et"
```

#### Müşteri Hizmetleri
```
"yardım"
"teknik destek"
"fiyat bilgisi"
```

## 🔧 Konfigürasyon

### Environment Değişkenleri (.env)
```env
# OpenAI API
OPENAI_API_KEY=your_openai_key_here

# WhatsApp
WHATSAPP_PHONE=905306897885

# Server Ports
ORCHESTRATOR_PORT=3000
REPLY_SERVER_PORT=3001
CUSTOMER_AGENT_PORT=3003
SWARM_SERVER_PORT=3007

# CloudFlare Tunnel
TUNNEL_URL=https://your-tunnel-url.trycloudflare.com

# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=eticaret_db
DB_USER=postgres
DB_PASSWORD=your_password
```

### Portlar
- `3001`: WhatsApp Reply Server
- `3007`: OpenAI Swarm Multi-Agent System
- `5678`: n8n (isteğe bağlı, kullanılmıyor)

## 📊 Multi-Agent İş Akışı

1. **Mesaj Alımı**: WhatsApp → WhatsApp Bot
2. **Intent Analizi**: Swarm Intent Analyzer mesajı kategorilendirme
3. **Agent Routing**: Uygun uzman agent'a yönlendirme
4. **İşlem**: Specialized agent görevini yerine getirme
5. **Database**: PostgreSQL'dan veri çekme/yazma
6. **Yanıt**: Akıllı yanıt oluşturma ve gönderme

### Agent Handoff Akışı
- **Ürün Arama**: Intent Analyzer → Product Specialist
- **Sipariş Verme**: Product Specialist → Order Manager
- **Teknik Sorular**: Intent Analyzer → Technical Support
- **Satış Desteği**: Herhangi bir agent → Sales Expert

## 🗄️ Veritabanı Şeması

```sql
-- Ürünler tablosu
CREATE TABLE products_semantic (
    id SERIAL PRIMARY KEY,
    product_code TEXT,
    product_name TEXT,
    price NUMERIC,
    stock_quantity INTEGER,
    description TEXT,
    specifications TEXT,
    category TEXT,
    brand TEXT
);

-- Siparişler tablosu
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_number TEXT UNIQUE,
    whatsapp_number TEXT,
    total_amount NUMERIC,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sipariş kalemleri
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products_semantic(id),
    quantity INTEGER,
    unit_price NUMERIC,
    total_price NUMERIC
);

-- Geçici sepet oturumları
CREATE TABLE temp_product_sessions (
    session_id TEXT,
    whatsapp_number TEXT,
    product_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 📁 Proje Yapısı

```
Asistan/
├── swarm_b2b_system.py          # Ana OpenAI Swarm Multi-Agent system
├── whatsapp-webhook-sender.js   # WhatsApp entegrasyonu
├── product_search_tools.py      # Ürün arama ve veritabanı araçları
├── database_utils.py            # Veritabanı yardımcı fonksiyonları
├── .env                         # Konfigürasyon
├── package.json                 # Node.js bağımlılıkları
├── requirements.txt             # Python bağımlılıkları
└── README.md                    # Bu dosya
```

## 🚀 Sistem Avantajları

- ✅ OpenAI Swarm Multi-Agent mimarisi
- ✅ Intent-based akıllı routing
- ✅ Gelişmiş sipariş yönetimi
- ✅ PostgreSQL entegrasyonu
- ✅ Web tabanlı ürün listesi
- ✅ Session ve context yönetimi
- ✅ Otomatik agent handoff
- ✅ Sipariş geçmişi ve iptal
- ✅ Stok kontrolü ve doğrulama

## 🔄 Sistem Durumu

### ✅ Aktif Sistemler
- OpenAI Swarm Multi-Agent System (Port 3007)
- WhatsApp Bot Integration (Port 3001)
- PostgreSQL Veritabanı

### ❌ Kaldırılan Sistemler
- ~~CrewAI Server (Port 3002)~~ - Swarm ile değiştirildi
- ~~n8n Workflow Engine~~ - Artık kullanılmıyor

## 📝 Lisans

MIT

## 👥 Katkıda Bulunanlar

- Proje Sahibi

## 📞 İletişim

WhatsApp: +90 530 689 78 85

---

🤖 Generated with [Claude Code](https://claude.ai/code)

Co-Authored-By: Claude <noreply@anthropic.com>