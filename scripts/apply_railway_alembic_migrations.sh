#!/bin/bash
# Script to apply Alembic migrations to the Railways PostgreSQL instance

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

echo "Applying Alembic migrations to Railway project: $PROJECT_NAME"
echo "---------------------------------------------------------"

# Create a temporary SQL file with Alembic commands
TMP_SQL=$(mktemp)

cat << EOF > "$TMP_SQL"
-- Set up Alembic version tracking if it doesn't exist
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Run migrations
EOF

# Get current migration in Railways
echo "Checking current migration status..."
CURRENT_VERSION=$(railway run "psql -t -c \"SELECT version_num FROM alembic_version LIMIT 1;\"" 2>/dev/null || echo "")
CURRENT_VERSION=$(echo "$CURRENT_VERSION" | tr -d '[:space:]')

echo "Current migration version: ${CURRENT_VERSION:-none}"

# Find the list of migrations to apply
MIGRATIONS_DIR="alembic/versions"
MIGRATIONS=()

if [ -z "$CURRENT_VERSION" ]; then
    # No migrations applied yet, get all migrations
    echo "No migrations applied yet. Will apply all migrations."
    for file in $(ls -1 "$MIGRATIONS_DIR"/*.py | sort); do
        migration_id=$(grep "revision = " "$file" | cut -d"'" -f2)
        MIGRATIONS+=("$migration_id")
    done
else
    # Find migrations after the current one
    found_current=false
    migration_chain=()
    
    # Build the migration chain
    for file in $(ls -1 "$MIGRATIONS_DIR"/*.py | sort); do
        migration_id=$(grep "revision = " "$file" | cut -d"'" -f2)
        migration_down=$(grep "down_revision = " "$file" | cut -d"'" -f2)
        
        # Skip if down_revision is None
        if [ "$migration_down" = "None" ]; then
            migration_down=""
        fi
        
        migration_chain+=("$migration_id:$migration_down")
    done
    
    # Find the migration path from current to head
    next_migration="$CURRENT_VERSION"
    while true; do
        found_next=false
        for entry in "${migration_chain[@]}"; do
            IFS=':' read -ra parts <<< "$entry"
            migration="${parts[0]}"
            down_rev="${parts[1]}"
            
            if [ "$down_rev" = "$next_migration" ]; then
                # This is the next migration
                MIGRATIONS+=("$migration")
                next_migration="$migration"
                found_next=true
                break
            fi
        done
        
        if [ "$found_next" = false ]; then
            # No more migrations in the chain
            break
        fi
    done
fi

if [ ${#MIGRATIONS[@]} -eq 0 ]; then
    echo "No new migrations to apply."
    rm "$TMP_SQL"
    exit 0
fi

echo "Migrations to apply: ${MIGRATIONS[*]}"

# For each migration, extract the SQL commands
for migration_id in "${MIGRATIONS[@]}"; do
    migration_file=$(grep -l "revision = '$migration_id'" "$MIGRATIONS_DIR"/*.py)
    
    if [ -z "$migration_file" ]; then
        echo "Error: Could not find migration file for $migration_id"
        rm "$TMP_SQL"
        exit 1
    fi
    
    echo "Processing migration: $migration_id ($(basename "$migration_file"))"
    
    # Extract SQL from the migration
    upgrade_sql=$(python3 -c "
import re, os, sys
sys.path.append('$PWD')
from alembic.script import ScriptDirectory
from alembic.config import Config
from alembic import autogenerate, operations

config = Config('alembic.ini')
script = ScriptDirectory.from_config(config)
revision = script.get_revision('$migration_id')

# Create a dummy context
class DummyContext:
    def __init__(self):
        self.dialect = operations.Operations.impl('postgresql')
        self.opts = {}
        
dummy_ctx = DummyContext()

# Get upgrade SQL
upgrade_fn = getattr(revision.module, 'upgrade')
ops = []

def add_op(op):
    ops.append(op)

# Monkey patch to capture operations
original_execute = operations.Operations.execute
def capture_execute(self, sql, *args, **kwargs):
    sql_str = str(sql)
    if isinstance(sql, str) and not sql.strip().startswith('SELECT'):
        ops.append(sql_str)
    return original_execute(self, sql, *args, **kwargs)

operations.Operations.execute = capture_execute

# Execute the upgrade function with our dummy context
operations_obj = operations.Operations(dummy_ctx)
upgrade_fn()

# Print captured operations
for op in ops:
    print(op)
")

    if [ -z "$upgrade_sql" ]; then
        echo "Warning: No SQL commands extracted from $migration_id"
        continue
    fi
    
    # Add to SQL file
    cat << EOF >> "$TMP_SQL"

-- Migration: $migration_id ($(basename "$migration_file"))
BEGIN;
$upgrade_sql

-- Update Alembic version
DELETE FROM alembic_version;
INSERT INTO alembic_version (version_num) VALUES ('$migration_id');
COMMIT;

EOF
done

# Add final message
cat << EOF >> "$TMP_SQL"
-- All migrations applied successfully
SELECT 'Migrations applied successfully!' AS result;
EOF

echo "---------------------------------------------------------"
echo "Created SQL script with migrations to apply."
echo "---------------------------------------------------------"

# Ask for confirmation
read -p "Apply these migrations to the Railways database? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migration aborted."
    rm "$TMP_SQL"
    exit 1
fi

# Apply migrations
echo "Applying migrations..."
railway run "psql -f $TMP_SQL"

# Clean up
rm "$TMP_SQL"

echo "---------------------------------------------------------"
echo "Migrations applied successfully!" 