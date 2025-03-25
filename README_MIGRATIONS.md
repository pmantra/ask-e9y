# Database Migration Guide

This guide explains how to apply migrations to your PostgreSQL database both locally and on Railway.

## Migration Scripts

We provide the following scripts for managing database migrations:

1. **Railway Migrations (Recommended)**:
   - `scripts/apply_railway_api_migrations.sh` - Apply migrations via the API container
   - `scripts/apply_railway_migrations.sh` - Apply migrations directly to PostgreSQL
   - `scripts/check_railway_db_status.sh` - Verify migration status

2. **Local Development**:
   - `apply_local_alembic_migrations.sh` - Apply Alembic migrations locally

## Migration Files

The SQL migrations are located in `db/migrations/` and are organized by date:

1. `20250309_01_add_query_history_table.sql` - Adds query history tracking
2. `20250310_01_add_schema_metadata.sql` - Adds schema metadata
3. `20250312_01_add_query_cache_table.sql` - Adds query caching
4. `20250322_01_add_api_metrics_table.sql` - Adds API metrics
5. `20250322_02_add_query_id_column.sql` - Adds query ID tracking
6. `20250322_03_add_query_id_mappings_table.sql` - Adds query ID mappings
7. `20250322_04_add_query_id_to_cache.sql` - Adds query ID to cache

## Prerequisites

Before running migrations, ensure you have:

1. **Railway CLI** (for Railway deployment):
   ```
   npm install -g @railway/cli
   ```

2. **PostgreSQL Client**:
   ```
   # MacOS
   brew install postgresql
   
   # Ubuntu/Debian
   apt-get install postgresql-client
   ```

3. **Authentication** (for Railway):
   ```
   railway login
   railway link
   ```

## Applying Migrations

### For Railway (Production)

#### Method 1: Using the API Container (Recommended)

The most reliable approach is to run migrations from within the API container:

```bash
./scripts/apply_railway_api_migrations.sh
```

This method:
- Uses the same database connection as your application
- Handles authentication automatically
- Applies all migrations in a single transaction
- Provides detailed feedback

#### Method 2: Direct PostgreSQL Connection

If you prefer connecting directly to the database:

```bash
./scripts/apply_railway_migrations.sh
```

#### Method 3: Manual Connection

For complete control, connect manually:

```bash
railway connect postgres
\i scripts/combined_migrations.sql
```

### For Local Development

Apply migrations to your local database using:

```bash
./scripts/apply_local_alembic_migrations.sh
```

## Verifying Migrations

After applying migrations, check the status with:

```bash
./scripts/check_railway_db_status.sh
```

This shows:
- All tables and their row counts
- Installed extensions
- Total database size

## Migration Design

Our migrations follow these principles:

1. **Idempotent**: Can be applied multiple times without error
2. **Transactional**: Run in a transaction for atomicity
3. **Sequential**: Applied in chronological order
4. **Independent**: Each focuses on a specific change

## Special Handling

The migration scripts include special handling for:

1. **Missing extensions**: If the vector extension isn't available, the script creates alternative table structures without vector support
2. **Duplicate keys**: Uses ON CONFLICT clauses to prevent errors on repeated runs
3. **Table existence**: Uses IF NOT EXISTS to prevent errors

## Troubleshooting

### Connection Issues

If you can't connect to Railway:

1. Verify login status:
   ```
   railway whoami
   ```

2. Check project linking:
   ```
   railway status
   ```

3. Try connecting directly:
   ```
   railway connect postgres
   ```

### API Container Issues

If the API container approach fails:

1. SSH manually:
   ```
   railway ssh api
   ```

2. Check if psql is available:
   ```
   psql --version
   ```

3. Verify the DATABASE_URL:
   ```
   echo $DATABASE_URL
   ```

4. Apply migrations directly:
   ```
   psql $DATABASE_URL -f combined_migrations.sql
   ```

### Local Database Issues

For local database problems:

1. Ensure PostgreSQL is running:
   ```
   pg_isready
   ```

2. Check connection details in your `.env` file
3. Try connecting manually:
   ```
   psql -h localhost -U your_username -d your_database
   ```

## Support

If you need assistance:

1. Capture the specific error message
2. Note the output of `railway status` (for Railway issues)
3. List the steps you've already tried
4. Include database status from `check_railway_db_status.sh`

Contact the development team with this information. 