#!/bin/bash
# Script to apply Alembic migrations locally

set -e  # Exit on any error

# Check if alembic is installed
if ! command -v alembic &> /dev/null; then
    echo "Error: alembic is not installed. Please install it first."
    echo "Run: pip install alembic"
    exit 1
fi

# Check environment - Docker or local
DOCKER_RUNNING=$(docker ps | grep -c "ask-e9y_db" || echo "0")

if [ "$DOCKER_RUNNING" -gt 0 ]; then
    echo "Detected Docker environment"
    DB_HOST="db"
    # Create a temporary alembic.ini with Docker connection
    cp alembic.ini alembic.docker.ini
    ALEMBIC_CONFIG="alembic.docker.ini"
else
    echo "Using local PostgreSQL"
    DB_HOST="localhost"
    # Create a temporary alembic.ini with local connection
    cp alembic.ini alembic.local.ini
    sed -i.bak "s|postgresql://postgres:postgres@db:5432/ask_e9y_db|postgresql://postgres:postgres@localhost:5432/ask_e9y_db|g" alembic.local.ini
    ALEMBIC_CONFIG="alembic.local.ini"
fi

echo "Using database host: $DB_HOST"

# Check if we're using local PostgreSQL and verify connection
if [ "$DB_HOST" = "localhost" ]; then
    if ! PGPASSWORD=postgres psql -h localhost -U postgres -c "SELECT 1" &>/dev/null; then
        echo "Error: Could not connect to the local PostgreSQL. Make sure PostgreSQL is running."
        echo "You can start the database with: docker-compose up -d db"
        exit 1
    fi
    
    # Check if database exists
    if ! PGPASSWORD=postgres psql -h localhost -U postgres -lqt | cut -d \| -f 1 | grep -qw ask_e9y_db; then
        echo "Database 'ask_e9y_db' does not exist."
        read -p "Would you like to create it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Creating database..."
            PGPASSWORD=postgres createdb -h localhost -U postgres ask_e9y_db
            echo "Database created."
        else
            rm "$ALEMBIC_CONFIG"* 2>/dev/null || true
            exit 1
        fi
    fi
fi

# Check if eligibility schema exists
if [ "$DB_HOST" = "localhost" ]; then
    if ! PGPASSWORD=postgres psql -h localhost -U postgres -d ask_e9y_db -c "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'eligibility'" | grep -q eligibility; then
        echo "Schema 'eligibility' does not exist."
        read -p "Would you like to create it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "Creating schema..."
            PGPASSWORD=postgres psql -h localhost -U postgres -d ask_e9y_db -c "CREATE SCHEMA eligibility"
            echo "Schema created."
        fi
    fi
fi

# Check current version
echo "Current migration version:"
alembic -c "$ALEMBIC_CONFIG" current

# Get list of migrations
echo "---------------------------------------------------------"
echo "Available migrations:"
alembic -c "$ALEMBIC_CONFIG" history

# Apply migrations
echo "---------------------------------------------------------"
echo "Applying all migrations to head..."
alembic -c "$ALEMBIC_CONFIG" upgrade head

# Verify success
echo "---------------------------------------------------------"
echo "Current migration version after upgrade:"
alembic -c "$ALEMBIC_CONFIG" current

# Clean up temporary files
rm "$ALEMBIC_CONFIG"* 2>/dev/null || true

echo "---------------------------------------------------------"
echo "Migrations applied successfully!" 