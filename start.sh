#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready with full schema..."
max_retries=30
counter=0
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "postgres" -d "ask_e9y_db" -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='eligibility';" >/dev/null 2>&1; do
  counter=$((counter+1))
  if [ $counter -ge $max_retries ]; then
    echo "Timed out waiting for database schema. Starting anyway..."
    break
  fi
  echo "Database schema not ready yet - waiting... ($counter/$max_retries)"
  sleep 3
done

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload