#!/bin/bash
set -e

echo "Waiting for PostgreSQL to be ready..."
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "db" -U "postgres" -d "ask_e9y_db" -c '\q'; do
  echo "PostgreSQL is unavailable - sleeping"
  sleep 1
done

echo "PostgreSQL is up - starting app"
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload