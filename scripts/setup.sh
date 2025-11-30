#!/bin/bash

# GPS Store Initial Setup Script
# This script sets up the production environment for the first time

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi

    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Create .env file if it doesn't exist
create_env_file() {
    if [ -f ".env" ]; then
        log_warn ".env file already exists. Skipping creation."
        return
    fi

    log_info "Creating .env file..."

    cat > .env << EOF
# Django Configuration
DEBUG=False
SECRET_KEY=your-super-secret-key-here-change-this-in-production
ALLOWED_HOSTS=your-domain.com,www.your-domain.com,localhost

# Database Configuration
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=gpsstore_prod
DATABASE_USER=gpsstore_user
DATABASE_PASSWORD=your-secure-db-password-here
DATABASE_HOST=db
DATABASE_PORT=5432

# Redis Configuration
REDIS_URL=redis://redis:6379/1

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password-here
DEFAULT_FROM_EMAIL=noreply@gpsstore.com

# Security Settings
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True

# Sentry Configuration (optional)
SENTRY_DSN=your-sentry-dsn-here

# Environment
ENVIRONMENT=production
EOF

    log_info ".env file created. Please update the values with your actual configuration."
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."

    mkdir -p logs
    mkdir -p media
    mkdir -p staticfiles
    mkdir -p backup/postgres
    mkdir -p backup/media
    mkdir -p ssl

    log_info "Directories created"
}

# Generate SSL certificates (self-signed for development)
generate_ssl() {
    log_info "Generating self-signed SSL certificates..."

    openssl req -x509 -newkey rsa:4096 -keyout ssl/ssl-cert-snakeoil.key -out ssl/ssl-cert-snakeoil.pem -days 365 -nodes -subj "/C=US/ST=State/L=City/O=Organization/CN=your-domain.com"

    log_info "SSL certificates generated"
}

# Build and start services
start_services() {
    log_info "Building and starting services..."

    docker-compose down -v 2>/dev/null || true
    docker-compose build
    docker-compose up -d db redis

    log_info "Waiting for database to be ready..."
    sleep 30

    # Run initial migrations
    docker-compose run --rm web python manage.py migrate

    # Create superuser
    log_info "Creating Django superuser..."
    docker-compose run --rm web python manage.py createsuperuser --noinput --username admin --email admin@gpsstore.com || log_warn "Superuser creation failed. You can create it manually later."

    # Collect static files
    docker-compose run --rm web python manage.py collectstatic --noinput

    # Start all services
    docker-compose up -d

    log_info "Services started successfully"
}

# Setup systemd services (for non-Docker deployment)
setup_systemd() {
    log_info "Setting up systemd services..."

    # Gunicorn service
    cat > /etc/systemd/system/gunicorn.service << EOF
[Unit]
Description=Gunicorn daemon for GPS Store
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/your/project
Environment="PATH=/path/to/your/venv/bin"
ExecStart=/path/to/your/venv/bin/gunicorn --config gunicorn.conf.py gps_store.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
EOF

    # Nginx reload
    systemctl daemon-reload
    systemctl enable gunicorn
    systemctl start gunicorn

    log_info "Systemd services configured"
}

# Main setup process
main() {
    log_info "Starting initial setup of GPS Store"

    check_prerequisites
    create_env_file
    create_directories
    generate_ssl
    start_services

    log_info "Initial setup completed!"
    log_info "Please update the .env file with your actual configuration values."
    log_info "Don't forget to:"
    log_info "  1. Update ALLOWED_HOSTS with your domain"
    log_info "  2. Set a secure SECRET_KEY"
    log_info "  3. Configure database credentials"
    log_info "  4. Set up proper SSL certificates"
    log_info "  5. Configure email settings"
    log_info "  6. Set up monitoring and backups"
}

# Run main function
main "$@"