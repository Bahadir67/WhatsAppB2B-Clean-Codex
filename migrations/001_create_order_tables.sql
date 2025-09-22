-- Migration: Create Order Management Tables
-- Date: 2025-09-11
-- Description: Creates orders and order_items tables for multi-product order support

-- Run this migration in a transaction
BEGIN;

-- Create orders table if not exists
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(20) UNIQUE NOT NULL,
    whatsapp_number VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    total_amount DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP,
    cancelled_at TIMESTAMP,
    CONSTRAINT chk_status CHECK (status IN ('draft', 'confirmed', 'cancelled'))
);

-- Create order_items table if not exists
CREATE TABLE IF NOT EXISTS order_items (
    id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_code VARCHAR(50) NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10,2) NOT NULL CHECK (unit_price >= 0),
    total_price DECIMAL(10,2) NOT NULL CHECK (total_price >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_orders_whatsapp ON orders(whatsapp_number);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_code);

-- Enhance temp_product_sessions for cart functionality
ALTER TABLE temp_product_sessions 
ADD COLUMN IF NOT EXISTS cart_items JSONB DEFAULT '[]'::jsonb,
ADD COLUMN IF NOT EXISTS cart_updated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS order_state VARCHAR(20) DEFAULT 'browsing';

-- Add GIN index for JSON queries
CREATE INDEX IF NOT EXISTS idx_sessions_cart ON temp_product_sessions USING GIN (cart_items);

-- Create sequence for order numbers if not exists
CREATE SEQUENCE IF NOT EXISTS order_number_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

COMMIT;

-- Rollback script (save separately)
-- DROP TABLE IF EXISTS order_items;
-- DROP TABLE IF EXISTS orders;
-- ALTER TABLE temp_product_sessions 
-- DROP COLUMN IF EXISTS cart_items,
-- DROP COLUMN IF EXISTS cart_updated_at,
-- DROP COLUMN IF EXISTS order_state;
-- DROP SEQUENCE IF EXISTS order_number_seq;