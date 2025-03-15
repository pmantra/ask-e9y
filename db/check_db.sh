#!/bin/bash

# Script to check database setup for query caching

# Get container name/ID for the database
DB_CONTAINER=$(docker ps --filter "name=db" --format "{{.Names}}")
APP_CONTAINER=$(docker ps --filter "name=app" --format "{{.Names}}")

if [ -z "$DB_CONTAINER" ]; then
  echo "Error: PostgreSQL container not found"
  exit 1
fi

echo "Found PostgreSQL container: $DB_CONTAINER"
echo "Found App container: $APP_CONTAINER"

echo "========== PostgreSQL Query Cache =========="
# Check if query_cache table exists
echo "Checking for query_cache table..."
docker exec -it $DB_CONTAINER psql -U postgres -d ask_e9y_db -c "
SELECT EXISTS (
   SELECT FROM information_schema.tables
   WHERE table_schema = 'eligibility'
   AND table_name = 'query_cache'
);"

# Check alembic version
echo "Checking Alembic version..."
docker exec -it $DB_CONTAINER psql -U postgres -d ask_e9y_db -c "
SELECT version_num FROM alembic_version;"

# List columns in query_cache table
echo "Listing columns in query_cache table..."
docker exec -it $DB_CONTAINER psql -U postgres -d ask_e9y_db -c "
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'eligibility'
AND table_name = 'query_cache'
ORDER BY ordinal_position;"

# Count records in query_cache
echo "Counting records in query_cache..."
docker exec -it $DB_CONTAINER psql -U postgres -d ask_e9y_db -c "
SELECT COUNT(*) FROM eligibility.query_cache;"

echo "========== ChromaDB Status =========="
# Check if ChromaDB directory exists and has content
echo "Checking ChromaDB directory..."
docker exec -it $APP_CONTAINER ls -la /app/chroma_db

# Check ChromaDB collection info..."
echo "Checking ChromaDB collection info..."
docker exec -it $APP_CONTAINER python -c "
import os
import json
try:
    chroma_dir = '/app/chroma_db'
    if os.path.exists(chroma_dir):
        print(f'ChromaDB directory exists: {os.path.exists(chroma_dir)}')
        collections_dir = os.path.join(chroma_dir, 'collections')
        if os.path.exists(collections_dir):
            collections = os.listdir(collections_dir)
            print(f'Collections found: {collections}')
            for collection in collections:
                coll_path = os.path.join(collections_dir, collection)
                if os.path.isdir(coll_path):
                    metadata_path = os.path.join(coll_path, 'metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                            print(f'Collection {collection} metadata: {metadata}')
        else:
            print('No collections directory found - ChromaDB may be using SQLite storage')
            sqlite_path = os.path.join(chroma_dir, 'chroma.sqlite3')
            if os.path.exists(sqlite_path):
                print(f'Found SQLite storage: {sqlite_path} (size: {os.path.getsize(sqlite_path)/1024:.1f} KB)')
except Exception as e:
    print(f'Error checking ChromaDB: {str(e)}')
"