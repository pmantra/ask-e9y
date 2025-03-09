-- Create the eligibility schema
CREATE SCHEMA IF NOT EXISTS eligibility;

-- Enable text search capabilities
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create organization table
CREATE TABLE eligibility.organization (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create file table
CREATE TABLE eligibility.file (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,  -- 'pending', 'processing', 'completed', 'error'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_organization FOREIGN KEY (organization_id) REFERENCES eligibility.organization(id)
);

-- Create member table
CREATE TABLE eligibility.member (
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
CREATE TABLE eligibility.verification (
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
CREATE TABLE eligibility.verification_attempt (
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
CREATE TABLE eligibility.member_verification (
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
CREATE TABLE eligibility.schema_metadata (
    table_name TEXT,
    column_name TEXT,
    description TEXT,
    example_value TEXT,
    PRIMARY KEY (table_name, column_name)
);

-- Create query templates table for chatbot
CREATE TABLE eligibility.query_templates (
    id SERIAL PRIMARY KEY,
    natural_language_pattern TEXT,
    sql_template TEXT,
    last_used TIMESTAMP WITH TIME ZONE,
    success_count INTEGER DEFAULT 0
);

-- Create materialized view for active verified members
CREATE MATERIALIZED VIEW eligibility.active_verified_members AS
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

-- Create indexes
CREATE INDEX idx_member_identity ON eligibility.member (organization_id, unique_corp_id, dependent_id);
CREATE INDEX idx_member_name_email ON eligibility.member (organization_id, last_name, first_name, email);
CREATE INDEX idx_verification_member_id ON eligibility.verification (member_id);
CREATE INDEX idx_verification_organization_id ON eligibility.verification (organization_id);
CREATE INDEX idx_verification_attempt_verification_id ON eligibility.verification_attempt (verification_id);
CREATE INDEX idx_member_verification_member_id ON eligibility.member_verification (member_id);
CREATE INDEX idx_member_verification_verification_id ON eligibility.member_verification (verification_id);
CREATE INDEX idx_member_effective_range ON eligibility.member USING gist (effective_range);
CREATE UNIQUE INDEX idx_active_verified_members_id ON eligibility.active_verified_members (id);

-- Full-text search indexes
CREATE INDEX idx_member_name_trgm ON eligibility.member USING gin (
    (first_name || ' ' || last_name) gin_trgm_ops
);
CREATE INDEX idx_member_email_trgm ON eligibility.member USING gin (
    email gin_trgm_ops
);

-- Add schema metadata for better LLM understanding
INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value) VALUES
('organization', 'id', 'Primary key for organization', '1'),
('organization', 'name', 'Name of the organization', 'ACME Corp'),

('file', 'id', 'Primary key for file', '1'),
('file', 'organization_id', 'Reference to organization', '1'),
('file', 'name', 'File name', 'employees_2023.csv'),
('file', 'status', 'Processing status of the file', 'completed'),

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
('member', 'effective_range', 'Date range when the member record is effective', '[2023-01-01,)'),

('verification', 'id', 'Primary key for verification', '1'),
('verification', 'member_id', 'Reference to member', '1'),
('verification', 'organization_id', 'Reference to organization', '1'),
('verification', 'verification_type', 'Type of verification', 'email'),
('verification', 'verified_at', 'When verification was completed', '2023-01-15 14:30:00'),

('verification_attempt', 'id', 'Primary key for verification attempt', '1'),
('verification_attempt', 'verification_id', 'Reference to verification', '1'),
('verification_attempt', 'successful_verification', 'Whether verification was successful', 'true'),

('member_verification', 'id', 'Primary key for member verification', '1'),
('member_verification', 'member_id', 'Reference to member', '1'),
('member_verification', 'verification_id', 'Reference to verification', '1'),
('member_verification', 'verification_attempt_id', 'Reference to verification attempt', '1');

-- Add sample query templates
INSERT INTO eligibility.query_templates (natural_language_pattern, sql_template, last_used, success_count) VALUES
('Show me all members from {organization}',
 'SELECT * FROM eligibility.member WHERE organization_id = (SELECT id FROM eligibility.organization WHERE name ILIKE ''%{organization}%'')',
 CURRENT_TIMESTAMP, 1),

('Find members with email {email}',
 'SELECT * FROM eligibility.member WHERE email ILIKE ''%{email}%''',
 CURRENT_TIMESTAMP, 1),

('Show verification status for member {member_id}',
 'SELECT m.*, v.verification_type, v.verified_at FROM eligibility.member m LEFT JOIN eligibility.member_verification mv ON m.id = mv.member_id LEFT JOIN eligibility.verification v ON mv.verification_id = v.id WHERE m.id = {member_id}',
 CURRENT_TIMESTAMP, 1);