#!/bin/bash
# Script to check the database status on Railway PostgreSQL

set -e  # Exit on any error

echo "==== Railway Database Status Check ===="

# Check if the railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Error: railway CLI is not installed. Please install it first."
    echo "You can install it using npm: npm install -g @railway/cli"
    exit 1
fi

# Check if we're logged in and linked to a project
echo "Checking Railway connection..."
if ! railway whoami &> /dev/null; then
    echo "You are not logged in to Railway. Please run: railway login"
    exit 1
fi

if ! railway status &> /dev/null; then
    echo "You are not linked to a Railway project. Please run: railway link"
    exit 1
fi

# Create temporary SQL script
temp_sql=$(mktemp)
cat > "$temp_sql" << 'EOF'
-- Check all eligibility tables and their row counts
SELECT 
    table_schema,
    table_name,
    pg_size_pretty(pg_total_relation_size(quote_ident(table_schema) || '.' || quote_ident(table_name))) as size,
    (SELECT COUNT(*) FROM eligibility."' || table_name || '") as row_count
FROM information_schema.tables
WHERE table_schema = 'eligibility'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- Check installed extensions
SELECT name, default_version, installed_version, comment 
FROM pg_available_extensions 
WHERE installed_version IS NOT NULL
ORDER BY name;

-- Check database size
SELECT pg_size_pretty(pg_database_size(current_database())) as database_size;
EOF

echo ""
echo "Connecting to Railway PostgreSQL to check status..."
echo ""

# Run the status check using railway CLI
if ! railway run "psql -f $temp_sql" 2>/dev/null; then
    echo "Error: Could not connect to Railway PostgreSQL instance."
    echo "Trying alternative method..."
    
    # Try using railway connect 
    echo ""
    echo "Please run the following command to check database status:"
    echo "railway connect postgres"
    echo ""
    echo "Then paste the following SQL commands at the psql prompt:"
    echo ""
    cat "$temp_sql"
fi

# Clean up
rm "$temp_sql"

echo ""
echo "Status check complete!" 