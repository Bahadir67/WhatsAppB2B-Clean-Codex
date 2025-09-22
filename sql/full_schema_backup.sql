--
-- PostgreSQL database dump
--

-- Dumped from database version 17.4
-- Dumped by pg_dump version 17.4

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: ChatProvider; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public."ChatProvider" AS ENUM (
    'WHATSAPP',
    'DIALOG360'
);


ALTER TYPE public."ChatProvider" OWNER TO postgres;

--
-- Name: CollaborationType; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public."CollaborationType" AS ENUM (
    'READ',
    'WRITE',
    'FULL_ACCESS'
);


ALTER TYPE public."CollaborationType" OWNER TO postgres;

--
-- Name: GraphNavigation; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public."GraphNavigation" AS ENUM (
    'MOUSE',
    'TRACKPAD'
);


ALTER TYPE public."GraphNavigation" OWNER TO postgres;

--
-- Name: Plan; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public."Plan" AS ENUM (
    'FREE',
    'STARTER',
    'PRO',
    'LIFETIME',
    'OFFERED',
    'CUSTOM',
    'UNLIMITED',
    'ENTERPRISE'
);


ALTER TYPE public."Plan" OWNER TO postgres;

--
-- Name: WorkspaceRole; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public."WorkspaceRole" AS ENUM (
    'ADMIN',
    'MEMBER',
    'GUEST'
);


ALTER TYPE public."WorkspaceRole" OWNER TO postgres;

--
-- Name: cleanup_old_sessions(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.cleanup_old_sessions() RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  DELETE FROM temp_product_sessions 
  WHERE created_at < NOW() - INTERVAL '2 hours';
END;
$$;


ALTER FUNCTION public.cleanup_old_sessions() OWNER TO postgres;

--
-- Name: count_cylinders(integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.count_cylinders(cap integer, strok integer) RETURNS integer
    LANGUAGE plpgsql
    AS $$
                DECLARE
                  total_count INTEGER;
                BEGIN
                  SELECT COUNT(*) INTO total_count
                  FROM find_cylinder(cap, strok);
                  
                  RETURN total_count;
                END;
                $$;


ALTER FUNCTION public.count_cylinders(cap integer, strok integer) OWNER TO postgres;

--
-- Name: find_air_preparation_units(text, text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_air_preparation_units(p_query text DEFAULT NULL::text, p_unit_type text DEFAULT NULL::text, p_connection_size text DEFAULT NULL::text, p_keywords text DEFAULT NULL::text) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, unit_type text, connection_size text, description text)
    LANGUAGE plpgsql
    AS $_$
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
$_$;


ALTER FUNCTION public.find_air_preparation_units(p_query text, p_unit_type text, p_connection_size text, p_keywords text) OWNER TO postgres;

--
-- Name: find_air_units_in_stock(text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_air_units_in_stock(p_query text DEFAULT NULL::text, p_unit_type text DEFAULT NULL::text, p_connection_size text DEFAULT NULL::text) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, unit_type text, connection_size text, description text)
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION public.find_air_units_in_stock(p_query text, p_unit_type text, p_connection_size text) OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: products_semantic; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.products_semantic (
    id integer NOT NULL,
    product_code text NOT NULL,
    product_name text NOT NULL,
    price numeric(10,2),
    stock_quantity integer DEFAULT 0,
    description text,
    specifications text,
    category text,
    brand text
);


ALTER TABLE public.products_semantic OWNER TO postgres;

--
-- Name: find_cylinder(integer, integer, text, text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_cylinder(cap integer DEFAULT NULL::integer, strok integer DEFAULT NULL::integer, extra1 text DEFAULT NULL::text, extra2 text DEFAULT NULL::text, extra3 text DEFAULT NULL::text, extra4 text DEFAULT NULL::text) RETURNS TABLE("like" public.products_semantic)
    LANGUAGE plpgsql
    AS $_$
                BEGIN
                  RETURN QUERY
                  WITH number_extract AS (
                    SELECT 
                      id, product_code, product_name, price, stock_quantity,
                      description, specifications, category, brand,
                      -- İlk iki sayıyı çıkar, büyük sayıları filtrele
                      CASE WHEN length((string_to_array(regexp_replace(regexp_replace(product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[1]) <= 4 
                           THEN (string_to_array(regexp_replace(regexp_replace(product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[1]::INT 
                           ELSE NULL END AS first_num,
                      CASE WHEN length((string_to_array(regexp_replace(regexp_replace(product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[2]) <= 4 
                           THEN (string_to_array(regexp_replace(regexp_replace(product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[2]::INT 
                           ELSE NULL END AS second_num
                    FROM products_semantic
                    WHERE 
                      (product_name ILIKE '%SIL%' OR product_name ILIKE '%SİL%')
                      AND regexp_replace(product_name, '[^0-9]+', ' ', 'g') ~ '[0-9]'
                      -- Extra parameter filtering
                      AND (extra1 IS NULL OR (
                          product_name ILIKE '%' || extra1 || '%' OR 
                          description ILIKE '%' || extra1 || '%' OR 
                          specifications ILIKE '%' || extra1 || '%'
                      ))
                      AND (extra2 IS NULL OR (
                          product_name ILIKE '%' || extra2 || '%' OR 
                          description ILIKE '%' || extra2 || '%' OR 
                          specifications ILIKE '%' || extra2 || '%'
                      ))
                      AND (extra3 IS NULL OR (
                          product_name ILIKE '%' || extra3 || '%' OR 
                          description ILIKE '%' || extra3 || '%' OR 
                          specifications ILIKE '%' || extra3 || '%'
                      ))
                      AND (extra4 IS NULL OR (
                          product_name ILIKE '%' || extra4 || '%' OR 
                          description ILIKE '%' || extra4 || '%' OR 
                          specifications ILIKE '%' || extra4 || '%'
                      ))
                  )
                  SELECT id, product_code, product_name, price, 
                         stock_quantity, description, specifications, 
                         category, brand 
                  FROM number_extract
                  WHERE 
                    (cap IS NULL OR first_num = cap)
                    AND (strok IS NULL OR second_num = strok)
                  ORDER BY stock_quantity DESC;
                END;
                $_$;


ALTER FUNCTION public.find_cylinder(cap integer, strok integer, extra1 text, extra2 text, extra3 text, extra4 text) OWNER TO postgres;

--
-- Name: find_cylinder_in_stock(integer, integer, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_cylinder_in_stock(cap integer DEFAULT NULL::integer, strok integer DEFAULT NULL::integer, min_stock integer DEFAULT 1) RETURNS TABLE("like" public.products_semantic)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                  RETURN QUERY
                  SELECT * FROM find_cylinder(cap, strok)
                  WHERE stock_quantity >= min_stock
                  ORDER BY stock_quantity DESC;
                END;
                $$;


ALTER FUNCTION public.find_cylinder_in_stock(cap integer, strok integer, min_stock integer) OWNER TO postgres;

--
-- Name: find_cylinder_in_stock(integer, integer, integer, text, text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_cylinder_in_stock(cap integer DEFAULT NULL::integer, strok integer DEFAULT NULL::integer, min_stock integer DEFAULT 1, extra1 text DEFAULT NULL::text, extra2 text DEFAULT NULL::text, extra3 text DEFAULT NULL::text, extra4 text DEFAULT NULL::text) RETURNS TABLE("like" public.products_semantic)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                  RETURN QUERY
                  SELECT * FROM find_cylinder(cap, strok, extra1, extra2, extra3, extra4)
                  WHERE stock_quantity >= min_stock
                  ORDER BY stock_quantity DESC;
                END;
                $$;


ALTER FUNCTION public.find_cylinder_in_stock(cap integer, strok integer, min_stock integer, extra1 text, extra2 text, extra3 text, extra4 text) OWNER TO postgres;

--
-- Name: find_cylinder_with_extras(integer, integer, text, text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_cylinder_with_extras(cap integer DEFAULT NULL::integer, strok integer DEFAULT NULL::integer, extra1 text DEFAULT NULL::text, extra2 text DEFAULT NULL::text, extra3 text DEFAULT NULL::text, extra4 text DEFAULT NULL::text) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, description text, specifications text, category text, brand text)
    LANGUAGE plpgsql
    AS $_$
BEGIN
  RETURN QUERY
  WITH number_extract AS (
    SELECT 
      p.id, p.product_code, p.product_name, p.price, p.stock_quantity,
      p.description, p.specifications, p.category, p.brand,
      CASE WHEN length((string_to_array(regexp_replace(regexp_replace(p.product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[1]) <= 4 
           THEN (string_to_array(regexp_replace(regexp_replace(p.product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[1]::INT 
           ELSE NULL END AS first_num,
      CASE WHEN length((string_to_array(regexp_replace(regexp_replace(p.product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[2]) <= 4 
           THEN (string_to_array(regexp_replace(regexp_replace(p.product_name, '[^0-9]+', ' ', 'g'), '^ +| +$', '', 'g'), ' '))[2]::INT 
           ELSE NULL END AS second_num
    FROM products_semantic p
    WHERE 
      (p.product_name ILIKE '%SIL%' OR p.product_name ILIKE '%SİL%')
      AND regexp_replace(p.product_name, '[^0-9]+', ' ', 'g') ~ '[0-9]'
      AND (extra1 IS NULL OR (
          p.product_name ILIKE '%' || extra1 || '%' OR 
          p.description ILIKE '%' || extra1 || '%' OR 
          p.specifications ILIKE '%' || extra1 || '%'
      ))
      AND (extra2 IS NULL OR (
          p.product_name ILIKE '%' || extra2 || '%' OR 
          p.description ILIKE '%' || extra2 || '%' OR 
          p.specifications ILIKE '%' || extra2 || '%'
      ))
      AND (extra3 IS NULL OR (
          p.product_name ILIKE '%' || extra3 || '%' OR 
          p.description ILIKE '%' || extra3 || '%' OR 
          p.specifications ILIKE '%' || extra3 || '%'
      ))
      AND (extra4 IS NULL OR (
          p.product_name ILIKE '%' || extra4 || '%' OR 
          p.description ILIKE '%' || extra4 || '%' OR 
          p.specifications ILIKE '%' || extra4 || '%'
      ))
  )
  SELECT ne.id, ne.product_code, ne.product_name, ne.price, 
         ne.stock_quantity, ne.description, ne.specifications, 
         ne.category, ne.brand 
  FROM number_extract ne
  WHERE 
    (cap IS NULL OR ne.first_num = cap)
    AND (strok IS NULL OR ne.second_num = strok)
  ORDER BY ne.stock_quantity DESC;
END;
$_$;


ALTER FUNCTION public.find_cylinder_with_extras(cap integer, strok integer, extra1 text, extra2 text, extra3 text, extra4 text) OWNER TO postgres;

--
-- Name: find_fry(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_fry(p_connection_size text DEFAULT NULL::text) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, connection_size text)
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION public.find_fry(p_connection_size text) OWNER TO postgres;

--
-- Name: find_mfry(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_mfry(p_connection_size text DEFAULT NULL::text) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, connection_size text)
    LANGUAGE plpgsql
    AS $$
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
  $$;


ALTER FUNCTION public.find_mfry(p_connection_size text) OWNER TO postgres;

--
-- Name: find_mr(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_mr(p_connection_size text DEFAULT NULL::text) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, connection_size text)
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION public.find_mr(p_connection_size text) OWNER TO postgres;

--
-- Name: find_products_by_price(numeric, numeric); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_products_by_price(min_price numeric DEFAULT 0, max_price numeric DEFAULT 999999) RETURNS TABLE("like" public.products_semantic)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                  RETURN QUERY
                  SELECT * FROM products_semantic
                  WHERE price BETWEEN min_price AND max_price
                  ORDER BY price ASC;
                END;
                $$;


ALTER FUNCTION public.find_products_by_price(min_price numeric, max_price numeric) OWNER TO postgres;

--
-- Name: find_similar_products(text, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_similar_products(product_code_input text, limit_count integer DEFAULT 10) RETURNS TABLE("like" public.products_semantic)
    LANGUAGE plpgsql
    AS $$
                DECLARE
                  target_category TEXT;
                  target_brand TEXT;
                BEGIN
                  -- Hedef ürünün kategori ve markasını al
                  SELECT category, brand INTO target_category, target_brand
                  FROM products_semantic
                  WHERE product_code = product_code_input
                  LIMIT 1;
                  
                  -- Benzer ürünleri getir
                  RETURN QUERY
                  SELECT * FROM products_semantic
                  WHERE 
                    product_code != product_code_input
                    AND (category = target_category OR brand = target_brand)
                    AND stock_quantity > 0
                  ORDER BY 
                    CASE WHEN category = target_category AND brand = target_brand THEN 0
                         WHEN category = target_category THEN 1
                         ELSE 2 END,
                    stock_quantity DESC
                  LIMIT limit_count;
                END;
                $$;


ALTER FUNCTION public.find_similar_products(product_code_input text, limit_count integer) OWNER TO postgres;

--
-- Name: find_y(text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.find_y(p_connection_size text DEFAULT NULL::text) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, connection_size text)
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION public.find_y(p_connection_size text) OWNER TO postgres;

--
-- Name: search_products_semantic(character varying, jsonb, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.search_products_semantic(p_category character varying DEFAULT NULL::character varying, p_specs jsonb DEFAULT NULL::jsonb, p_text character varying DEFAULT NULL::character varying) RETURNS TABLE(product_code character varying, product_name character varying, category character varying, price numeric, stock_quantity integer, specifications jsonb, relevance real)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ps.product_code,
        ps.product_name,
        ps.category,
        ps.price,
        ps.stock_quantity,
        ps.specifications,
        CASE 
            WHEN p_text IS NOT NULL THEN 
                ts_rank(ps.search_vector, plainto_tsquery('turkish', p_text))
            ELSE 1.0
        END as relevance
    FROM products_semantic ps
    WHERE 
        (p_category IS NULL OR ps.category = p_category)
        AND (p_specs IS NULL OR ps.specifications @> p_specs)
        AND (p_text IS NULL OR ps.search_vector @@ plainto_tsquery('turkish', p_text))
        AND ps.stock_quantity > 0
    ORDER BY relevance DESC, ps.product_name
    LIMIT 50;
END;
$$;


ALTER FUNCTION public.search_products_semantic(p_category character varying, p_specs jsonb, p_text character varying) OWNER TO postgres;

--
-- Name: search_products_smart(text, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.search_products_smart(search_term text, limit_count integer DEFAULT 50) RETURNS TABLE("like" public.products_semantic)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                  RETURN QUERY
                  SELECT * FROM products_semantic
                  WHERE 
                    product_name ILIKE '%' || search_term || '%'
                    OR description ILIKE '%' || search_term || '%'
                    OR specifications ILIKE '%' || search_term || '%'
                  ORDER BY stock_quantity DESC
                  LIMIT limit_count;
                END;
                $$;


ALTER FUNCTION public.search_products_smart(search_term text, limit_count integer) OWNER TO postgres;

--
-- Name: update_updated_at_column(); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.update_updated_at_column() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.update_updated_at_column() OWNER TO postgres;

--
-- Name: valve_bul(character varying, character varying); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.valve_bul(tip character varying DEFAULT NULL::character varying, baglanti_boyutu character varying DEFAULT NULL::character varying) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, description text, specifications text, category text, brand text)
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


ALTER FUNCTION public.valve_bul(tip character varying, baglanti_boyutu character varying) OWNER TO postgres;

--
-- Name: valve_bul(character varying, character varying, text, text, text, text); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.valve_bul(tip character varying DEFAULT NULL::character varying, baglanti_boyutu character varying DEFAULT NULL::character varying, extra1 text DEFAULT NULL::text, extra2 text DEFAULT NULL::text, extra3 text DEFAULT NULL::text, extra4 text DEFAULT NULL::text) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, description text, specifications text, category text, brand text)
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


ALTER FUNCTION public.valve_bul(tip character varying, baglanti_boyutu character varying, extra1 text, extra2 text, extra3 text, extra4 text) OWNER TO postgres;

--
-- Name: valve_bul_in_stock(character varying, character varying, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.valve_bul_in_stock(tip character varying DEFAULT NULL::character varying, baglanti_boyutu character varying DEFAULT NULL::character varying, min_stock integer DEFAULT 1) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, description text, specifications text, category text, brand text)
    LANGUAGE plpgsql
    AS $$
                BEGIN
                    RETURN QUERY
                    SELECT 
                        v.id,
                        v.product_code,
                        v.product_name,
                        v.price,
                        v.stock_quantity,
                        v.description,
                        v.specifications,
                        v.category,
                        v.brand
                    FROM valve_bul(tip, baglanti_boyutu) v
                    WHERE v.stock_quantity >= min_stock
                    ORDER BY v.stock_quantity DESC;
                END;
                $$;


ALTER FUNCTION public.valve_bul_in_stock(tip character varying, baglanti_boyutu character varying, min_stock integer) OWNER TO postgres;

--
-- Name: valve_bul_in_stock(character varying, character varying, text, text, text, text, integer); Type: FUNCTION; Schema: public; Owner: postgres
--

CREATE FUNCTION public.valve_bul_in_stock(tip character varying DEFAULT NULL::character varying, baglanti_boyutu character varying DEFAULT NULL::character varying, extra1 text DEFAULT NULL::text, extra2 text DEFAULT NULL::text, extra3 text DEFAULT NULL::text, extra4 text DEFAULT NULL::text, min_stock integer DEFAULT 1) RETURNS TABLE(id integer, product_code text, product_name text, price numeric, stock_quantity integer, description text, specifications text, category text, brand text)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM valve_bul(tip, baglanti_boyutu, extra1, extra2, extra3, extra4)
    WHERE stock_quantity >= min_stock;
END;
$$;


ALTER FUNCTION public.valve_bul_in_stock(tip character varying, baglanti_boyutu character varying, extra1 text, extra2 text, extra3 text, extra4 text, min_stock integer) OWNER TO postgres;

--
-- Name: customer_history; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.customer_history (
    id integer NOT NULL,
    customer_id integer,
    event_type character varying(30) NOT NULL,
    event_description text,
    amount numeric(12,2),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.customer_history OWNER TO postgres;

--
-- Name: customer_history_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.customer_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.customer_history_id_seq OWNER TO postgres;

--
-- Name: customer_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.customer_history_id_seq OWNED BY public.customer_history.id;


--
-- Name: customers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.customers (
    id integer NOT NULL,
    whatsapp_number character varying(50) NOT NULL,
    company_name character varying(200) NOT NULL,
    contact_person character varying(100),
    email character varying(100),
    tax_number character varying(20),
    customer_type character varying(20) DEFAULT 'PERAKENDE'::character varying,
    risk_score integer DEFAULT 50,
    credit_limit numeric(12,2) DEFAULT 0,
    current_balance numeric(12,2) DEFAULT 0,
    payment_terms integer DEFAULT 0,
    address text,
    city character varying(50),
    status character varying(20) DEFAULT 'ACTIVE'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.customers OWNER TO postgres;

--
-- Name: customers_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.customers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.customers_id_seq OWNER TO postgres;

--
-- Name: customers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.customers_id_seq OWNED BY public.customers.id;


--
-- Name: inventory; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.inventory (
    id integer NOT NULL,
    product_code character varying(50) NOT NULL,
    available_stock integer DEFAULT 0,
    reserved_stock integer DEFAULT 0,
    min_stock_level integer DEFAULT 0,
    last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.inventory OWNER TO postgres;

--
-- Name: inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_id_seq OWNER TO postgres;

--
-- Name: inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.inventory_id_seq OWNED BY public.inventory.id;


--
-- Name: langchain_chat_histories; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.langchain_chat_histories (
    id integer NOT NULL,
    session_id character varying(255) NOT NULL,
    message jsonb NOT NULL
);


ALTER TABLE public.langchain_chat_histories OWNER TO postgres;

--
-- Name: langchain_chat_histories_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.langchain_chat_histories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.langchain_chat_histories_id_seq OWNER TO postgres;

--
-- Name: langchain_chat_histories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.langchain_chat_histories_id_seq OWNED BY public.langchain_chat_histories.id;


--
-- Name: order_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.order_items (
    id integer NOT NULL,
    order_id integer,
    product_code character varying(50) NOT NULL,
    product_name text NOT NULL,
    quantity integer NOT NULL,
    unit_price numeric(10,2) NOT NULL,
    total_price numeric(10,2) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.order_items OWNER TO postgres;

--
-- Name: order_items_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.order_items_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.order_items_id_seq OWNER TO postgres;

--
-- Name: order_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.order_items_id_seq OWNED BY public.order_items.id;


--
-- Name: order_number_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.order_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.order_number_seq OWNER TO postgres;

--
-- Name: orders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.orders (
    id integer NOT NULL,
    order_number character varying(20) NOT NULL,
    customer_id integer,
    whatsapp_number character varying(50) NOT NULL,
    total_amount numeric(12,2) NOT NULL,
    status character varying(30) DEFAULT 'PENDING'::character varying,
    payment_status character varying(20) DEFAULT 'PENDING'::character varying,
    order_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    delivery_address text,
    delivery_city character varying(50),
    estimated_delivery date,
    tracking_code character varying(50),
    carrier character varying(50),
    notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.orders OWNER TO postgres;

--
-- Name: orders_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.orders_id_seq OWNER TO postgres;

--
-- Name: orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.orders_id_seq OWNED BY public.orders.id;


--
-- Name: pricing; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pricing (
    id integer NOT NULL,
    product_code character varying(50) NOT NULL,
    customer_type character varying(20) NOT NULL,
    price numeric(10,2) NOT NULL,
    discount_percent numeric(5,2) DEFAULT 0,
    valid_from date DEFAULT CURRENT_DATE,
    valid_until date,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.pricing OWNER TO postgres;

--
-- Name: pricing_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.pricing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pricing_id_seq OWNER TO postgres;

--
-- Name: pricing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.pricing_id_seq OWNED BY public.pricing.id;


--
-- Name: products_semantic_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.products_semantic_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.products_semantic_id_seq OWNER TO postgres;

--
-- Name: products_semantic_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.products_semantic_id_seq OWNED BY public.products_semantic.id;


--
-- Name: shipments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.shipments (
    id integer NOT NULL,
    order_id integer,
    tracking_code character varying(50) NOT NULL,
    carrier character varying(50) NOT NULL,
    status character varying(30) DEFAULT 'PREPARING'::character varying,
    shipped_date timestamp without time zone,
    delivered_date timestamp without time zone,
    recipient_name character varying(100),
    delivery_notes text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.shipments OWNER TO postgres;

--
-- Name: shipments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.shipments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.shipments_id_seq OWNER TO postgres;

--
-- Name: shipments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.shipments_id_seq OWNED BY public.shipments.id;


--
-- Name: temp_product_sessions_backup; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.temp_product_sessions_backup (
    session_id text,
    whatsapp_number text,
    message_id text,
    product_list jsonb,
    product_count integer,
    created_at timestamp without time zone,
    order_state character varying(20)
);


ALTER TABLE public.temp_product_sessions_backup OWNER TO postgres;

--
-- Name: customer_history id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customer_history ALTER COLUMN id SET DEFAULT nextval('public.customer_history_id_seq'::regclass);


--
-- Name: customers id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customers ALTER COLUMN id SET DEFAULT nextval('public.customers_id_seq'::regclass);


--
-- Name: inventory id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory ALTER COLUMN id SET DEFAULT nextval('public.inventory_id_seq'::regclass);


--
-- Name: langchain_chat_histories id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.langchain_chat_histories ALTER COLUMN id SET DEFAULT nextval('public.langchain_chat_histories_id_seq'::regclass);


--
-- Name: order_items id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items ALTER COLUMN id SET DEFAULT nextval('public.order_items_id_seq'::regclass);


--
-- Name: orders id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders ALTER COLUMN id SET DEFAULT nextval('public.orders_id_seq'::regclass);


--
-- Name: pricing id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pricing ALTER COLUMN id SET DEFAULT nextval('public.pricing_id_seq'::regclass);


--
-- Name: products_semantic id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products_semantic ALTER COLUMN id SET DEFAULT nextval('public.products_semantic_id_seq'::regclass);


--
-- Name: shipments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shipments ALTER COLUMN id SET DEFAULT nextval('public.shipments_id_seq'::regclass);


--
-- Name: customer_history customer_history_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customer_history
    ADD CONSTRAINT customer_history_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: customers customers_whatsapp_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_whatsapp_number_key UNIQUE (whatsapp_number);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_product_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_product_code_key UNIQUE (product_code);


--
-- Name: langchain_chat_histories langchain_chat_histories_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.langchain_chat_histories
    ADD CONSTRAINT langchain_chat_histories_pkey PRIMARY KEY (id);


--
-- Name: order_items order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_pkey PRIMARY KEY (id);


--
-- Name: orders orders_order_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_order_number_key UNIQUE (order_number);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: pricing pricing_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pricing
    ADD CONSTRAINT pricing_pkey PRIMARY KEY (id);


--
-- Name: products_semantic products_semantic_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products_semantic
    ADD CONSTRAINT products_semantic_pkey PRIMARY KEY (id);


--
-- Name: shipments shipments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shipments
    ADD CONSTRAINT shipments_pkey PRIMARY KEY (id);


--
-- Name: shipments shipments_tracking_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shipments
    ADD CONSTRAINT shipments_tracking_code_key UNIQUE (tracking_code);


--
-- Name: idx_customers_whatsapp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_customers_whatsapp ON public.customers USING btree (whatsapp_number);


--
-- Name: idx_inventory_product; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_inventory_product ON public.inventory USING btree (product_code);


--
-- Name: idx_order_items_order; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_order_items_order ON public.order_items USING btree (order_id);


--
-- Name: idx_order_items_product; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_order_items_product ON public.order_items USING btree (product_code);


--
-- Name: idx_orders_created; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_created ON public.orders USING btree (created_at DESC);


--
-- Name: idx_orders_customer; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_customer ON public.orders USING btree (customer_id);


--
-- Name: idx_orders_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_status ON public.orders USING btree (status);


--
-- Name: idx_orders_whatsapp; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_orders_whatsapp ON public.orders USING btree (whatsapp_number);


--
-- Name: idx_pricing_product_type; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_pricing_product_type ON public.pricing USING btree (product_code, customer_type);


--
-- Name: customer_history customer_history_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.customer_history
    ADD CONSTRAINT customer_history_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: order_items order_items_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: orders orders_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id);


--
-- Name: shipments shipments_order_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shipments
    ADD CONSTRAINT shipments_order_id_fkey FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- PostgreSQL database dump complete
--

