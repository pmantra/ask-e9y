-- Add schema metadata to help the LLM understand our database structure better

BEGIN;

-- Insert metadata records with detailed information about tables and columns
INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value) VALUES
('member', 'effective_range', 'Date range when a member is considered active. A member is active when CURRENT_DATE is contained within this range.', '[2023-01-01,)'),
('member', 'organization_id', 'Reference to the organization the member belongs to', '1'),
('organization', 'name', 'Name of the organization', 'ACME Corporation'),
('organization', 'id', 'Unique identifier for the organization', '1');

-- Create a view for active members to simplify queries
CREATE OR REPLACE VIEW eligibility.active_members AS
SELECT m.*
FROM eligibility.member m
WHERE m.effective_range @> CURRENT_DATE;

-- Add documentation for the view
INSERT INTO eligibility.schema_metadata (table_name, column_name, description, example_value) VALUES
('active_members', NULL, 'View that contains only currently active members (where current date is within effective_range)', NULL);

COMMIT;