/*
   WARNING: This is a reference schema only! 
   Do NOT apply this directly to a production database.
   Use Alembic migrations for schema changes:
   ./scripts/apply_local_alembic_migrations.sh (for local)
   ./scripts/apply_railway_alembic_migrations.sh (for Railways)
*/

-- Consolidated schema.sql including all migrations
-- This represents the complete database structure as of March 2025

-- Enable extensions first (must be done outside the main transaction)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS vector;

-- Start a transaction for the rest of the schema creation
BEGIN;

-- Create the eligibility schema
CREATE SCHEMA IF NOT EXISTS eligibility;

-- Create organization table
CREATE TABLE IF NOT EXISTS eligibility.organization (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create file table
CREATE TABLE IF NOT EXISTS eligibility.file (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'pending', 'processing', 'completed', 'error'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_organization FOREIGN KEY (organization_id) REFERENCES eligibility.organization(id)
);

-- Create member table
CREATE TABLE IF NOT EXISTS eligibility.member (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    file_id INTEGER,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    unique_corp_id TEXT NOT NULL,
    dependent_id TEXT NOT NULL,
    date_of_birth DATE NOT NULL,
    work_state TEXT,
    effective_range daterange,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_organization FOREIGN KEY (organization_id) REFERENCES eligibility.organization(id),
    CONSTRAINT fk_file FOREIGN KEY (file_id) REFERENCES eligibility.file(id)
);

-- Create verification table
CREATE TABLE IF NOT EXISTS eligibility.verification (
    id SERIAL PRIMARY KEY,
    member_id INTEGER,  -- Can be NULL if verification is created before member record
    organization_id INTEGER NOT NULL,
    unique_corp_id TEXT NOT NULL,
    dependent_id TEXT NOT NULL,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL,
    date_of_birth DATE,
    work_state TEXT,
    verification_type TEXT NOT NULL,  -- e.g., 'email', 'document', 'id'
    verified_at TIMESTAMP WITH TIME ZONE,
    deactivated_at TIMESTAMP WITH TIME ZONE,
    additional_fields JSONB,  -- For any custom verification data
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_organization FOREIGN KEY (organization_id) REFERENCES eligibility.organization(id),
    CONSTRAINT fk_member FOREIGN KEY (member_id) REFERENCES eligibility.member(id)
);

-- Create verification_attempt table
CREATE TABLE IF NOT EXISTS eligibility.verification_attempt (
    id SERIAL PRIMARY KEY,
    verification_id INTEGER NOT NULL,
    organization_id INTEGER NOT NULL,
    unique_corp_id TEXT,
    dependent_id TEXT,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    date_of_birth DATE,
    work_state TEXT,
    verification_type TEXT NOT NULL,
    successful_verification BOOLEAN,
    verified_at TIMESTAMP WITH TIME ZONE,
    additional_fields JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_verification FOREIGN KEY (verification_id) REFERENCES eligibility.verification(id),
    CONSTRAINT fk_organization FOREIGN KEY (organization_id) REFERENCES eligibility.organization(id)
);

-- Create member_verification join table
CREATE TABLE IF NOT EXISTS eligibility.member_verification (
    id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL,
    verification_id INTEGER NOT NULL,
    verification_attempt_id INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_member FOREIGN KEY (member_id) REFERENCES eligibility.member(id) ON DELETE CASCADE,
    CONSTRAINT fk_verification FOREIGN KEY (verification_id) REFERENCES eligibility.verification(id) ON DELETE CASCADE,
    CONSTRAINT fk_verification_attempt FOREIGN KEY (verification_attempt_id) REFERENCES eligibility.verification_attempt(id) ON DELETE CASCADE
);

-- Create schema metadata table for chatbot
CREATE TABLE IF NOT EXISTS eligibility.schema_metadata (
    table_name TEXT,
    column_name TEXT,
    description TEXT,
    example_value TEXT,
    PRIMARY KEY (table_name, column_name)
);

-- Create query templates table for chatbot
CREATE TABLE IF NOT EXISTS eligibility.query_templates (
    id SERIAL PRIMARY KEY,
    natural_language_pattern TEXT,
    sql_template TEXT,
    last_used TIMESTAMP WITH TIME ZONE,
    success_count INTEGER DEFAULT 0
);

-- Create query_history table (from migration 20250309_01_add_query_history_table.sql)
CREATE TABLE IF NOT EXISTS eligibility.query_history (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    execution_success BOOLEAN NOT NULL,
    execution_time_ms FLOAT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_feedback TEXT,
    result_count INTEGER,
    query_id TEXT
);

-- Create query_cache table (from migration 20250312_01_add_query_cache_table.sql)
CREATE TABLE IF NOT EXISTS eligibility.query_cache (
    id SERIAL PRIMARY KEY,
    natural_query TEXT NOT NULL,
    generated_sql TEXT NOT NULL,
    explanation TEXT,
    execution_count INTEGER DEFAULT 1,
    last_used TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms FLOAT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    query_id TEXT,
    CONSTRAINT unique_natural_query UNIQUE (natural_query)
);

-- Handle the vector column separately to ensure vector extension is available
DO $$
BEGIN
    -- Check if vector extension exists and is installed
    IF EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'vector'
    ) THEN
        -- Add vector column if not already present
        IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'eligibility'
            AND table_name = 'query_cache'
            AND column_name = 'query_embedding'
        ) THEN
            ALTER TABLE eligibility.query_cache ADD COLUMN query_embedding VECTOR(1536);

            -- Create vector index (this might fail if the vector extension isn't properly available)
            BEGIN
                EXECUTE 'CREATE INDEX IF NOT EXISTS idx_query_cache_embedding
                ON eligibility.query_cache USING ivfflat (query_embedding vector_cosine_ops)
                WITH (lists = 100)';
                RAISE NOTICE 'Vector index created successfully';
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'Could not create vector index: %', SQLERRM;
            END;
        END IF;
    ELSE
        RAISE NOTICE 'Vector extension not available - skipping vector column creation';
    END IF;
END
$$;

-- Create query_id_mappings table
CREATE TABLE IF NOT EXISTS eligibility.query_id_mappings (
    new_query_id TEXT PRIMARY KEY,
    original_query_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create materialized view for active verified members
CREATE MATERIALIZED VIEW IF NOT EXISTS eligibility.active_verified_members AS
SELECT
    m.id,
    m.organization_id,
    m.first_name,
    m.last_name,
    m.email,
    m.unique_corp_id,
    m.dependent_id,
    m.date_of_birth,
    m.work_state,
    CASE
        WHEN v.id IS NOT NULL AND v.verified_at IS NOT NULL
        THEN true
        ELSE false
    END AS is_verified
FROM
    eligibility.member m
LEFT JOIN
    eligibility.member_verification mv ON m.id = mv.member_id
LEFT JOIN
    eligibility.verification v ON mv.verification_id = v.id
WHERE
    (m.effective_range @> CURRENT_DATE)
WITH DATA;

-- Create view for member details with verification status
DROP VIEW IF EXISTS eligibility.member_details;
CREATE VIEW eligibility.member_details AS
SELECT
    m.id,
    m.organization_id,
    m.first_name,
    m.last_name,
    m.email,
    m.unique_corp_id,
    m.dependent_id,
    m.date_of_birth,
    m.work_state,
    m.effective_range,
    (m.effective_range @> CURRENT_DATE) AS is_active,
    (SELECT COUNT(*) > 0 FROM eligibility.member_verification mv
     JOIN eligibility.verification v ON mv.verification_id = v.id
     WHERE mv.member_id = m.id AND v.verified_at IS NOT NULL) AS is_verified
FROM
    eligibility.member m;

-- Create all required indexes
CREATE INDEX IF NOT EXISTS idx_member_identity ON eligibility.member (organization_id, unique_corp_id, dependent_id);
CREATE INDEX IF NOT EXISTS idx_member_name_email ON eligibility.member (organization_id, last_name, first_name, email);
CREATE INDEX IF NOT EXISTS idx_verification_member_id ON eligibility.verification (member_id);
CREATE INDEX IF NOT EXISTS idx_verification_organization_id ON eligibility.verification (organization_id);
CREATE INDEX IF NOT EXISTS idx_verification_attempt_verification_id ON eligibility.verification_attempt (verification_id);
CREATE INDEX IF NOT EXISTS idx_member_verification_member_id ON eligibility.member_verification (member_id);
CREATE INDEX IF NOT EXISTS idx_member_verification_verification_id ON eligibility.member_verification (verification_id);
CREATE INDEX IF NOT EXISTS idx_member_effective_range ON eligibility.member USING gist (effective_range);
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_verified_members_id ON eligibility.active_verified_members (id);
CREATE INDEX IF NOT EXISTS idx_query_history_timestamp ON eligibility.query_history (timestamp);
CREATE INDEX IF NOT EXISTS idx_query_cache_natural ON eligibility.query_cache (natural_query);
CREATE INDEX IF NOT EXISTS idx_query_cache_last_used ON eligibility.query_cache (last_used);
CREATE INDEX IF NOT EXISTS idx_member_name_dob ON eligibility.member (first_name, last_name, date_of_birth);
CREATE INDEX IF NOT EXISTS idx_query_id_mappings_original_id ON eligibility.query_id_mappings (original_query_id);

-- Full-text search indexes
CREATE INDEX IF NOT EXISTS idx_member_name_trgm ON eligibility.member USING gin (
    (first_name || ' ' || last_name) gin_trgm_ops
);
CREATE INDEX IF NOT EXISTS idx_member_email_trgm ON eligibility.member USING gin (
    email gin_trgm_ops
);

-- Add schema metadata for better LLM understanding
-- Use ON CONFLICT DO NOTHING to prevent duplicate key errors
INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value)
VALUES
('member', 'effective_range', 'Date range when a member is considered active. A member is active when CURRENT_DATE is contained within this range.', '[2023-01-01,)'),
('active_members', '', 'View that contains only currently active members (where current date is within effective_range)', NULL)
ON CONFLICT (table_name, column_name) DO NOTHING;

INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value)
VALUES
('file', 'id', 'Primary key for file', '1'),
('file', 'organization_id', 'Reference to organization', '1'),
('file', 'name', 'File name', 'employees_2023.csv'),
('file', 'status', 'Processing status of the file', 'completed')
ON CONFLICT (table_name, column_name) DO NOTHING;

INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value)
VALUES
('member', 'id', 'Primary key for member', '1'),
('member', 'organization_id', 'Reference to organization', '1'),
('member', 'file_id', 'Reference to file that created this record', '1'),
('member', 'first_name', 'First name of member', 'John'),
('member', 'last_name', 'Last name of member', 'Doe'),
('member', 'email', 'Email address of member', 'john.doe@example.com'),
('member', 'unique_corp_id', 'Unique corporate identifier for the employee', 'EMP12345'),
('member', 'dependent_id', 'Dependent identifier, empty for primary members', 'DEP001'),
('member', 'date_of_birth', 'Date of birth', '1980-01-01'),
('member', 'work_state', 'State where member works', 'CA'),
('member', 'effective_range', 'Date range when the member record is effective', '[2023-01-01,)')
ON CONFLICT (table_name, column_name) DO NOTHING;

INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value)
VALUES
('verification', 'id', 'Primary key for verification', '1'),
('verification', 'member_id', 'Reference to member', '1'),
('verification', 'organization_id', 'Reference to organization', '1'),
('verification', 'verification_type', 'Type of verification', 'email'),
('verification', 'verified_at', 'When verification was completed', '2023-01-15 14:30:00')
ON CONFLICT (table_name, column_name) DO NOTHING;

INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value)
VALUES
('verification_attempt', 'id', 'Primary key for verification attempt', '1'),
('verification_attempt', 'verification_id', 'Reference to verification', '1'),
('verification_attempt', 'successful_verification', 'Whether verification was successful', 'true')
ON CONFLICT (table_name, column_name) DO NOTHING;

INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value)
VALUES
('member_verification', 'id', 'Primary key for member verification', '1'),
('member_verification', 'member_id', 'Reference to member', '1'),
('member_verification', 'verification_id', 'Reference to verification', '1'),
('member_verification', 'verification_attempt_id', 'Reference to verification attempt', '1')
ON CONFLICT (table_name, column_name) DO NOTHING;

-- Add business concept metadata from migration 20250310_01_add_schema_metadata.sql
INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value)
VALUES
('member', 'effective_range', 'Date range when a member is considered active. A member is active when CURRENT_DATE is contained within this range.', '[2023-01-01,)'),
('active_members', '', 'View that contains only currently active members (where current date is within effective_range)', NULL)
ON CONFLICT (table_name, column_name) DO NOTHING;

-- Add overeligibility concept from migration ee218ec76260
INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value)
VALUES
('member', '', 'A person is considered "overeligible" if they have active member records in more than one organization with the same first name, last name, and date of birth.', '')
ON CONFLICT (table_name, column_name) DO NOTHING;

-- Add sample query templates
-- Use ON CONFLICT DO NOTHING for templates as well
INSERT INTO eligibility.query_templates (natural_language_pattern, sql_template, last_used, success_count)
VALUES
('Show me all members from {organization}',
 'SELECT * FROM eligibility.member WHERE organization_id = (SELECT id FROM eligibility.organization WHERE name ILIKE ''%{organization}%'')',
 CURRENT_TIMESTAMP, 1)
ON CONFLICT DO NOTHING;

INSERT INTO eligibility.query_templates (natural_language_pattern, sql_template, last_used, success_count)
VALUES
('Find members with email {email}',
 'SELECT * FROM eligibility.member WHERE email ILIKE ''%{email}%''',
 CURRENT_TIMESTAMP, 1)
ON CONFLICT DO NOTHING;

INSERT INTO eligibility.query_templates (natural_language_pattern, sql_template, last_used, success_count)
VALUES
('Show verification status for member {member_id}',
 'SELECT m.*, v.verification_type, v.verified_at FROM eligibility.member m LEFT JOIN eligibility.member_verification mv ON m.id = mv.member_id LEFT JOIN eligibility.verification v ON mv.verification_id = v.id WHERE m.id = {member_id}',
 CURRENT_TIMESTAMP, 1)
ON CONFLICT DO NOTHING;

-- Add overeligibility query templates from migration ee218ec76260
INSERT INTO eligibility.query_templates (natural_language_pattern, sql_template, last_used, success_count)
VALUES
('Show me all overeligible members',
 'SELECT m.first_name, m.last_name, m.date_of_birth, COUNT(DISTINCT m.organization_id) as org_count, array_agg(DISTINCT o.name) as organizations FROM eligibility.member m JOIN eligibility.organization o ON m.organization_id = o.id WHERE m.effective_range @> CURRENT_DATE GROUP BY m.first_name, m.last_name, m.date_of_birth HAVING COUNT(DISTINCT m.organization_id) > 1',
 CURRENT_TIMESTAMP, 1)
ON CONFLICT DO NOTHING;

INSERT INTO eligibility.query_templates (natural_language_pattern, sql_template, last_used, success_count)
VALUES
('Is {first_name} {last_name} overeligible',
 'SELECT COUNT(DISTINCT organization_id) > 1 as is_overeligible FROM eligibility.member WHERE first_name ILIKE ''{first_name}'' AND last_name ILIKE ''{last_name}'' AND effective_range @> CURRENT_DATE',
 CURRENT_TIMESTAMP, 1)
ON CONFLICT DO NOTHING;

INSERT INTO eligibility.query_templates (natural_language_pattern, sql_template, last_used, success_count)
VALUES
('Check if member with ID {member_id} is overeligible',
 'WITH member_identity AS (SELECT first_name, last_name, date_of_birth FROM eligibility.member WHERE id = {member_id}) SELECT COUNT(DISTINCT m.organization_id) > 1 as is_overeligible FROM eligibility.member m JOIN member_identity mi ON m.first_name = mi.first_name AND m.last_name = mi.last_name AND m.date_of_birth = mi.date_of_birth WHERE m.effective_range @> CURRENT_DATE',
 CURRENT_TIMESTAMP, 1)
ON CONFLICT DO NOTHING;

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

CREATE INDEX IF NOT EXISTS idx_api_metrics_query_id ON eligibility.api_metrics (query_id);
CREATE INDEX IF NOT EXISTS idx_api_metrics_timestamp ON eligibility.api_metrics (timestamp);

-- Commit the transaction
COMMIT;