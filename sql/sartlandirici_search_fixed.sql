-- Şartlandırıcı, Filtre, Regülatör, Yağlayıcı Arama Fonksiyonu
-- WhatsApp B2B System - Air Preparation Units Search
-- TÜM PARAMETRELER AND MANTIĞIYLA ÇALIŞIR

DROP FUNCTION IF EXISTS find_air_preparation_units CASCADE;

CREATE OR REPLACE FUNCTION find_air_preparation_units(
    p_query TEXT DEFAULT NULL,           -- Genel arama metni
    p_unit_type TEXT DEFAULT NULL,       -- MR, FRY, MFRY, Y vb.
    p_connection_size TEXT DEFAULT NULL, -- 1/4, 1/2, 3/8, 3/4, 1/8
    p_keywords TEXT DEFAULT NULL         -- REGÜLATÖR, YAĞLAYICI vb.
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
    v_parsed_size TEXT;
    v_parsed_type TEXT;
    v_parsed_keywords TEXT;
BEGIN
    -- Eğer sadece p_query gelirse, onu parse et
    IF p_query IS NOT NULL AND p_unit_type IS NULL AND p_connection_size IS NULL THEN
        p_query := UPPER(TRIM(p_query));
        
        -- Ölçü algılama
        IF p_query ~ '1/8' THEN v_parsed_size := '1/8';
        ELSIF p_query ~ '1/4' THEN v_parsed_size := '1/4';
        ELSIF p_query ~ '1/2' THEN v_parsed_size := '1/2';
        ELSIF p_query ~ '3/8' THEN v_parsed_size := '3/8';
        ELSIF p_query ~ '3/4' THEN v_parsed_size := '3/4';
        END IF;
        
        -- Tip algılama
        IF p_query ~ '\sMR\s|^MR\s|\sMR$|^MR$' THEN v_parsed_type := 'MR';
        ELSIF p_query ~ 'FRY' THEN v_parsed_type := 'FRY';
        ELSIF p_query ~ 'MFRY|M\(FR\)Y' THEN v_parsed_type := 'MFRY';
        ELSIF p_query ~ '\sY\s|^Y\s|\sY$|^Y$' THEN v_parsed_type := 'Y';
        END IF;
        
        -- Anahtar kelime algılama
        IF p_query ~ 'REGÜLATÖR|REGULATÖR' THEN v_parsed_keywords := 'REGÜLATÖR';
        ELSIF p_query ~ 'YAĞLAYICI' THEN v_parsed_keywords := 'YAĞLAYICI';
        ELSIF p_query ~ 'ŞARTLANDIRICI' THEN v_parsed_keywords := 'ŞARTLANDIRICI';
        END IF;
        
        -- Parse edilenleri parametrelere ata
        IF v_parsed_size IS NOT NULL THEN p_connection_size := v_parsed_size; END IF;
        IF v_parsed_type IS NOT NULL THEN p_unit_type := v_parsed_type; END IF;
        IF v_parsed_keywords IS NOT NULL THEN p_keywords := v_parsed_keywords; END IF;
    END IF;
    
    -- Parametreleri büyük harfe çevir
    IF p_unit_type IS NOT NULL THEN p_unit_type := UPPER(TRIM(p_unit_type)); END IF;
    IF p_keywords IS NOT NULL THEN p_keywords := UPPER(TRIM(p_keywords)); END IF;
    
    RETURN QUERY
    SELECT 
        p.id,
        p.product_code,
        p.product_name,
        p.price,
        p.stock_quantity,
        CASE 
            WHEN p.product_name ~ 'MFRY|M\(FR\)Y' THEN 'MFRY'
            WHEN p.product_name ~ 'MFR|M\(FR\)' AND p.product_name !~ 'Y' THEN 'MFR'
            WHEN p.product_name ~ '\sMR\s' THEN 'MR'
            WHEN p.product_name ~ 'FRY' THEN 'FRY'
            WHEN p.product_name ~ '\sY\s' THEN 'Y'
            WHEN p.product_name ~ 'REGÜLATÖR|REGULATÖR' THEN 'REGULATOR'
            WHEN p.product_name ~ 'YAĞLAYICI' THEN 'YAGLAYICI'
            ELSE 'SARTLANDIRICI'
        END AS unit_type,
        CASE
            WHEN p.product_name ~ '1/8' THEN '1/8'
            WHEN p.product_name ~ '1/4' THEN '1/4'
            WHEN p.product_name ~ '1/2' THEN '1/2'
            WHEN p.product_name ~ '3/8' THEN '3/8'
            WHEN p.product_name ~ '3/4' THEN '3/4'
            ELSE NULL
        END AS connection_size,
        p.description
    FROM products_semantic p
    WHERE 
        -- TÜM PARAMETRELER AND İLE BAĞLANMALI
        
        -- 1. Ölçü filtresi (varsa AND)
        (p_connection_size IS NULL OR p.product_name ~ p_connection_size)
        AND
        -- 2. Tip filtresi (varsa AND)
        (
            p_unit_type IS NULL OR
            CASE 
                WHEN p_unit_type = 'MR' THEN p.product_name ~ '\sMR\s|^MR\s'
                WHEN p_unit_type = 'FRY' THEN p.product_name ~ 'FRY'
                WHEN p_unit_type = 'MFRY' THEN p.product_name ~ 'MFRY|M\(FR\)Y'
                WHEN p_unit_type = 'MFR' THEN p.product_name ~ 'MFR|M\(FR\)'
                WHEN p_unit_type = 'Y' THEN p.product_name ~ '\sY\s|^Y\s'
                ELSE FALSE
            END
        )
        AND
        -- 3. Anahtar kelime filtresi (varsa AND)
        (
            p_keywords IS NULL OR
            CASE
                WHEN p_keywords ~ 'REGÜLATÖR|REGULATÖR' THEN 
                    p.product_name ~ 'REGÜLATÖR|REGULATÖR|REG'
                WHEN p_keywords ~ 'YAĞLAYICI' THEN 
                    p.product_name ~ 'YAĞLAYICI|YAĞ'
                WHEN p_keywords ~ 'ŞARTLANDIRICI' THEN 
                    p.product_name ~ 'ŞARTLANDIRICI|ŞART'
                WHEN p_keywords ~ 'FILTRE' THEN 
                    p.product_name ~ 'FILTRE|FİLTRE'
                ELSE 
                    p.product_name ILIKE '%' || p_keywords || '%'
            END
        )
        AND
        -- 4. Genel kategori filtresi (en az birinde olmalı)
        (
            -- Eğer hiç parametre yoksa, tüm hava hazırlama ürünlerini getir
            (p_unit_type IS NULL AND p_keywords IS NULL AND p_connection_size IS NULL) OR
            -- Yoksa sadece hava hazırlama kategorisinde ara
            p.product_name ~ 'MR|FRY|MFRY|MFR|\sY\s|REGÜLATÖR|REGULATÖR|YAĞLAYICI|ŞARTLANDIRICI|FILTRE'
        )
    ORDER BY 
        p.stock_quantity DESC NULLS LAST,
        p.product_name;
END;
$$ LANGUAGE plpgsql;

-- Yardımcı fonksiyonlar
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

-- Test örnekleri:
-- SELECT * FROM find_air_preparation_units('MR 1/2 REGÜLATÖR');  -- MR AND 1/2 AND REGÜLATÖR
-- SELECT * FROM find_air_preparation_units(NULL, 'MR', '1/2', NULL);  -- MR AND 1/2
-- SELECT * FROM find_air_preparation_units(NULL, NULL, '1/2', 'REGÜLATÖR');  -- 1/2 AND REGÜLATÖR
-- SELECT * FROM find_mr('1/2');  -- MR AND 1/2
-- SELECT * FROM find_y('1/4');  -- Y AND 1/4