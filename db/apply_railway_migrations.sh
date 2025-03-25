#!/bin/bash
# Script to apply missing migrations to the Railways PostgreSQL instance

set -e  # Exit on any error

# Check if the railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Error: railway CLI is not installed. Please install it first."
    echo "See: https://docs.railway.app/develop/cli"
    exit 1
fi

# Check if user is logged in to Railway
railway whoami &> /dev/null || {
    echo "You are not logged in to Railway. Please run 'railway login' first."
    exit 1
}

# Check if we have the right project
PROJECT_NAME=$(railway current)
if [ -z "$PROJECT_NAME" ]; then
    echo "No Railway project selected. Please run 'railway link' first."
    exit 1
fi

echo "Applying migrations to Railway project: $PROJECT_NAME"
echo "---------------------------------------------------------"

# Apply new migrations
apply_migration() {
    local migration_file=$1
    echo "Applying migration: $migration_file"
    
    # Create a temporary file with the migration SQL
    TMP_FILE=$(mktemp)
    cat "$migration_file" > "$TMP_FILE"
    
    # Run the migration
    railway run "psql -f $TMP_FILE"
    
    # Remove the temporary file
    rm "$TMP_FILE"
    
    echo "Applied: $migration_file"
    echo "---------------------------------------------------------"
}

# List of migrations to apply - add or remove as needed
MIGRATIONS=(
    "db/migrations/20250322_01_add_api_metrics_table.sql"
    "db/migrations/20250322_02_add_query_id_column.sql"
    "db/migrations/20250322_03_add_query_id_mappings_table.sql"
    "db/migrations/20250322_04_add_query_id_to_cache.sql"
)

# Apply each migration
for migration in "${MIGRATIONS[@]}"; do
    if [ -f "$migration" ]; then
        apply_migration "$migration"
    else
        echo "Warning: Migration file not found: $migration"
    fi
done

echo "All migrations applied successfully!" 