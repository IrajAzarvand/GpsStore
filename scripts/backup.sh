#!/bin/bash

# GPS Store Backup Script
# This script creates backups of database and media files

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="./backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=7

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

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_DIR/postgres"
    mkdir -p "$BACKUP_DIR/media"
    log_info "Backup directories created"
}

# Backup PostgreSQL database
backup_database() {
    log_info "Starting database backup..."

    if docker-compose ps db | grep -q "Up"; then
        docker-compose exec -T db pg_dump -U "$DATABASE_USER" "$DATABASE_NAME" > "$BACKUP_DIR/postgres/db_backup_$TIMESTAMP.sql"

        # Compress the backup
        gzip "$BACKUP_DIR/postgres/db_backup_$TIMESTAMP.sql"

        log_info "Database backup completed: db_backup_$TIMESTAMP.sql.gz"
    else
        log_error "Database container is not running"
        exit 1
    fi
}

# Backup media files
backup_media() {
    log_info "Starting media files backup..."

    if [ -d "media" ]; then
        tar -czf "$BACKUP_DIR/media/media_backup_$TIMESTAMP.tar.gz" -C media .
        log_info "Media files backup completed: media_backup_$TIMESTAMP.tar.gz"
    else
        log_warn "Media directory not found"
    fi
}

# Backup static files
backup_static() {
    log_info "Starting static files backup..."

    if [ -d "staticfiles" ]; then
        tar -czf "$BACKUP_DIR/static_backup_$TIMESTAMP.tar.gz" -C staticfiles .
        log_info "Static files backup completed: static_backup_$TIMESTAMP.tar.gz"
    else
        log_warn "Static files directory not found"
    fi
}

# Clean up old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups (older than $RETENTION_DAYS days)..."

    # Clean up database backups
    find "$BACKUP_DIR/postgres" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

    # Clean up media backups
    find "$BACKUP_DIR/media" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

    # Clean up static backups
    find "$BACKUP_DIR" -name "static_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

    log_info "Cleanup completed"
}

# Generate backup report
generate_report() {
    log_info "Generating backup report..."

    REPORT_FILE="$BACKUP_DIR/backup_report_$TIMESTAMP.txt"

    echo "GPS Store Backup Report" > "$REPORT_FILE"
    echo "Timestamp: $TIMESTAMP" >> "$REPORT_FILE"
    echo "=========================" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    echo "Database Backups:" >> "$REPORT_FILE"
    ls -la "$BACKUP_DIR/postgres/"*.sql.gz 2>/dev/null || echo "No database backups found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    echo "Media Backups:" >> "$REPORT_FILE"
    ls -la "$BACKUP_DIR/media/"*.tar.gz 2>/dev/null || echo "No media backups found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    echo "Static Backups:" >> "$REPORT_FILE"
    ls -la "$BACKUP_DIR/"static_backup_*.tar.gz 2>/dev/null || echo "No static backups found" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"

    echo "Disk Usage:" >> "$REPORT_FILE"
    du -sh "$BACKUP_DIR"/* 2>/dev/null || echo "Unable to calculate disk usage" >> "$REPORT_FILE"

    log_info "Backup report generated: $REPORT_FILE"
}

# Main backup process
main() {
    log_info "Starting GPS Store backup process"

    create_backup_dir
    backup_database
    backup_media
    backup_static
    cleanup_old_backups
    generate_report

    log_info "Backup process completed successfully"
    log_info "Backup location: $BACKUP_DIR"
}

# Run main function
main "$@"