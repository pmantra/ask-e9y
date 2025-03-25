#!/bin/bash
# Script to prepare and apply migrations by SSHing into the Railway API container

set -e  # Exit on any error

# Get the absolute path to the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." &> /dev/null && pwd )"
MIGRATIONS_DIR="$PROJECT_ROOT/db/migrations"
COMBINED_SQL="$SCRIPT_DIR/combined_migrations.sql"

# Print header
echo "==== Railway API Container Migration Tool ===="
echo "Script location: $SCRIPT_DIR"
echo "Migrations directory: $MIGRATIONS_DIR"
echo "Combined SQL file will be created at: $COMBINED_SQL"
echo "=============================================="

# Check if the migrations directory exists
if [ ! -d "$MIGRATIONS_DIR" ]; then
    echo "Error: Migrations directory not found at $MIGRATIONS_DIR"
    exit 1
fi

# Check if the railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Error: railway CLI is not installed. Please install it first."
    echo "You can install it using npm: npm install -g @railway/cli"
    echo "Or see documentation at: https://docs.railway.app/develop/cli"
    exit 1
fi

# Create the combined migrations file
echo "Creating combined migrations file..."

# Start with transaction and extension setup
cat > "$COMBINED_SQL" << 'EOF'
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

EOF

# Get all migration files sorted by name
migration_files=$(find "$MIGRATIONS_DIR" -name "*.sql" -type f | sort)

# Check if we found any migration files
if [ -z "$migration_files" ]; then
    echo "Error: No migration files found in $MIGRATIONS_DIR"
    rm "$COMBINED_SQL"
    exit 1
fi

# Process each migration file
for file in $migration_files; do
    filename=$(basename "$file")
    echo "Adding migration: $filename"
    
    # Add file header comment
    echo "-- Migration: $filename" >> "$COMBINED_SQL"
    echo "" >> "$COMBINED_SQL"
    
    # Special handling for specific migrations
    if [[ "$filename" == *"add_schema_metadata.sql" ]]; then
        # Handle schema_metadata inserts with special care for NULL values
        cat > "$COMBINED_SQL.temp" << 'EOF'
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
EOF
        cat "$COMBINED_SQL.temp" >> "$COMBINED_SQL"
        rm "$COMBINED_SQL.temp"
    elif [[ "$filename" == *"add_query_cache_table.sql" ]]; then
        # Conditionally create vector-related elements
        cat > "$COMBINED_SQL.temp" << 'EOF'
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
EOF
        cat "$COMBINED_SQL.temp" >> "$COMBINED_SQL"
        rm "$COMBINED_SQL.temp"
    else
        # Add file contents (skip any transaction statements)
        cat "$file" | grep -v "BEGIN;" | grep -v "COMMIT;" >> "$COMBINED_SQL"
    fi
    
    # Add separator
    echo "" >> "$COMBINED_SQL"
    echo "" >> "$COMBINED_SQL"
done

# Finish with commit
cat >> "$COMBINED_SQL" << 'EOF'
-- Commit the transaction
COMMIT;

-- Verify migrations were applied
SELECT 'Migrations completed successfully!' as result;
EOF

echo "Combined migrations file created at: $COMBINED_SQL"
echo ""

# Ask if the user wants to apply migrations by SSHing into the API container
read -p "Do you want to apply migrations through the Railway API container? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Applying migrations via SSH to the API container..."
    echo "Note: You'll need to be logged in and linked to your Railway project."
    
    # Get all services
    services=$(railway service list)
    
    # Check if we have an API service
    if echo "$services" | grep -q "api"; then
        echo "API service found. Attempting to SSH into the container..."
        
        # Create a temporary file to store remote execution script
        temp_script=$(mktemp)
        cat > "$temp_script" << 'REMOTE_EOF'
#!/bin/bash
# Check if we have psql installed
if ! command -v psql &> /dev/null; then
    echo "Error: psql is not available in the container"
    exit 1
fi

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "Error: DATABASE_URL is not set in the container"
    exit 1
fi

# Create a temp file for the SQL
sql_file=$(mktemp)

# Receive the SQL content from stdin
cat > "$sql_file"

# Run the SQL
echo "Applying migrations..."
psql "$DATABASE_URL" -f "$sql_file"

# Clean up
rm "$sql_file"
REMOTE_EOF
        
        # Make the temp script executable
        chmod +x "$temp_script"
        
        # SSH into the API container and pipe the SQL file to the remote script
        cat "$COMBINED_SQL" | railway ssh api --command "bash -s" < "$temp_script"
        
        # Check if the command succeeded
        if [ $? -eq 0 ]; then
            echo "Migrations applied successfully!"
        else
            echo "Migration command encountered an error."
            echo "You can try applying migrations manually by:"
            echo "1. SSH into your API container: railway ssh api"
            echo "2. Apply migrations using psql with the DATABASE_URL environment variable"
        fi
        
        # Clean up the temp script
        rm "$temp_script"
    else
        echo "Error: No API service found in your Railway project."
        echo "Available services:"
        echo "$services"
        echo ""
        echo "Please try applying migrations directly with: railway connect postgres"
        echo "Then run: \i $COMBINED_SQL"
    fi
else
    echo "Migrations were not applied."
    echo ""
    echo "To apply migrations manually via Railway PostgreSQL, run:"
    echo "railway connect postgres"
    echo "Then in the psql prompt, run:"
    echo "\i $COMBINED_SQL"
    echo ""
    echo "To apply migrations via the API container, SSH into it and use psql:"
    echo "railway ssh api"
    echo "psql \$DATABASE_URL -f /path/to/migrations.sql"
fi 