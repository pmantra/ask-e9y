#!/bin/bash
set -e

# Check if database exists, create if it doesn't
echo "Checking if database exists..."
DATABASE_EXISTS=$(psql -U "$POSTGRES_USER" -tAc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'")
if [ -z "$DATABASE_EXISTS" ]; then
    echo "Database $POSTGRES_DB does not exist, creating..."
    createdb -U "$POSTGRES_USER" "$POSTGRES_DB"
    echo "Database created successfully."
else
    echo "Database $POSTGRES_DB already exists."
fi

# Check if eligibility schema exists
echo "Checking if eligibility schema exists..."
SCHEMA_EXISTS=$(psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM information_schema.schemata WHERE schema_name='eligibility'")
if [ -z "$SCHEMA_EXISTS" ]; then
    echo "Eligibility schema does not exist. Creating schema and tables..."
    # Run the schema creation script
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/schema.sql

    # Run the sample data script
    psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/sample_data.sql

    echo "Schema and tables created successfully."
else
    echo "Eligibility schema already exists. Checking if we need to run migrations..."

    # Check if we have any migration scripts and run them
    if [ -d "/docker-entrypoint-initdb.d/migrations" ]; then
        echo "Running migrations..."
        for migration in /docker-entrypoint-initdb.d/migrations/*.sql; do
            if [ -f "$migration" ]; then
                echo "Applying migration: $migration"
                psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f "$migration"
            fi
        done
        echo "Migrations completed."
    else
        echo "No migrations to run."
    fi
fi

echo "Database initialization completed."