-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create query cache table
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
CREATE INDEX idx_query_cache_embedding ON eligibility.query_cache
USING ivfflat (query_embedding vector_cosine_ops) WITH (lists = 100);

-- Create text lookup index for exact matches
CREATE INDEX idx_query_cache_natural ON eligibility.query_cache (natural_query);