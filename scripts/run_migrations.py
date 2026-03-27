#!/usr/bin/env python3
"""
SyncLearn Database Migration Helper Script
Runs database migrations on Supabase PostgreSQL

This script is platform-independent and works on Windows, macOS, and Linux.
It requires the psycopg2 package to connect to PostgreSQL.

Usage:
    python run_migrations.py --host db.supabase.co --user postgres --database postgres
    
    Or interactively:
    python run_migrations.py
"""

import argparse
import getpass
import sys
import os
from pathlib import Path

try:
    import psycopg2
except ImportError:
    print("ERROR: psycopg2 is not installed.")
    print("Please install it using: pip install psycopg2-binary")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def print_info(msg):
    """Print info message"""
    print(f"{Colors.BLUE}[INFO]{Colors.END} {msg}")


def print_success(msg):
    """Print success message"""
    print(f"{Colors.GREEN}[✓]{Colors.END} {msg}")


def print_error(msg):
    """Print error message"""
    print(f"{Colors.RED}[ERROR]{Colors.END} {msg}", file=sys.stderr)


def print_warning(msg):
    """Print warning message"""
    print(f"{Colors.YELLOW}[WARNING]{Colors.END} {msg}")


def test_connection(host, database, user, password):
    """Test database connection"""
    try:
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password,
            connect_timeout=5
        )
        conn.close()
        return True
    except (Exception,) as error:
        print_error(f"Connection failed: {error}")
        return False


def read_sql_file(filepath):
    """Read SQL migration file"""
    try:
        with open(filepath, 'r') as f:
            return f.read()
    except FileNotFoundError:
        print_error(f"File not found: {filepath}")
        return None


def execute_migration(host, database, user, password, sql_content, migration_name):
    """Execute a migration script"""
    try:
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        
        # Split by semicolon and execute each statement
        statements = [s.strip() for s in sql_content.split(';') if s.strip()]
        
        for statement in statements:
            try:
                cursor.execute(statement)
            except psycopg2.errors.DuplicateObject:
                # Ignore "already exists" errors (idempotent)
                conn.rollback()
            except Exception as e:
                print_error(f"Error executing statement: {e}")
                conn.rollback()
                return False
        
        conn.commit()
        cursor.close()
        conn.close()
        print_success(f"{migration_name} completed successfully")
        return True
        
    except (Exception,) as error:
        print_error(f"Migration failed: {error}")
        return False


def verify_migration(host, database, user, password):
    """Verify that migration was successful"""
    try:
        conn = psycopg2.connect(
            host=host,
            database=database,
            user=user,
            password=password
        )
        cursor = conn.cursor()
        
        # Count tables
        cursor.execute("""
            SELECT COUNT(*) FROM pg_tables 
            WHERE schemaname = 'public'
        """)
        table_count = cursor.fetchone()[0]
        
        # Count indexes
        cursor.execute("""
            SELECT COUNT(*) FROM pg_indexes 
            WHERE schemaname = 'public'
        """)
        index_count = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return table_count, index_count
        
    except (Exception,) as error:
        print_error(f"Verification failed: {error}")
        return None, None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='SyncLearn Database Migration Helper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (prompts for all inputs)
  python run_migrations.py
  
  # With all parameters
  python run_migrations.py --host db.supabase.co --user postgres --password 'mypass' --database postgres
  
  # With environment variables
  export SUPABASE_HOST=db.supabase.co
  export SUPABASE_USER=postgres
  export SUPABASE_PASSWORD=mypass
  export SUPABASE_DATABASE=postgres
  python run_migrations.py
        """
    )
    
    parser.add_argument('--host', help='Supabase host')
    parser.add_argument('--user', help='Database user')
    parser.add_argument('--password', help='Database password')
    parser.add_argument('--database', help='Database name')
    
    args = parser.parse_args()
    
    # Get values from arguments or environment variables or prompt
    host = args.host or os.environ.get('SUPABASE_HOST', '')
    user = args.user or os.environ.get('SUPABASE_USER', '')
    password = args.password or os.environ.get('SUPABASE_PASSWORD', '')
    database = args.database or os.environ.get('SUPABASE_DATABASE', '')
    
    # Prompt for missing values
    if not host:
        host = input("Enter Supabase host (default: db.supabase.co): ").strip() or "db.supabase.co"
    
    if not user:
        user = input("Enter database user (default: postgres): ").strip() or "postgres"
    
    if not database:
        database = input("Enter database name (default: postgres): ").strip() or "postgres"
    
    if not password:
        password = getpass.getpass("Enter database password: ")
    
    print()
    print_info("SyncLearn Database Migration Helper")
    print()
    print_info("Configuration:")
    print(f"  Host:     {host}")
    print(f"  Database: {database}")
    print(f"  User:     {user}")
    print()
    
    # Test connection
    print_info("Testing database connection...")
    if not test_connection(host, database, user, password):
        print_error("Connection failed. Please check your credentials.")
        sys.exit(1)
    print_success("Connection successful")
    print()
    
    # Get script directory
    script_dir = Path(__file__).parent
    
    # Apply schema migration
    print_info("Applying schema migration (001_init_schema.sql)...")
    sql_file = script_dir / '001_init_schema.sql'
    if not sql_file.exists():
        print_error(f"Migration file not found: {sql_file}")
        sys.exit(1)
    
    sql_content = read_sql_file(sql_file)
    if not sql_content:
        sys.exit(1)
    
    if not execute_migration(host, database, user, password, sql_content, "Schema migration"):
        sys.exit(1)
    print()
    
    # Apply indexes migration
    print_info("Applying index migration (002_create_indexes.sql)...")
    sql_file = script_dir / '002_create_indexes.sql'
    if not sql_file.exists():
        print_error(f"Migration file not found: {sql_file}")
        sys.exit(1)
    
    sql_content = read_sql_file(sql_file)
    if not sql_content:
        sys.exit(1)
    
    if not execute_migration(host, database, user, password, sql_content, "Index migration"):
        sys.exit(1)
    print()
    
    # Verify migration
    print_info("Verifying migration...")
    table_count, index_count = verify_migration(host, database, user, password)
    
    if table_count is not None:
        print(f"  Tables created: {table_count}")
        print(f"  Indexes created: {index_count}")
        print()
        
        if table_count == 9 and index_count > 0:
            print_success("Migration verification successful!")
            print()
            print_info("Next steps:")
            print("  1. Configure backend with Supabase credentials:")
            print("     - SUPABASE_URL")
            print("     - SUPABASE_PUBLISHABLE_KEY")
            print("  2. Run the backend: python run.py")
            print("  3. Test the API endpoints")
        else:
            print_warning("Verification completed but table or index count unexpected")
            print(f"  Expected: 9 tables, 30+ indexes")
    
    print()
    print_success("Migration complete!")


if __name__ == '__main__':
    main()
