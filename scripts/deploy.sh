#!/bin/bash

# GPS Store Deployment Script
# This script handles the deployment of the GPS Store application

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="gpsstore"
DOCKER_COMPOSE_FILE="docker-compose.yml"
BACKUP_DIR="./backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

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

# Check if .env file exists
check_env() {
    if [ ! -f ".env" ]; then
        log_error ".env file not found. Please create it with production settings."
        exit 1
    fi
    log_info ".env file found"
}

# Create backup
create_backup() {
    log_info "Creating backup..."
    mkdir -p "$BACKUP_DIR"

    # Backup database
    docker-compose exec -T db pg_dump -U "$DATABASE_USER" "$DATABASE_NAME" > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql" 2>/dev/null || log_warn "Database backup failed"

    # Backup media files
    tar -czf "$BACKUP_DIR/media_backup_$TIMESTAMP.tar.gz" media/ 2>/dev/null || log_warn "Media backup failed"

    log_info "Backup completed"
}

# Pull latest changes
pull_changes() {
    log_info "Pulling latest changes..."
    git pull origin main
}

# Build and deploy
deploy() {
    log_info "Building and deploying application..."

    # Stop services
    docker-compose down

    # Build images
    docker-compose build --no-cache

    # Start services
    docker-compose up -d

    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30

    # Run migrations
    docker-compose exec -T web python manage.py migrate

    # Collect static files
    docker-compose exec -T web python manage.py collectstatic --noinput

    log_info "Deployment completed successfully"
}

# Health check
health_check() {
    log_info "Performing health check..."

    # Check if services are running
    if docker-compose ps | grep -q "Up"; then
        log_info "All services are running"
    else
        log_error "Some services failed to start"
        exit 1
    fi

    # Check application health
    if curl -f -s http://localhost/health/ > /dev/null; then
        log_info "Application health check passed"
    else
        log_error "Application health check failed"
        exit 1
    fi
}

# Cleanup old backups
cleanup() {
    log_info "Cleaning up old backups..."
    find "$BACKUP_DIR" -name "*.sql" -mtime +7 -delete 2>/dev/null || true
    find "$BACKUP_DIR" -name "*.tar.gz" -mtime +7 -delete 2>/dev/null || true
    log_info "Cleanup completed"
}

# Rollback function
rollback() {
    log_error "Deployment failed. Rolling back..."
    docker-compose down
    # Restore from backup if needed
    log_info "Rollback completed"
}

# Main deployment process
main() {
    log_info "Starting deployment of $PROJECT_NAME"

    check_env
    create_backup
    pull_changes

    if deploy; then
        health_check
        cleanup
        log_info "Deployment successful!"
    else
        rollback
        exit 1
    fi
}

# Run main function
main "$@"