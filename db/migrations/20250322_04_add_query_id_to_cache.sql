-- Migration: Add query_id column to query_cache table
-- This column will store a reference to the query id for linking with other tables

BEGIN;

-- Add query_id column if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'eligibility' 
        AND table_name = 'query_cache' 
        AND column_name = 'query_id'
    ) THEN
        ALTER TABLE eligibility.query_cache ADD COLUMN query_id TEXT;
    END IF;
END $$;

-- Add unique constraint if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        JOIN pg_class cl ON cl.oid = c.conrelid
        WHERE n.nspname = 'eligibility'
        AND cl.relname = 'query_cache'
        AND c.conname = 'unique_natural_query'
    ) THEN
        ALTER TABLE eligibility.query_cache ADD CONSTRAINT unique_natural_query UNIQUE (natural_query);
    END IF;
END $$;

-- Add index for last_used if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_indexes
        WHERE schemaname = 'eligibility'
        AND tablename = 'query_cache'
        AND indexname = 'idx_query_cache_last_used'
    ) THEN
        CREATE INDEX idx_query_cache_last_used ON eligibility.query_cache (last_used);
    END IF;
END $$;

COMMIT;

-- Rollback:
-- ALTER TABLE eligibility.query_cache DROP CONSTRAINT IF EXISTS unique_natural_query;
-- ALTER TABLE eligibility.query_cache DROP COLUMN IF EXISTS query_id;
-- DROP INDEX IF EXISTS idx_query_cache_last_used; 