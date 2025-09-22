-- Şartlandırıcı, Filtre, Regülatör, Yağlayıcı Arama Fonksiyonu
-- WhatsApp B2B System - Air Preparation Units Search

-- Ana arama fonksiyonu
CREATE OR REPLACE FUNCTION find_air_preparation_units(
    p_query TEXT DEFAULT NULL,
    p_unit_type TEXT DEFAULT NULL,  -- FRY, MFR, Y, vb.
    p_connection_size TEXT DEFAULT NULL,  -- 1/4, 1/2, 3/8, 3/4, 1
    p_features TEXT[] DEFAULT NULL  -- OTO.TAH, METAL KAV, vb.
)
RETURNS TABLE (
    id INTEGER,
    product_code TEXT,
    product_name TEXT, 
    price NUMERIC,
    stock_quantity INTEGER,
    unit_type TEXT,
    connection_size TEXT,
    description TEXT
) AS $$
DECLARE
    v_search_pattern TEXT;
    v_type_pattern TEXT;
BEGIN
    -- Temizlik ve normalizasyon
    IF p_query IS NOT NULL THEN
        p_query := UPPER(TRIM(p_query));
    END IF;
    
    -- Tip algılama (kullanıcı girişinden)
    IF p_unit_type IS NULL AND p_query IS NOT NULL THEN
        -- FRY varyasyonları
        IF p_query ~ 'FRY|F\.?R\.?Y' THEN
            p_unit_type := 'FRY';
        -- M(FR)Y varyasyonları
        ELSIF p_query ~ 'M\(?FR\)?Y|MFRY' THEN
            p_unit_type := 'MFRY';
        -- M(FR) varyasyonları
        ELSIF p_query ~ 'M\(?FR\)?[^Y]|MFR[^Y]' THEN
            p_unit_type := 'MFR';
        -- MR - Sadece Regülatör
        ELSIF p_query ~ '^MR[^F]|^MR\s|^MR-' THEN
            p_unit_type := 'MR';
        -- FR varyasyonları
        ELSIF p_query ~ '^FR[^Y]|FILTRE.*REG' THEN
            p_unit_type := 'FR';
        -- Yağlayıcı
        ELSIF p_query ~ '^\s*Y\s|YAGLAYICI|YAĞLAYICI' THEN
            p_unit_type := 'Y';
        -- Sadece Regülatör
        ELSIF p_query ~ 'REGULAT|REGÜLAT' AND p_query !~ 'FILTRE|FR' THEN
            p_unit_type := 'MR';
        -- Genel şartlandırıcı
        ELSIF p_query ~ 'SART|ŞART' THEN
            p_unit_type := 'SARTLANDIRICI';
        -- Hava hazırlayıcı
        ELSIF p_query ~ 'HAVA.*HAZIRLA' THEN
            p_unit_type := 'HAVA_HAZIRLAYICI';
        END IF;
    END IF;
    
    -- Bağlantı boyutu algılama
    IF p_connection_size IS NULL AND p_query IS NOT NULL THEN
        -- 1/4, 1/2, 3/8, 3/4, 1 formatlarını bul
        IF p_query ~ '1/4' THEN
            p_connection_size := '1/4';
        ELSIF p_query ~ '1/2' THEN
            p_connection_size := '1/2';
        ELSIF p_query ~ '3/8' THEN
            p_connection_size := '3/8';
        ELSIF p_query ~ '3/4' THEN
            p_connection_size := '3/4';
        ELSIF p_query ~ '\s1\s|\-1\s' THEN
            p_connection_size := '1';
        END IF;
    END IF;
    
    -- Ana sorgu
    RETURN QUERY
    SELECT 
        p.id,
        p.product_code,
        p.product_name,
        p.price,
        p.stock_quantity,
        CASE 
            WHEN p.product_name ~ 'M\(?FR\)?Y|MFRY' THEN 'MFRY'
            WHEN p.product_name ~ 'M\(?FR\)?[^Y]|MFR[^Y]' THEN 'MFR'
            WHEN p.product_name ~ '^MR[^F]|^MR\s|^MR-|\sMR\s|\sMR-' THEN 'MR'
            WHEN p.product_name ~ 'FRY' THEN 'FRY'
            WHEN p.product_name ~ 'FR[^Y]' THEN 'FR'
            WHEN p.product_name ~ '^\s*Y\s|YAGLAYICI|YAĞLAYICI' THEN 'Y'
            ELSE 'SARTLANDIRICI'
        END AS unit_type,
        CASE
            WHEN p.product_name ~ '1/4' THEN '1/4'
            WHEN p.product_name ~ '1/2' THEN '1/2'
            WHEN p.product_name ~ '3/8' THEN '3/8'
            WHEN p.product_name ~ '3/4' THEN '3/4'
            WHEN p.product_name ~ '\s1\s|\-1\s' THEN '1'
            ELSE NULL
        END AS connection_size,
        p.description
    FROM products_semantic p
    WHERE 
        -- Temel filtre: şartlandırıcı, filtre, regülatör, yağlayıcı
        (
            p.product_name ILIKE '%SARTLANDIRICI%' OR
            p.product_name ILIKE '%ŞARTLANDIRICI%' OR
            p.product_name ILIKE '%FILTRE%' OR
            p.product_name ILIKE '%REGULAT%' OR
            p.product_name ILIKE '%REGÜLAT%' OR
            p.product_name ILIKE '%YAGLAYICI%' OR
            p.product_name ILIKE '%YAĞLAYICI%' OR
            p.product_name ILIKE '%HAVA HAZIRLA%' OR
            p.product_name ~ 'FRY|MFR|M\(FR\)|^\s*Y\s|^MR[^F]|\sMR\s|\sMR-'
        )
        -- Tip filtresi
        AND (
            p_unit_type IS NULL OR
            CASE p_unit_type
                WHEN 'FRY' THEN p.product_name ~ 'FRY'
                WHEN 'MFRY' THEN p.product_name ~ 'M\(?FR\)?Y|MFRY'
                WHEN 'MFR' THEN p.product_name ~ 'M\(?FR\)?[^Y]|MFR[^Y]'
                WHEN 'MR' THEN p.product_name ~ '^MR[^F]|^MR\s|^MR-|\sMR\s|\sMR-' AND p.product_name !~ 'FR'
                WHEN 'FR' THEN p.product_name ~ 'FR[^Y]'
                WHEN 'Y' THEN p.product_name ~ '^\s*Y\s|YAGLAYICI|YAĞLAYICI'
                WHEN 'SARTLANDIRICI' THEN p.product_name ILIKE '%SART%' OR p.product_name ILIKE '%ŞART%'
                WHEN 'HAVA_HAZIRLAYICI' THEN p.product_name ILIKE '%HAVA%HAZIRLA%'
                ELSE TRUE
            END
        )
        -- Bağlantı boyutu filtresi
        AND (
            p_connection_size IS NULL OR
            p.product_name ~ p_connection_size
        )
        -- Özellik filtresi
        AND (
            p_features IS NULL OR
            (
                SELECT COUNT(*) 
                FROM unnest(p_features) AS feature
                WHERE p.product_name ILIKE '%' || feature || '%'
            ) = array_length(p_features, 1)
        )
        -- Genel arama
        AND (
            p_query IS NULL OR
            p.product_name ILIKE '%' || p_query || '%'
        )
    ORDER BY 
        -- Öncelik sıralaması
        CASE 
            WHEN p.product_name ILIKE p_query || '%' THEN 1  -- Tam eşleşme önce
            WHEN p.stock_quantity > 0 THEN 2  -- Stokta olanlar
            ELSE 3
        END,
        p.product_name;
END;
$$ LANGUAGE plpgsql;

-- Stokta olan ürünler için fonksiyon
CREATE OR REPLACE FUNCTION find_air_units_in_stock(
    p_query TEXT DEFAULT NULL,
    p_unit_type TEXT DEFAULT NULL,
    p_connection_size TEXT DEFAULT NULL
)
RETURNS TABLE (
    id INTEGER,
    product_code TEXT,
    product_name TEXT,
    price NUMERIC,
    stock_quantity INTEGER,
    unit_type TEXT,
    connection_size TEXT,
    description TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM find_air_preparation_units(
        p_query,
        p_unit_type,
        p_connection_size,
        NULL
    )
    WHERE stock_quantity > 0;
END;
$$ LANGUAGE plpgsql;

-- Hızlı arama fonksiyonları
CREATE OR REPLACE FUNCTION find_fry(p_connection_size TEXT DEFAULT NULL)
RETURNS TABLE (
    id INTEGER,
    product_code TEXT,
    product_name TEXT,
    price NUMERIC,
    stock_quantity INTEGER,
    connection_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        id,
        product_code,
        product_name,
        price,
        stock_quantity,
        connection_size
    FROM find_air_preparation_units(NULL, 'FRY', p_connection_size, NULL);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION find_mfry(p_connection_size TEXT DEFAULT NULL)
RETURNS TABLE (
    id INTEGER,
    product_code TEXT,
    product_name TEXT,
    price NUMERIC,
    stock_quantity INTEGER,
    connection_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        id,
        product_code,
        product_name,
        price,
        stock_quantity,
        connection_size
    FROM find_air_preparation_units(NULL, 'MFRY', p_connection_size, NULL);
END;
$$ LANGUAGE plpgsql;

-- Kullanım örnekleri:
-- SELECT * FROM find_air_preparation_units('FRY 1/2');
-- SELECT * FROM find_air_preparation_units(NULL, 'FRY', '1/2');
-- SELECT * FROM find_air_preparation_units(NULL, 'MFRY', NULL, ARRAY['OTO.TAH']);
-- SELECT * FROM find_air_units_in_stock('SARTLANDIRICI');
-- SELECT * FROM find_fry('1/2');
-- SELECT * FROM find_mfry('3/8');

-- MR (Sadece Regülatör) için hızlı arama
CREATE OR REPLACE FUNCTION find_mr(p_connection_size TEXT DEFAULT NULL)
RETURNS TABLE (
    id INTEGER,
    product_code TEXT,
    product_name TEXT,
    price NUMERIC,
    stock_quantity INTEGER,
    connection_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        id,
        product_code,
        product_name,
        price,
        stock_quantity,
        connection_size
    FROM find_air_preparation_units(NULL, 'MR', p_connection_size, NULL);
END;
$$ LANGUAGE plpgsql;

-- Y (Sadece Yağlayıcı) için hızlı arama
CREATE OR REPLACE FUNCTION find_y(p_connection_size TEXT DEFAULT NULL)
RETURNS TABLE (
    id INTEGER,
    product_code TEXT,
    product_name TEXT,
    price NUMERIC,
    stock_quantity INTEGER,
    connection_size TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        id,
        product_code,
        product_name,
        price,
        stock_quantity,
        connection_size
    FROM find_air_preparation_units(NULL, 'Y', p_connection_size, NULL);
END;
$$ LANGUAGE plpgsql;

-- Kullanım örnekleri:
-- SELECT * FROM find_mr('1/2');  -- MR 1/2 regülatörleri
-- SELECT * FROM find_air_preparation_units('MR 1/4');  -- MR 1/4 regülatör
-- SELECT * FROM find_air_preparation_units('regülatör');
-- SELECT * FROM find_y('1/2');  -- Y 1/2 yağlayıcıları
-- SELECT * FROM find_air_preparation_units('yağlayıcı');  -- Tüm yağlayıcılar