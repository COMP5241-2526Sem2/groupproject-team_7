# SyncLearn Supabase Database Migration Scripts

This directory contains SQL migration scripts for initializing the SyncLearn database in Supabase (PostgreSQL).

## Overview

The database schema consists of the following tables:
- **courses** - Course metadata and information
- **slides** - Slide file metadata (PDFs, PPTs)
- **slide_pages** - Individual slide page content and embeddings
- **videos** - Video file metadata
- **video_transcripts** - ASR transcript segments with timestamps
- **knowledge_points** - Learning objectives and alignment between slides/videos
- **quizzes** - Quiz questions associated with knowledge points
- **quiz_attempts** - Student quiz responses and performance tracking
- **chat_messages** - Chat messages between users and AI assistant

## Migration Files

### 1. `001_init_schema.sql`
Creates the complete database schema including:
- All 9 tables with proper data types
- Primary keys (SERIAL)
- Foreign key constraints with CASCADE delete where appropriate
- UNIQUE constraints for compound keys
- TIMESTAMP WITH TIME ZONE for UTC timestamps
- DEFAULT values for common fields
- Automatic `updated_at` trigger for courses table

**Execution time:** < 1 second
**Prerequisites:** Supabase PostgreSQL database connection

### 2. `002_create_indexes.sql`
Creates 30+ indexes to optimize query performance:
- Foreign key indexes for JOIN operations
- Filtering indexes for WHERE clauses
- Sorting indexes for ORDER BY operations
- Composite indexes for common query patterns
- GIN indexes for JSONB fields
- Organized by table with detailed comments

**Execution time:** 5-10 seconds
**Prerequisites:** Schema migration (001_init_schema.sql) must be applied first

## How to Apply Migrations

### Method 1: Supabase Dashboard (Recommended)

1. **Open Supabase Console**
   - Navigate to https://supabase.com
   - Go to your project

2. **Access SQL Editor**
   - Click on **SQL Editor** in the left sidebar
   - Click **+ New Query**

3. **Copy and Paste Schema Migration**
   - Open `001_init_schema.sql`
   - Copy the entire contents
   - Paste into the SQL Editor
   - Click **Run** (or press `Ctrl+Enter`)
   - Wait for completion (should see success message)

4. **Copy and Paste Index Migration**
   - Open `002_create_indexes.sql`
   - Copy the entire contents
   - Paste into the SQL Editor
   - Click **Run**
   - Wait for completion

5. **Verify Schema**
   - Click on **Table Editor** in the left sidebar
   - You should see all 9 tables listed

### Method 2: Using psql Command Line

If you have PostgreSQL client tools installed:

```bash
# Set your Supabase connection details
export PGPASSWORD="your-database-password"

# Run schema migration
psql -h db.supabase.co \
     -U postgres \
     -d postgres \
     -f 001_init_schema.sql

# Run indexes migration
psql -h db.supabase.co \
     -U postgres \
     -d postgres \
     -f 002_create_indexes.sql
```

Replace:
- `your-database-password` with your Supabase database password
- `db.supabase.co` with your actual Supabase host

### Method 3: Using Python Script

```python
import psycopg2

# Connect to Supabase
conn = psycopg2.connect(
    host="db.supabase.co",
    database="postgres",
    user="postgres",
    password="your-database-password"
)

cursor = conn.cursor()

# Read and execute schema migration
with open('001_init_schema.sql', 'r') as f:
    cursor.execute(f.read())
conn.commit()

# Read and execute indexes migration
with open('002_create_indexes.sql', 'r') as f:
    cursor.execute(f.read())
conn.commit()

cursor.close()
conn.close()
```

## Accessing Supabase Connection Details

1. Go to your **Supabase Project Dashboard**
2. Click **Connect** (top right)
3. Select **Connection String** tab
4. Choose **Username and Password** option
5. Copy the connection string or individual details:
   - **Host:** `db.supabase.co` (or your custom domain)
   - **Database:** `postgres` (default)
   - **User:** `postgres` (or your custom user)
   - **Password:** Found in Project Settings > Database

## Configuration in Backend

The backend (`config.py`) expects these environment variables:

```bash
# Supabase REST API credentials
SUPABASE_URL=<your-supabase-url>
SUPABASE_PUBLISHABLE_KEY=<your-public-anon-key>

# For direct database connection (optional)
SUPABASE_DB_PASSWORD=<your-database-password>

# Legacy support for direct connection string
DATABASE_URL=postgresql://user:password@db.supabase.co:5432/postgres?sslmode=require
```

## Verifying the Migration

### 1. Check Tables Exist
```sql
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;
```

Expected output:
```
 chat_messages
 courses
 knowledge_points
 quiz_attempts
 quizzes
 slide_pages
 slides
 video_transcripts
 videos
```

### 2. Check Indexes Created
```sql
SELECT indexname FROM pg_indexes 
WHERE schemaname = 'public' 
ORDER BY indexname;
```

Should show 30+ index names starting with `idx_`

### 3. Check Table Schema
```sql
\d courses  -- View table structure
\d slides   -- View table structure
-- etc.
```

### 4. Test Foreign Keys
```sql
-- This should fail (course doesn't exist)
INSERT INTO slides (course_id, filename, original_filename, file_type, file_path) 
VALUES (999, 'test.pdf', 'test.pdf', 'pdf', '/path/test.pdf');

-- This should succeed
INSERT INTO courses (title, description) 
VALUES ('Test Course', 'A test course');

-- This should succeed now
INSERT INTO slides (course_id, filename, original_filename, file_type, file_path) 
VALUES (1, 'test.pdf', 'test.pdf', 'pdf', '/path/test.pdf');
```

## Common Issues & Troubleshooting

### Issue: "Permission denied" Error
**Cause:** Using the wrong database role (anon key instead of service role)
**Solution:** Use a role with proper permissions in Supabase SQL Editor or use service_role credentials

### Issue: "Table already exists" Error
**Cause:** Migration scripts have been run before
**Solution:** Tables are safe to recreate (DROP IF EXISTS is used). Re-running is idempotent.

### Issue: "Foreign key constraint failed"
**Cause:** Trying to insert data referencing non-existent parent records
**Solution:** Insert parent records first (e.g., courses before slides)

### Issue: Indexes not being used
**Cause:** Query optimizer chooses not to use index (common for small tables)
**Solution:** Use `EXPLAIN ANALYZE` to verify query plans; indexes are beneficial at scale

## Performance Considerations

### Pre-Migration
- Total schema: ~9 tables
- Total indexes: ~30+
- Storage: ~100 MB for empty schema + indexes
- Migration time: ~10 seconds total

### After Large Data Population
Monitor these metrics:
- Disk usage (indexes take ~10-15% of data size)
- Query performance (should improve significantly)
- Connection pool saturation

### Optimization Tips
1. **Use pagination** for large result sets
2. **Create composite indexes** for your specific query patterns
3. **Use EXPLAIN ANALYZE** to verify index usage
4. **Archive old chat messages** and quiz attempts periodically
5. **Monitor slow queries** using Supabase dashboard

## Rollback Instructions

If you need to remove all tables and start over:

```sql
-- Drop all tables (CASCADE handles dependencies)
DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS quiz_attempts CASCADE;
DROP TABLE IF EXISTS quizzes CASCADE;
DROP TABLE IF EXISTS knowledge_points CASCADE;
DROP TABLE IF EXISTS video_transcripts CASCADE;
DROP TABLE IF EXISTS videos CASCADE;
DROP TABLE IF EXISTS slide_pages CASCADE;
DROP TABLE IF EXISTS slides CASCADE;
DROP TABLE IF EXISTS courses CASCADE;

-- Then re-run 001_init_schema.sql and 002_create_indexes.sql
```

## Next Steps

1. ✅ Apply schema migration (001_init_schema.sql)
2. ✅ Apply index migration (002_create_indexes.sql)
3. 🔄 Set up backend with Supabase credentials
4. 🔄 Test database connection from Flask application
5. 🔄 Run application: `python run.py`
6. 🔄 Populate sample data if available

## References

- [Supabase Documentation](https://supabase.com/docs)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy ORM Models](https://flask-sqlalchemy.palletsprojects.com/models-and-tables/)
- [Database Performance Best Practices](https://supabase.com/docs/guides/database/overview)
