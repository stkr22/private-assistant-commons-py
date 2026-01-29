# Database Migrations

This directory contains SQL migration scripts for the Private Assistant Commons database schema.

## Migration Files

### 001_add_skill_help_text_and_intents.sql

**Purpose:** Adds skill help text and intent tracking capabilities

**Changes:**
- Adds `help_text` column to `skills` table (TEXT, nullable)
- Creates `skill_intents` junction table linking skills to intent patterns
- Adds indexes on foreign key columns for query performance
- Ensures unique skill-intent combinations via constraint

**Rollback:** Use `001_add_skill_help_text_and_intents_rollback.sql`

### 002_add_is_regex_remove_hints.sql

**Purpose:** Add regex support to keywords and remove hints table

**Changes:**
- Adds `is_regex` column to `intent_pattern_keywords` table (BOOLEAN, default FALSE)
- Adds index on `is_regex` column for query performance
- Drops `intent_pattern_hints` table completely (CASCADE)

**Rollback:** Use `002_add_is_regex_remove_hints_rollback.sql`

**Warning:** Rollback recreates hints table structure but cannot restore data

## Applying Migrations

### Manual Application

Connect to your PostgreSQL database and run:

```bash
psql -h localhost -U your_user -d your_database -f migrations/001_add_skill_help_text_and_intents.sql
```

### Using Python (psycopg)

```python
from pathlib import Path
import asyncpg

async def apply_migration():
    conn = await asyncpg.connect(
        host='localhost',
        user='your_user',
        password='your_password',
        database='your_database'
    )

    migration_path = Path('migrations/001_add_skill_help_text_and_intents.sql')
    migration_sql = migration_path.read_text()

    await conn.execute(migration_sql)
    await conn.close()
```

## Rolling Back Migrations

To revert a migration, run the corresponding rollback script:

```bash
psql -h localhost -U your_user -d your_database -f migrations/001_add_skill_help_text_and_intents_rollback.sql
```

## Migration Checklist

Before applying a migration to production:

- [ ] Test migration on a development database
- [ ] Verify all dependent applications are updated
- [ ] Back up production database
- [ ] Apply migration during maintenance window
- [ ] Verify application functionality
- [ ] Keep rollback script ready

## Notes

- All migrations use `IF NOT EXISTS` / `IF EXISTS` for idempotency
- Foreign keys include `ON DELETE CASCADE` for automatic cleanup
- UUIDs are generated using PostgreSQL's `gen_random_uuid()`
- Timestamps use `TIMESTAMP WITHOUT TIME ZONE` for consistency
