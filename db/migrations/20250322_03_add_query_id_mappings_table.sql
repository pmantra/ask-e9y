-- Migration: Add query_id_mappings table
-- This table will store mappings between original and new query IDs for tracking related queries

BEGIN;

-- Create query_id_mappings table
CREATE TABLE IF NOT EXISTS eligibility.query_id_mappings (
    new_query_id TEXT PRIMARY KEY,
    original_query_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups by original query ID
CREATE INDEX IF NOT EXISTS idx_query_id_mappings_original_id 
ON eligibility.query_id_mappings (original_query_id);

COMMIT;

-- Rollback:
-- DROP TABLE IF EXISTS eligibility.query_id_mappings;
-- DROP INDEX IF EXISTS idx_query_id_mappings_original_id; 