# WhatsApp B2B AI Satış Asistanı (OpenAI Swarm)

Modern B2B satış süreçleri için WhatsApp üzerinden çalışan çok ajanlı (multi-agent) bir AI asistanı. Ürün arama, stok kontrolü, sipariş oluşturma ve sipariş geçmişi gibi işlemleri, OpenRouter üzerindeki OpenAI Swarm runtime’ı ve PostgreSQL veritabanını kullanarak uçtan uca yönetir.

---

## 🧩 Bileşen Özeti

```
[Müşteri]
   │ WhatsApp
   ▼
[whatsapp-webhook-sender.js]  ── typing indicator, mesaj köprüsü
   │ HTTP (3001)                
   ▼
[swarm_api.py / SwarmB2BSystem] ── OpenRouter (Swarm) çağrıları (3007)
   │
   ├─ swarm_agents.py            →  Intent Analyzer, Product Specialist, Sales Expert,
   │                                Order Manager, Customer Manager
   ├─ swarm_orders.py            →  Sipariş geçmişi + LLM destekli zaman aralığı çözümü
   ├─ swarm_search.py            →  Ürün arama & stok araçları
   ├─ swarm_html.py              →  HTML katalog & sipariş sayfaları
   └─ PostgreSQL                 →  orders, order_items, products_semantic, vb.
```

---

## 👥 Ajanlar

| Ajan | Rolü | Ana Fonksiyonlar |
|------|------|------------------|
| **Intent Analyzer** | İlk mesaj analizi, niyet tespiti | Handoff kararları, MIKTAR
giriş koruması |
| **Product Specialist** | Ürün arama & listeleme | `product_search_tool`, stok kontrol, HTML ürün listesi |
| **Sales Expert** | Seçilen ürün doğrulama, sipariş geçmişi | `get_order_history`, JSON handoff, fiyat/teknik yönlendirme |
| **Order Manager** | Tek ürün sipariş akışı | `process_context_quantity_input`, stok kontrol, sipariş kaydı |
| **Customer Manager** | Selamlama / teşekkür / müşteri status | `customer_check_tool`, kredi limiti bilgiler |

Swarm runtime, ajanlar arası geçişleri `swarm_agents.py` içerisindeki handoff yardımcılarıyla yönetir.

---

## 🧠 Öne Çıkan Özellikler

- **LLM Destekli Zaman Aralığı Çözümü:** `_llm_resolve_order_history_timeframe()` Türkçe doğal dil ifadelerini (örn. “geçen cuma”, “temmuz başı”) ISO tarih aralıklarına çevirir; güven düşükse deterministik fallback devreye girer.
- **Otomatik WhatsApp Kimlik Normalizasyonu:** `get_order_history`, `get_all_orders_for_customer`, `get_order_details` fonksiyonları `+90…`, `905…` veya `@c.us` formatlarını otomatik normalize eder.
- **Typing Indicator:** `whatsapp-webhook-sender.js` gelen mesajı işlediği süre boyunca typing durumunu otomatik gönderir, kullanıcı beklerken üç nokta animasyonu görür.
- **HTML Sipariş/Katalog Sayfaları:** `swarm_html.py` ile oluşturulan sayfalar Cloudflare tüneli üzerinden dışarı açılır.
- **Gelişmiş Miktar Algılama:** Task 2.5 geliştirmesi ile Türkçe sayı yazımları, aralıklar, “birkaç” gibi muğlak ifadeler işlem akışına entegre edilir.

---

## 🔧 Kurulum ve Çalıştırma

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/Bahadir67/B2B_Agent.git
cd B2B_Agent
```

### 2. Python Ortamı
```bash
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 3. Node.js Bağımlılıkları
```bash
npm install
```

### 4. Ortam Değişkenleri
```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```
`.env` içindeki ana değişkenler:

| Değişken | Açıklama |
|----------|----------|
| `OPENROUTER_API_KEY` | OpenRouter API anahtarınız |
| `OPENROUTER_MODEL`   | Varsayılan Swarm modeli (`openai/gpt-4.1-mini`) |
| `POSTGRES_*`         | PostgreSQL bağlantı bilgileri |
| `WHATSAPP_NUMBER`    | Katalog tüneli ve bağlantılar için kullanılır |
| `TUNNEL_URL`         | `product-pages/` klasörünün harici adresi |
| `WHATSAPP_TYPING_INTERVAL_MS` | Typing göstergesi yenileme süresi (opsiyonel) |

### 5. Veritabanı
```bash
psql -U postgres -c "CREATE DATABASE eticaret_db;"
psql -U postgres -d eticaret_db -f migrations/001_create_order_tables.sql
psql -U postgres -d eticaret_db -f migrations/002_remove_cart_system.sql
psql -U postgres -d eticaret_db -f migrations/003_valve_bul_extras.sql
```

### 6. Servisleri Başlat
```bash
start_services.bat            # Windows tüm servisleri açar
# python src/core/swarm_b2b_system.py   # Sadece Swarm runtime
# node src/core/whatsapp-webhook-sender.js
# node src/core/product-list-server-v2.js
```

---

## 🗂️ Önemli Modüller

- `swarm_b2b_system.py` – CLI giriş noktası, Swarm runtime başlatma
- `swarm_runtime.py` – Konuşma hafızası, Swarm çağrıları, JSON override desteği
- `swarm_agents.py` – Ajan talimatları ve handoff fonksiyonları
- `swarm_orders.py` – Sipariş akışı, LLM zaman aralığı analizi, HTML geçmiş üretimi
- `swarm_search.py` – Ürün arama & stok kontrol araçları (valf, şartlandırıcı, vb.)
- `swarm_html.py` – HTML sipariş/katalog üreticileri
- `swarm_api.py` – Flask HTTP yüzeyi (`/process-message`, ürün seçim webhook’u)
- `whatsapp-webhook-sender.js` – WhatsApp-API köprüsü, typing indicator
- `product-list-server-v2.js` – Ürün & sipariş HTML sunucusu
- `database_tools_fixed.py` – PostgreSQL bağlantısı ve yardımcı fonksiyonlar

---

## 🔄 Çalışma Akışı (Sipariş Geçmişi Örneği)

1. **Mesaj**: “Geçen cuma siparişlerim?”
2. **Intent Analyzer**: Mesajı `SIPARIS_GECMIS` olarak sınıflandırır, Sales Expert’e devreder.
3. **Sales Expert**: Talebi anlar, gerekirse kullanıcıya JSON çözümü döndürür.
4. **Swarm Runtime**: JSON dönerse doğrudan `get_order_history` çağrısı yapar; aksi halinde `timeframe_text` ile devam eder.
5. **swarm_orders**:
   - `_llm_resolve_order_history_timeframe` çağrısı (güvenli ise Türkçe etiket/note üretir)
   - PostgreSQL’den siparişleri çeker
   - `product-pages/` içinde HTML çıktıyı üretir
   - WhatsApp mesajı ve linki döndürür
6. **whatsapp-webhook-sender**: Yanıt gönderene kadar typing durumunu gösterir, ardından mesajı teslim eder.

---

## 🧪 Geliştirme İpuçları

- **HTML Çıktıları**: `product-pages/` klasörü git tarafından izlenmez; gereksiz dosyaları düzenli temizleyin.
- **WhatsApp Sessions**: `whatsapp-sessions/` klasörünü depoya dahil etmeyin.
- **LLM Fallback**: `_resolve_order_history_timeframe` halen “bu ay”, “geçen ay” gibi kalıpları anında çözer; bu nedenle LLM çağrıları gereksiz yere tetiklenmez.
- **Typing Interval**: Ağ gecikmesi yüksek ortamlarda `WHATSAPP_TYPING_INTERVAL_MS` değerini 4000–8000 ms aralığında tutmak yeterlidir.
- **Debug Script**: `debug_month_detection.py` ile LLM zaman aralığı testleri yapılabilir.

---

## 🛠️ Sorun Giderme

| Sorun | İpuçları |
|-------|----------|
| WhatsApp mesajı gelmiyor | `whatsapp-webhook-sender.js` loglarını kontrol edin, QR yeniden tarayın, `WHATSAPP_WEBHOOK_PORT` çakışması olup olmadığını kontrol edin |
| Sipariş geçmişi boş dönüyor | WhatsApp numarasının `orders.whatsapp_number` alanında doğru formatta olduğundan emin olun; yeni normalizasyon sayesinde `+90…`, `905…` veya `@c.us` çalışır |
| LLM yanıtı “Bu ay…” notu döndürüyor | `_llm_resolve_order_history_timeframe` güven düşük gördüğünde fallback’e döner; ihtiyaç varsa prompt metnini `swarm_orders.py` üzerinden güncelleyin |
| Typing göstergesi kapanmıyor | `whatsapp-web.js` sürümünü ve istemci loglarını kontrol edin; `runWithTypingIndicator` hatalarında `paused` gönderimi atlanmış olabilir |

---

## 📄 Lisans ve İletişim

- **Lisans:** MIT
- **İletişim:** WhatsApp – +90 530 689 78 85

---

> Bu dokümantasyon OpenAI Swarm tabanlı WhatsApp B2B AI Satış Asistanı için güncellenmiştir.
