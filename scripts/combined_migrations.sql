-- Combined migrations file generated on $(date)
-- Extensions must be created outside a transaction
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create schema if it doesn't exist
CREATE SCHEMA IF NOT EXISTS eligibility;

-- Create schema_metadata table if it doesn't exist
CREATE TABLE IF NOT EXISTS eligibility.schema_metadata (
    table_name TEXT,
    column_name TEXT NOT NULL,
    description TEXT,
    example_value TEXT,
    PRIMARY KEY (table_name, column_name)
);

-- Conditionally create vector extension (only if available)
DO $$
BEGIN
    -- Check if vector extension exists on the system
    IF EXISTS (
        SELECT 1 FROM pg_available_extensions WHERE name = 'vector'
    ) THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS vector';
    ELSE
        RAISE NOTICE 'Vector extension not available - skipping vector-specific features';
    END IF;
END $$;

-- Start a transaction for all migrations
BEGIN;

-- Migration: 20250309_01_add_query_history_table.sql

-- Migration: Add query history table
-- This table will store the history of queries made through the system


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


-- Rollback:
-- DROP TABLE IF EXISTS eligibility.query_history;
-- DROP INDEX IF EXISTS idx_query_history_timestamp;


-- Migration: 20250310_01_add_schema_metadata.sql

-- Add schema metadata to help the LLM understand our database structure better

-- Insert metadata records with detailed information about tables and columns
INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value) VALUES
('member', 'effective_range', 'Date range when a member is considered active. A member is active when CURRENT_DATE is contained within this range.', '[2023-01-01,)'),
('member', 'organization_id', 'Reference to the organization the member belongs to', '1'),
('organization', 'name', 'Name of the organization', 'ACME Corporation'),
('organization', 'id', 'Unique identifier for the organization', '1')
ON CONFLICT (table_name, column_name) DO NOTHING;

-- Create a view for active members to simplify queries
CREATE OR REPLACE VIEW eligibility.active_members AS
SELECT m.*
FROM eligibility.member m
WHERE m.effective_range @> CURRENT_DATE;

-- Add documentation for the view (using empty string instead of NULL)
INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value) VALUES
('active_members', '', 'View that contains only currently active members (where current date is within effective_range)', NULL)
ON CONFLICT (table_name, column_name) DO NOTHING;


-- Migration: 20250312_01_add_query_cache_table.sql

-- Conditionally handle vector-related operations
DO $$
BEGIN
    -- Check if vector extension exists
    IF EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'vector'
    ) THEN
        -- Create query cache table with vector support
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'eligibility' AND table_name = 'query_cache'
        ) THEN
            CREATE TABLE eligibility.query_cache (
                id SERIAL PRIMARY KEY,
                natural_query TEXT NOT NULL,
                query_embedding VECTOR(1536),
                generated_sql TEXT NOT NULL,
                explanation TEXT,
                execution_count INTEGER DEFAULT 1,
                last_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms FLOAT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Create vector similarity index
            EXECUTE 'CREATE INDEX idx_query_cache_embedding ON eligibility.query_cache
            USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100)';
        END IF;
    ELSE
        -- Create query cache table without vector support
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'eligibility' AND table_name = 'query_cache'
        ) THEN
            CREATE TABLE eligibility.query_cache (
                id SERIAL PRIMARY KEY,
                natural_query TEXT NOT NULL,
                generated_sql TEXT NOT NULL,
                explanation TEXT,
                execution_count INTEGER DEFAULT 1,
                last_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms FLOAT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        END IF;
    END IF;
    
    -- Create text lookup index for exact matches
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE schemaname = 'eligibility' AND tablename = 'query_cache' AND indexname = 'idx_query_cache_natural'
    ) THEN
        CREATE INDEX idx_query_cache_natural ON eligibility.query_cache (natural_query);
    END IF;
END $$;


-- Migration: 20250322_01_add_api_metrics_table.sql

-- Migration: Add API metrics table
-- This table will store metrics about API usage and performance


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


-- Rollback:
-- DROP TABLE IF EXISTS eligibility.api_metrics;
-- DROP INDEX IF EXISTS idx_api_metrics_query_id;
-- DROP INDEX IF EXISTS idx_api_metrics_timestamp; 


-- Migration: 20250322_02_add_query_id_column.sql

-- Migration: Add query_id column to query_history table
-- This column will store a reference to the query id for linking with other tables


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


-- Rollback:
-- ALTER TABLE eligibility.query_history DROP COLUMN IF EXISTS query_id; 


-- Migration: 20250322_03_add_query_id_mappings_table.sql

-- Migration: Add query_id_mappings table
-- This table will store mappings between original and new query IDs for tracking related queries


-- Create query_id_mappings table
CREATE TABLE IF NOT EXISTS eligibility.query_id_mappings (
    new_query_id TEXT PRIMARY KEY,
    original_query_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create index for faster lookups by original query ID
CREATE INDEX IF NOT EXISTS idx_query_id_mappings_original_id 
ON eligibility.query_id_mappings (original_query_id);


-- Rollback:
-- DROP TABLE IF EXISTS eligibility.query_id_mappings;
-- DROP INDEX IF EXISTS idx_query_id_mappings_original_id; 


-- Migration: 20250322_04_add_query_id_to_cache.sql

-- Migration: Add query_id column to query_cache table
-- This column will store a reference to the query id for linking with other tables


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


-- Rollback:
-- ALTER TABLE eligibility.query_cache DROP CONSTRAINT IF EXISTS unique_natural_query;
-- ALTER TABLE eligibility.query_cache DROP COLUMN IF EXISTS query_id;
-- DROP INDEX IF EXISTS idx_query_cache_last_used; 


-- Commit the transaction
COMMIT;

-- Verify migrations were applied
SELECT 'Migrations completed successfully!' as result;
