-- Migration: Add query history table
-- This table will store the history of queries made through the system

BEGIN;

-- Create query_history table
CREATE TABLE IF NOT EXISTS eligibility.query_history (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    execution_success BOOLEAN NOT NULL,
    execution_time_ms FLOAT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_feedback TEXT,
    result_count INTEGER
);

-- Create index for faster searches
CREATE INDEX IF NOT EXISTS idx_query_history_timestamp
ON eligibility.query_history (timestamp);

COMMIT;

-- Rollback:
-- DROP TABLE IF EXISTS eligibility.query_history;
-- DROP INDEX IF EXISTS idx_query_history_timestamp;