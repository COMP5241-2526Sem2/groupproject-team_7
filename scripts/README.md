# Database Migration Scripts Overview

This directory contains all necessary SQL and helper scripts to initialize the SyncLearn Supabase PostgreSQL database.

## Quick Start

### Option 1: Use Supabase Dashboard (Easiest)
1. Go to Supabase Dashboard → SQL Editor
2. Create new query and copy contents of `001_init_schema.sql`
3. Run the query
4. Repeat for `002_create_indexes.sql`

### Option 2: Use Python Script (Cross-Platform)
```bash
python run_migrations.py
```

### Option 3: Use Bash Script (Linux/macOS)
```bash
./run_migrations.sh
```

---

## File Descriptions

### `001_init_schema.sql`
**Purpose:** Creates the complete database schema

**Contents:**
- 9 tables: courses, slides, slide_pages, videos, video_transcripts, knowledge_points, quizzes, quiz_attempts, chat_messages
- Primary keys, foreign keys with CASCADE deletes
- UNIQUE constraints for compound keys
- Default timestamps and values
- Automatic updated_at trigger

**Execution Time:** < 1 second
**Prerequisites:** None (Supabase database must exist)
**Idempotent:** Yes (uses CREATE TABLE IF NOT EXISTS)

**Tables Created:**
| Table | Purpose |
|-------|---------|
| courses | Course metadata |
| slides | Slide file metadata |
| slide_pages | Individual slide pages with content |
| videos | Video file metadata |
| video_transcripts | ASR transcript segments |
| knowledge_points | Learning objectives alignment |
| quizzes | Quiz questions |
| quiz_attempts | Student quiz responses |
| chat_messages | Chat messages |

---

### `002_create_indexes.sql`
**Purpose:** Creates 30+ indexes to optimize query performance

**Contents:**
- Foreign key indexes for JOIN operations
- Filtering indexes for WHERE clauses
- Sorting indexes for ORDER BY operations
- Composite indexes for common query patterns
- GIN indexes for JSONB fields

**Execution Time:** 5-10 seconds
**Prerequisites:** Schema migration must be applied first
**Idempotent:** Yes (uses CREATE INDEX IF NOT EXISTS)

**Index Categories:**
- Courses: 1 index
- Slides: 3 indexes
- Slide Pages: 3 indexes
- Videos: 3 indexes
- Video Transcripts: 3 indexes
- Knowledge Points: 4 indexes
- Quizzes: 4 indexes
- Quiz Attempts: 5 indexes
- Chat Messages: 5 indexes
- JSONB: 2 indexes

---

### `run_migrations.sh`
**Purpose:** Bash helper script to automate migrations

**Platform:** Linux/macOS
**Prerequisites:** PostgreSQL client tools (`psql`), Bash

**Usage:**
```bash
# Interactive (will prompt for password)
./run_migrations.sh

# With all parameters
./run_migrations.sh -h your-project.supabase.co -d postgres -u postgres -p 'password'

# Show help
./run_migrations.sh --help
```

**Features:**
- Connection testing
- Automatic schema and index migration
- Migration verification
- Color-coded output
- Error handling

---

### `run_migrations.py`
**Purpose:** Python helper script to automate migrations

**Platform:** Windows/macOS/Linux
**Prerequisites:** Python 3.6+, psycopg2 (`pip install psycopg2-binary`)

**Usage:**
```bash
# Interactive mode (prompts for all inputs)
python run_migrations.py

# With parameters
python run_migrations.py --host db.supabase.co --user postgres --password 'pass' --database postgres

# Using environment variables
export SUPABASE_HOST=db.supabase.co
export SUPABASE_USER=postgres
export SUPABASE_PASSWORD=mypass
python run_migrations.py
```

**Features:**
- Cross-platform support (Windows, macOS, Linux)
- Connection testing
- Automatic schema and index migration
- Migration verification
- Colored output
- Error handling
- Support for environment variables

---

### `MIGRATIONS.md`
**Purpose:** Comprehensive guide for database migrations

**Contents:**
- Overview of database schema
- Detailed file descriptions
- Multiple methods to apply migrations
- How to access Supabase credentials
- Verification procedures
- Troubleshooting guide
- Performance considerations
- Rollback instructions
- References

---

## Migration Execution Order

Always follow this order:

1. **`001_init_schema.sql`** ← Creates all tables and constraints
2. **`002_create_indexes.sql`** ← Creates indexes for optimization

---

## Database Schema Diagram

```
┌────────────────────────────────────────────────────────────┐
│                        DATABASE                            │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐                                       │
│  │    courses       │                                       │
│  │  ├─ id (PK)      │                                       │
│  │  ├─ title        │                                       │
│  │  ├─ description  │                                       │
│  │  ├─ created_at   │                                       │
│  │  └─ updated_at   │                                       │
│  └────────┬─────────┘                                       │
│           │                                                 │
│           ├─────────────────────────────────────────┐       │
│           │                                         │       │
│  ┌────────▼──────────┐                ┌────────────▼──────┐ │
│  │  slides           │                │  videos           │ │
│  │  ├─ id (PK)       │                │  ├─ id (PK)       │ │
│  │  ├─ course_id(FK) │                │  ├─ course_id(FK) │ │
│  │  ├─ filename      │                │  ├─ filename      │ │
│  │  ├─ file_type     │                │  ├─ duration      │ │
│  │  ├─ processed     │                │  ├─ processed     │ │
│  │  └─ created_at    │                │  └─ created_at    │ │
│  └────────┬──────────┘                └────────┬──────────┘ │
│           │                                    │             │
│  ┌────────▼──────────┐                ┌────────▼──────────┐  │
│  │  slide_pages      │                │video_transcripts  │  │
│  │  ├─ id (PK)       │                │  ├─ id (PK)       │  │
│  │  ├─ slide_id (FK) │                │  ├─ video_id (FK) │  │
│  │  ├─ page_number   │                │  ├─ segment_index │  │
│  │  ├─ content_text  │                │  ├─ start_time    │  │
│  │  ├─ embedding     │                │  ├─ text          │  │
│  │  └─ thumbnail_path│                │  ├─ embedding     │  │
│  └────────┬──────────┘                └───────────────────┘  │
│           │                                                   │
│  ┌────────▼──────────────────┐                               │
│  │ knowledge_points          │                               │
│  │  ├─ id (PK)               │                               │
│  │  ├─ slide_page_id (FK)    │                               │
│  │  ├─ video_id (FK, nullable)│                              │
│  │  ├─ title                 │                               │
│  │  ├─ content               │                               │
│  │  ├─ video_timestamp       │                               │
│  │  ├─ confidence            │                               │
│  │  └─ created_at            │                               │
│  └────────┬───────────────────┘                              │
│           │                                                   │
│  ┌────────▼──────────┐        ┌──────────────────┐           │
│  │  quizzes          │        │  quiz_attempts   │           │
│  │  ├─ id (PK)       │        │  ├─ id (PK)      │           │
│  │  ├─ course_id(FK) │        │  ├─ quiz_id (FK) │           │
│  │  ├─ knowledge_... │────────┼─→├─ selected_ans │           │
│  │  ├─ question      │        │  ├─ is_correct   │           │
│  │  ├─ options(JSON) │        │  └─ created_at   │           │
│  │  ├─ correct_ans   │        └──────────────────┘           │
│  │  └─ created_at    │                                       │
│  └───────────────────┘                                       │
│                                                               │
│  ┌─────────────────────────────┐                             │
│  │  chat_messages              │                             │
│  │  ├─ id (PK)                 │                             │
│  │  ├─ course_id (FK)          │                             │
│  │  ├─ role (user/assistant)   │                             │
│  │  ├─ content                 │                             │
│  │  ├─ citations (JSON)        │                             │
│  │  └─ created_at              │                             │
│  └─────────────────────────────┘                             │
│                                                               │
└────────────────────────────────────────────────────────────┘
```

---

## Getting Started

### Step 1: Prepare Supabase Credentials
Get your Supabase credentials from:
- Dashboard: https://supabase.com
- Project Settings → Database
- Connection string or individual credentials

### Step 2: Run Migrations
Choose one method:
- **Supabase Dashboard** (simplest)
- **Python script** (cross-platform)
- **Bash script** (Linux/macOS)

### Step 3: Configure Backend
Update backend environment variables:
```bash
SUPABASE_URL=<your-project-url>
SUPABASE_PUBLISHABLE_KEY=<your-public-key>
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
```

### Step 4: Start Application
```bash
cd backend
python run.py
```

---

## Testing the Schema

After running migrations, verify tables were created:

```sql
-- List all tables
SELECT tablename FROM pg_tables 
WHERE schemaname = 'public' 
ORDER BY tablename;

-- List all indexes
SELECT indexname FROM pg_indexes 
WHERE schemaname = 'public' 
ORDER BY indexname;

-- Test inserting data
INSERT INTO courses (title, description) 
VALUES ('Test Course', 'Testing the schema');

-- Verify data was inserted
SELECT * FROM courses;
```

---

## Support & Documentation

- **Full Guide:** See `MIGRATIONS.md`
- **Supabase Docs:** https://supabase.com/docs
- **PostgreSQL Docs:** https://postgresql.org/docs/
- **Issues:** Check the troubleshooting section in `MIGRATIONS.md`

---

## File Structure

```
scripts/
├── 001_init_schema.sql      ← Create tables
├── 002_create_indexes.sql   ← Create indexes
├── run_migrations.sh        ← Bash helper
├── run_migrations.py        ← Python helper
├── MIGRATIONS.md            ← Full guide
└── README.md                ← This file
```

---

## Summary

| Task | File(s) |
|------|---------|
| **Manual Dashboard** | 001_init_schema.sql + 002_create_indexes.sql |
| **Automated (Python)** | run_migrations.py |
| **Automated (Bash)** | run_migrations.sh |
| **Full Documentation** | MIGRATIONS.md |
| **Quick Reference** | README.md |

Choose the method that best fits your setup and follow the instructions in `MIGRATIONS.md` for detailed guidance.
