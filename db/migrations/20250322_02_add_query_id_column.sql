-- Migration: Add query_id column to query_history table
-- This column will store a reference to the query id for linking with other tables

BEGIN;

-- Add query_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'eligibility' 
        AND table_name = 'query_history' 
        AND column_name = 'query_id'
    ) THEN
        ALTER TABLE eligibility.query_history ADD COLUMN query_id TEXT;
    END IF;
END $$;

COMMIT;

-- Rollback:
-- ALTER TABLE eligibility.query_history DROP COLUMN IF EXISTS query_id; 