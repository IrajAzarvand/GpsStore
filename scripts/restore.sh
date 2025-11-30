#!/bin/bash

# GPS Store Restore Script
# This script restores database and media files from backups

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="./backup"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# List available backups
list_backups() {
    echo "Available Database Backups:"
    ls -la "$BACKUP_DIR/postgres/"*.sql.gz 2>/dev/null || echo "No database backups found"
    echo ""
    echo "Available Media Backups:"
    ls -la "$BACKUP_DIR/media/"*.tar.gz 2>/dev/null || echo "No media backups found"
    echo ""
    echo "Available Static Backups:"
    ls -la "$BACKUP_DIR/"static_backup_*.tar.gz 2>/dev/null || echo "No static backups found"
}

# Restore database
restore_database() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        log_error "No database backup file specified"
        echo "Usage: $0 database <backup_file.sql.gz>"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi

    log_info "Restoring database from $backup_file"

    # Create a temporary uncompressed file
    temp_file=$(mktemp)
    gunzip -c "$backup_file" > "$temp_file"

    # Stop the web service to prevent conflicts
    docker-compose stop web

    # Restore the database
    docker-compose exec -T db psql -U "$DATABASE_USER" -d "$DATABASE_NAME" < "$temp_file"

    # Clean up
    rm "$temp_file"

    # Restart the web service
    docker-compose start web

    log_info "Database restore completed"
}

# Restore media files
restore_media() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        log_error "No media backup file specified"
        echo "Usage: $0 media <backup_file.tar.gz>"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi

    log_info "Restoring media files from $backup_file"

    # Create media directory if it doesn't exist
    mkdir -p media

    # Extract the backup
    tar -xzf "$backup_file" -C media/

    log_info "Media files restore completed"
}

# Restore static files
restore_static() {
    local backup_file=$1

    if [ -z "$backup_file" ]; then
        log_error "No static backup file specified"
        echo "Usage: $0 static <backup_file.tar.gz>"
        exit 1
    fi

    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        exit 1
    fi

    log_info "Restoring static files from $backup_file"

    # Create staticfiles directory if it doesn't exist
    mkdir -p staticfiles

    # Extract the backup
    tar -xzf "$backup_file" -C staticfiles/

    log_info "Static files restore completed"
}

# Show usage
usage() {
    echo "GPS Store Restore Script"
    echo "Usage:"
    echo "  $0 list                           - List available backups"
    echo "  $0 database <backup_file.sql.gz>  - Restore database from backup"
    echo "  $0 media <backup_file.tar.gz>     - Restore media files from backup"
    echo "  $0 static <backup_file.tar.gz>    - Restore static files from backup"
    echo "  $0 all <timestamp>                - Restore all components from timestamp"
}

# Restore all components
restore_all() {
    local timestamp=$1

    if [ -z "$timestamp" ]; then
        log_error "No timestamp specified"
        echo "Usage: $0 all <timestamp>"
        exit 1
    fi

    log_info "Restoring all components from timestamp: $timestamp"

    # Restore database
    db_backup="$BACKUP_DIR/postgres/db_backup_$timestamp.sql.gz"
    if [ -f "$db_backup" ]; then
        restore_database "$db_backup"
    else
        log_warn "Database backup not found for timestamp: $timestamp"
    fi

    # Restore media
    media_backup="$BACKUP_DIR/media/media_backup_$timestamp.tar.gz"
    if [ -f "$media_backup" ]; then
        restore_media "$media_backup"
    else
        log_warn "Media backup not found for timestamp: $timestamp"
    fi

    # Restore static files
    static_backup="$BACKUP_DIR/static_backup_$timestamp.tar.gz"
    if [ -f "$static_backup" ]; then
        restore_static "$static_backup"
    else
        log_warn "Static backup not found for timestamp: $timestamp"
    fi

    log_info "Full restore completed"
}

# Main restore process
main() {
    case "$1" in
        list)
            list_backups
            ;;
        database)
            restore_database "$2"
            ;;
        media)
            restore_media "$2"
            ;;
        static)
            restore_static "$2"
            ;;
        all)
            restore_all "$2"
            ;;
        *)
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"