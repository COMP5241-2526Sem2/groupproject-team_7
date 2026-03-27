#!/bin/bash

# SyncLearn Database Migration Helper Script
# This script helps apply database migrations to Supabase PostgreSQL
# Usage: ./run_migrations.sh <supabase_host> <database> <username> <password>

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values (can be overridden by environment or arguments)
SUPABASE_HOST="${1:-db.supabase.co}"
DATABASE="${2:-postgres}"
USERNAME="${3:-postgres}"
PASSWORD="${4:-}"

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to display help
show_help() {
    echo "SyncLearn Database Migration Helper"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
    echo "  -h, --host HOST          Supabase host (default: db.supabase.co)"
    echo "  -d, --database DB        Database name (default: postgres)"
    echo "  -u, --user USER          Database user (default: postgres)"
    echo "  -p, --password PASS      Database password (prompted if not provided)"
    echo "  --help                   Show this help message"
    echo ""
    echo "ENVIRONMENT VARIABLES:"
    echo "  PGHOST                   Supabase host"
    echo "  PGDATABASE               Database name"
    echo "  PGUSER                   Database user"
    echo "  PGPASSWORD               Database password"
    echo ""
    echo "EXAMPLES:"
    echo "  # Interactive mode (will prompt for password)"
    echo "  $0 -h your-project.supabase.co -u postgres"
    echo ""
    echo "  # With all parameters"
    echo "  $0 -h your-project.supabase.co -d postgres -u postgres -p 'your-password'"
    echo ""
    echo "  # Using environment variables"
    echo "  export PGHOST=your-project.supabase.co"
    echo "  export PGUSER=postgres"
    echo "  export PGPASSWORD=your-password"
    echo "  $0"
    echo ""
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--host)
            SUPABASE_HOST="$2"
            shift 2
            ;;
        -d|--database)
            DATABASE="$2"
            shift 2
            ;;
        -u|--user)
            USERNAME="$2"
            shift 2
            ;;
        -p|--password)
            PASSWORD="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Use environment variables if not provided via command line
SUPABASE_HOST="${PGHOST:-$SUPABASE_HOST}"
DATABASE="${PGDATABASE:-$DATABASE}"
USERNAME="${PGUSER:-$USERNAME}"
PASSWORD="${PGPASSWORD:-$PASSWORD}"

# Prompt for password if not provided
if [ -z "$PASSWORD" ]; then
    read -sp "Enter database password: " PASSWORD
    echo ""
fi

# Check if required tools are installed
if ! command -v psql &> /dev/null; then
    print_error "psql is not installed. Please install PostgreSQL client tools."
    echo "  - macOS: brew install postgresql"
    echo "  - Ubuntu: sudo apt-get install postgresql-client"
    echo "  - Windows: Install PostgreSQL"
    exit 1
fi

print_info "Supabase Database Migration Helper"
echo ""
print_info "Configuration:"
echo "  Host:     $SUPABASE_HOST"
echo "  Database: $DATABASE"
echo "  User:     $USERNAME"
echo ""

# Test connection
print_info "Testing database connection..."
if PGPASSWORD="$PASSWORD" psql -h "$SUPABASE_HOST" -U "$USERNAME" -d "$DATABASE" -c "SELECT 1;" > /dev/null 2>&1; then
    print_info "✓ Connection successful"
else
    print_error "Connection failed. Please check your credentials."
    exit 1
fi

echo ""

# Apply schema migration
print_info "Applying schema migration (001_init_schema.sql)..."
if PGPASSWORD="$PASSWORD" psql -h "$SUPABASE_HOST" \
    -U "$USERNAME" \
    -d "$DATABASE" \
    -f "$SCRIPT_DIR/001_init_schema.sql" > /dev/null 2>&1; then
    print_info "✓ Schema migration completed successfully"
else
    print_error "Schema migration failed. Check the SQL errors above."
    exit 1
fi

echo ""

# Apply indexes migration
print_info "Applying index migration (002_create_indexes.sql)..."
if PGPASSWORD="$PASSWORD" psql -h "$SUPABASE_HOST" \
    -U "$USERNAME" \
    -d "$DATABASE" \
    -f "$SCRIPT_DIR/002_create_indexes.sql" > /dev/null 2>&1; then
    print_info "✓ Index migration completed successfully"
else
    print_error "Index migration failed. Check the SQL errors above."
    exit 1
fi

echo ""

# Verify migration
print_info "Verifying migration..."
TABLE_COUNT=$(PGPASSWORD="$PASSWORD" psql -h "$SUPABASE_HOST" \
    -U "$USERNAME" \
    -d "$DATABASE" \
    -t -c "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public';")

INDEX_COUNT=$(PGPASSWORD="$PASSWORD" psql -h "$SUPABASE_HOST" \
    -U "$USERNAME" \
    -d "$DATABASE" \
    -t -c "SELECT COUNT(*) FROM pg_indexes WHERE schemaname = 'public';")

echo "  Tables created: $TABLE_COUNT"
echo "  Indexes created: $INDEX_COUNT"

if [ "$TABLE_COUNT" -eq 9 ] && [ "$INDEX_COUNT" -gt 0 ]; then
    echo ""
    print_info "✓ Migration verification successful!"
    echo ""
    print_info "Next steps:"
    echo "  1. Configure backend with Supabase credentials:"
    echo "     - SUPABASE_URL"
    echo "     - SUPABASE_PUBLISHABLE_KEY"
    echo "  2. Run the backend: python run.py"
    echo "  3. Test the API endpoints"
    echo ""
else
    print_warning "Verification completed but table or index count unexpected"
    echo "  Expected: 9 tables, 30+ indexes"
    echo "  Got: $TABLE_COUNT tables, $INDEX_COUNT indexes"
fi

print_info "Migration complete!"
