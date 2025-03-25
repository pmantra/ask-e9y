-- Migration: Add API metrics table
-- This table will store metrics about API usage and performance

BEGIN;

-- Create api_metrics table
CREATE TABLE IF NOT EXISTS eligibility.api_metrics (
    id SERIAL PRIMARY KEY,
    query_id TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    original_query TEXT NOT NULL,
    prompt_system TEXT,
    prompt_user TEXT,
    cache_status TEXT,
    execution_time_ms FLOAT,
    total_time_ms FLOAT,
    row_count INTEGER,
    schema_size INTEGER,
    token_usage JSONB,
    stage_timings JSONB,
    success BOOLEAN,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_api_metrics_query_id ON eligibility.api_metrics (query_id);
CREATE INDEX IF NOT EXISTS idx_api_metrics_timestamp ON eligibility.api_metrics (timestamp);

COMMIT;

-- Rollback:
-- DROP TABLE IF EXISTS eligibility.api_metrics;
-- DROP INDEX IF EXISTS idx_api_metrics_query_id;
-- DROP INDEX IF EXISTS idx_api_metrics_timestamp; 