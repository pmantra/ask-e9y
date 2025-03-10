# Database Migrations

This directory contains SQL migration scripts that will be applied to the database in alphabetical order.

## Naming Convention

Migration files should follow this naming pattern:
```
YYYYMMDD_XX_description.sql
```

Where:
- `YYYYMMDD` is the date in year-month-day format
- `XX` is a two-digit sequence number for that day (e.g., 01, 02)
- `description` is a brief description of what the migration does

Example: `20250309_01_add_user_preferences_table.sql`

## Creating Migrations

To create a new migration:

1. Create a new SQL file following the naming convention
2. Include both the changes and any necessary rollback commands (commented out)
3. Test your migration locally before committing

Example migration file:
```sql
-- Migration: Add user preferences table
CREATE TABLE eligibility.user_preferences (
    user_id BIGINT PRIMARY KEY,
    theme TEXT DEFAULT 'light',
    language TEXT DEFAULT 'en',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Rollback:
-- DROP TABLE eligibility.user_preferences;
```

## Applying Migrations

Migrations are automatically applied when the Docker container starts if the database already exists.