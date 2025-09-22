-- Sipariş İptal Sistemi için Veritabanı Şema Güncellemeleri
-- WhatsApp B2B System - Order Cancellation Feature

-- 1. Mevcut orders tablosuna iptal kolonları ekle
ALTER TABLE orders 
ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS cancellation_reason TEXT,
ADD COLUMN IF NOT EXISTS cancelled_by VARCHAR(100);

-- 2. İptal geçmişi tablosu oluştur
CREATE TABLE IF NOT EXISTS order_cancellations (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    order_number VARCHAR(50),
    whatsapp_number VARCHAR(50),
    cancelled_at TIMESTAMP DEFAULT NOW(),
    reason TEXT,
    cancelled_by VARCHAR(100),
    previous_status VARCHAR(50),
    total_amount DECIMAL(10,2),
    refund_amount DECIMAL(10,2),
    items_json TEXT, -- Ürün detayları JSON formatında
    created_at TIMESTAMP DEFAULT NOW()
);

-- 3. İptal edilebilir durumlar için index
CREATE INDEX IF NOT EXISTS idx_orders_status_cancellable 
ON orders(status) 
WHERE status IN ('draft', 'pending', 'awaiting_payment');

-- 4. İptal geçmişi için indexler
CREATE INDEX IF NOT EXISTS idx_cancellations_order_id ON order_cancellations(order_id);
CREATE INDEX IF NOT EXISTS idx_cancellations_whatsapp ON order_cancellations(whatsapp_number);
CREATE INDEX IF NOT EXISTS idx_cancellations_date ON order_cancellations(cancelled_at);

-- 5. İptal istatistikleri view'ı
CREATE OR REPLACE VIEW cancellation_stats AS
SELECT 
    DATE(cancelled_at) as cancellation_date,
    COUNT(*) as total_cancellations,
    SUM(refund_amount) as total_refunded,
    COUNT(DISTINCT whatsapp_number) as unique_customers
FROM order_cancellations
GROUP BY DATE(cancelled_at);

-- 6. Son iptal edilen siparişleri getiren fonksiyon
CREATE OR REPLACE FUNCTION get_recent_cancellations(
    p_whatsapp_number VARCHAR DEFAULT NULL,
    p_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    order_number VARCHAR,
    cancelled_at TIMESTAMP,
    reason TEXT,
    refund_amount DECIMAL,
    previous_status VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        oc.order_number,
        oc.cancelled_at,
        oc.reason,
        oc.refund_amount,
        oc.previous_status
    FROM order_cancellations oc
    WHERE (p_whatsapp_number IS NULL OR oc.whatsapp_number = p_whatsapp_number)
    ORDER BY oc.cancelled_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- 7. Sipariş iptal fonksiyonu
CREATE OR REPLACE FUNCTION cancel_order(
    p_order_id INTEGER,
    p_reason TEXT,
    p_cancelled_by VARCHAR
)
RETURNS JSON AS $$
DECLARE
    v_order_record RECORD;
    v_result JSON;
BEGIN
    -- Sipariş bilgilerini al
    SELECT * INTO v_order_record 
    FROM orders 
    WHERE id = p_order_id;
    
    -- Sipariş bulunamadı
    IF NOT FOUND THEN
        RETURN json_build_object(
            'success', false,
            'error', 'Sipariş bulunamadı'
        );
    END IF;
    
    -- İptal edilebilir durumda mı kontrol et
    IF v_order_record.status NOT IN ('draft', 'pending', 'awaiting_payment') THEN
        RETURN json_build_object(
            'success', false,
            'error', 'Bu sipariş iptal edilemez. Durum: ' || v_order_record.status
        );
    END IF;
    
    -- Zaten iptal edilmiş mi?
    IF v_order_record.status = 'cancelled' THEN
        RETURN json_build_object(
            'success', false,
            'error', 'Bu sipariş zaten iptal edilmiş'
        );
    END IF;
    
    -- İptal geçmişine kaydet
    INSERT INTO order_cancellations (
        order_id,
        order_number,
        whatsapp_number,
        reason,
        cancelled_by,
        previous_status,
        total_amount,
        refund_amount,
        items_json
    ) VALUES (
        p_order_id,
        v_order_record.order_number,
        v_order_record.whatsapp_number,
        p_reason,
        p_cancelled_by,
        v_order_record.status,
        v_order_record.total_amount,
        v_order_record.total_amount, -- Full refund for now
        v_order_record.items::TEXT
    );
    
    -- Siparişi güncelle
    UPDATE orders 
    SET 
        status = 'cancelled',
        cancelled_at = NOW(),
        cancellation_reason = p_reason,
        cancelled_by = p_cancelled_by,
        updated_at = NOW()
    WHERE id = p_order_id;
    
    -- Başarılı sonuç döndür
    RETURN json_build_object(
        'success', true,
        'order_number', v_order_record.order_number,
        'refund_amount', v_order_record.total_amount,
        'message', 'Sipariş başarıyla iptal edildi'
    );
END;
$$ LANGUAGE plpgsql;

-- 8. Toplu iptal fonksiyonu (tüm draft siparişleri iptal et)
CREATE OR REPLACE FUNCTION cancel_all_draft_orders(
    p_whatsapp_number VARCHAR,
    p_reason TEXT DEFAULT 'Müşteri talebi ile toplu iptal'
)
RETURNS JSON AS $$
DECLARE
    v_cancelled_count INTEGER := 0;
    v_order_numbers TEXT[] := ARRAY[]::TEXT[];
    v_order RECORD;
BEGIN
    -- Draft siparişleri bul ve iptal et
    FOR v_order IN 
        SELECT id, order_number 
        FROM orders 
        WHERE whatsapp_number = p_whatsapp_number 
        AND status = 'draft'
    LOOP
        -- Her siparişi iptal et
        PERFORM cancel_order(v_order.id, p_reason, p_whatsapp_number);
        v_cancelled_count := v_cancelled_count + 1;
        v_order_numbers := array_append(v_order_numbers, v_order.order_number);
    END LOOP;
    
    -- Sonuç döndür
    IF v_cancelled_count > 0 THEN
        RETURN json_build_object(
            'success', true,
            'cancelled_count', v_cancelled_count,
            'order_numbers', v_order_numbers,
            'message', v_cancelled_count || ' sipariş iptal edildi'
        );
    ELSE
        RETURN json_build_object(
            'success', false,
            'message', 'İptal edilecek taslak sipariş bulunamadı'
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 9. İptal edilebilir siparişleri listele
CREATE OR REPLACE FUNCTION get_cancellable_orders(
    p_whatsapp_number VARCHAR
)
RETURNS JSON AS $$
DECLARE
    v_orders JSON;
BEGIN
    SELECT json_agg(
        json_build_object(
            'order_number', order_number,
            'status', status,
            'total_amount', total_amount,
            'created_at', created_at,
            'items', items
        )
    ) INTO v_orders
    FROM orders
    WHERE whatsapp_number = p_whatsapp_number
    AND status IN ('draft', 'pending', 'awaiting_payment')
    ORDER BY created_at DESC;
    
    IF v_orders IS NULL THEN
        RETURN json_build_object(
            'success', false,
            'message', 'İptal edilebilir sipariş bulunamadı'
        );
    ELSE
        RETURN json_build_object(
            'success', true,
            'orders', v_orders
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 10. Yetki kontrol fonksiyonu
CREATE OR REPLACE FUNCTION can_cancel_order(
    p_order_id INTEGER,
    p_whatsapp_number VARCHAR
)
RETURNS BOOLEAN AS $$
DECLARE
    v_owner VARCHAR;
    v_status VARCHAR;
    v_created_at TIMESTAMP;
BEGIN
    SELECT whatsapp_number, status, created_at 
    INTO v_owner, v_status, v_created_at
    FROM orders 
    WHERE id = p_order_id;
    
    -- Sipariş sahibi mi kontrol et
    IF v_owner != p_whatsapp_number THEN
        RETURN FALSE;
    END IF;
    
    -- İptal edilebilir durumda mı?
    IF v_status NOT IN ('draft', 'pending', 'awaiting_payment') THEN
        RETURN FALSE;
    END IF;
    
    -- 24 saat kuralı (opsiyonel - şimdilik devre dışı)
    -- IF v_created_at < NOW() - INTERVAL '24 hours' THEN
    --     RETURN FALSE;
    -- END IF;
    
    RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- Örnek kullanım:
-- SELECT cancel_order(1, 'Müşteri vazgeçti', '905306897885@c.us');
-- SELECT * FROM get_recent_cancellations('905306897885@c.us');
-- SELECT * FROM get_cancellable_orders('905306897885@c.us');