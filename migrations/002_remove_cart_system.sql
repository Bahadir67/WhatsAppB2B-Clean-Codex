-- Migration 002: Remove Cart System for Swarm-Only Single-Product Workflow
-- Date: 2025-09-12
-- Description: Removes cart functionality to implement single-product instant workflow

BEGIN;

-- Remove cart-related columns from temp_product_sessions
ALTER TABLE temp_product_sessions 
DROP COLUMN IF EXISTS cart_items,
DROP COLUMN IF EXISTS cart_updated_at;

-- Drop the GIN index on cart_items if it exists
DROP INDEX IF EXISTS idx_sessions_cart;

-- Update order_state values (keep this for single-product workflow)
-- No changes needed to order_state as it's still useful for tracking session state

-- Add comment to document the change
COMMENT ON TABLE temp_product_sessions IS 'Updated for single-product instant workflow - cart system removed 2025-09-12';

-- Verify the changes
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'temp_product_sessions'
ORDER BY ordinal_position;

COMMIT;

-- Rollback script (for reference - save separately if needed)
-- BEGIN;
-- ALTER TABLE temp_product_sessions 
-- ADD COLUMN cart_items JSONB DEFAULT '[]'::jsonb,
-- ADD COLUMN cart_updated_at TIMESTAMP;
-- CREATE INDEX idx_sessions_cart ON temp_product_sessions USING GIN (cart_items);
-- COMMIT;