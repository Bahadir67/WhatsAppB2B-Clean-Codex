-- Mevcut valve_bul fonksiyonunu extra parametrelerle güncelle
CREATE OR REPLACE FUNCTION valve_bul(
    tip VARCHAR DEFAULT NULL,
    baglanti_boyutu VARCHAR DEFAULT NULL,
    extra1 TEXT DEFAULT NULL,
    extra2 TEXT DEFAULT NULL,
    extra3 TEXT DEFAULT NULL,
    extra4 TEXT DEFAULT NULL
)
RETURNS TABLE(
    id INTEGER,
    product_code TEXT,
    product_name TEXT,
    price NUMERIC,
    stock_quantity INTEGER,
    description TEXT,
    specifications TEXT,
    category TEXT,
    brand TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.product_code,
        p.product_name,
        p.price,
        p.stock_quantity,
        p.description,
        p.specifications,
        p.category,
        p.brand
    FROM products_semantic p
    WHERE 
        -- Valf kategorisi filtresi
        (p.category ILIKE '%valf%' OR p.category ILIKE '%valve%' OR 
         p.product_name ILIKE '%valf%' OR p.product_name ILIKE '%valve%')
    AND (
        -- Tip parametresi kontrolü (5/2, 3/2, vb.)
        tip IS NULL OR 
        p.product_name ~ ('.*' || tip || '.*') OR 
        p.description ~ ('.*' || tip || '.*') OR
        p.specifications ~ ('.*' || tip || '.*')
    )
    AND (
        -- Bağlantı boyutu kontrolü (1/4, 1/8, vb.)
        baglanti_boyutu IS NULL OR 
        p.product_name ~ ('.*' || baglanti_boyutu || '.*') OR 
        p.description ~ ('.*' || baglanti_boyutu || '.*') OR
        p.specifications ~ ('.*' || baglanti_boyutu || '.*')
    )
    -- Extra1 kontrolü
    AND (extra1 IS NULL OR (
        p.product_name ILIKE '%' || extra1 || '%' OR 
        p.description ILIKE '%' || extra1 || '%' OR 
        p.specifications ILIKE '%' || extra1 || '%'
    ))
    -- Extra2 kontrolü
    AND (extra2 IS NULL OR (
        p.product_name ILIKE '%' || extra2 || '%' OR 
        p.description ILIKE '%' || extra2 || '%' OR 
        p.specifications ILIKE '%' || extra2 || '%'
    ))
    -- Extra3 kontrolü
    AND (extra3 IS NULL OR (
        p.product_name ILIKE '%' || extra3 || '%' OR 
        p.description ILIKE '%' || extra3 || '%' OR 
        p.specifications ILIKE '%' || extra3 || '%'
    ))
    -- Extra4 kontrolü
    AND (extra4 IS NULL OR (
        p.product_name ILIKE '%' || extra4 || '%' OR 
        p.description ILIKE '%' || extra4 || '%' OR 
        p.specifications ILIKE '%' || extra4 || '%'
    ))
    AND p.stock_quantity > 0
    ORDER BY 
        -- Relevance scoring
        CASE 
            WHEN tip IS NOT NULL AND p.product_name ILIKE ('%' || tip || '%') THEN 1
            WHEN tip IS NOT NULL AND p.description ILIKE ('%' || tip || '%') THEN 2
            ELSE 3
        END,
        CASE 
            WHEN baglanti_boyutu IS NOT NULL AND p.product_name ILIKE ('%' || baglanti_boyutu || '%') THEN 1
            WHEN baglanti_boyutu IS NOT NULL AND p.description ILIKE ('%' || baglanti_boyutu || '%') THEN 2
            ELSE 3
        END,
        p.stock_quantity DESC,
        p.price ASC;
END;
$$;

-- valve_bul_in_stock fonksiyonunu da güncelle
CREATE OR REPLACE FUNCTION valve_bul_in_stock(
    tip VARCHAR DEFAULT NULL,
    baglanti_boyutu VARCHAR DEFAULT NULL,
    extra1 TEXT DEFAULT NULL,
    extra2 TEXT DEFAULT NULL,
    extra3 TEXT DEFAULT NULL,
    extra4 TEXT DEFAULT NULL,
    min_stock INTEGER DEFAULT 1
)
RETURNS TABLE(
    id INTEGER,
    product_code TEXT,
    product_name TEXT,
    price NUMERIC,
    stock_quantity INTEGER,
    description TEXT,
    specifications TEXT,
    category TEXT,
    brand TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM valve_bul(tip, baglanti_boyutu, extra1, extra2, extra3, extra4)
    WHERE stock_quantity >= min_stock;
END;
$$;