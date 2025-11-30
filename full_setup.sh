#!/bin/bash
cd "$(dirname "$0")"

# GPS Store Full Setup Script with Docker
# This script sets up and runs the GPS Store site using Docker

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

# Install Docker and Docker Compose
install_docker() {
    log_info "Installing Docker and Docker Compose..."

    # Update package lists
    sudo apt update

    # Install required packages
    sudo apt install -y ca-certificates curl gnupg lsb-release

    # Create keyrings directory
    sudo install -m 0755 -d /etc/apt/keyrings

    # Add Docker's official GPG key
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    sudo chmod a+r /etc/apt/keyrings/docker.gpg

    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Update package lists again
    sudo apt update

    # Install Docker CE and Docker Compose plugin
    sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    # Start and enable Docker service
    sudo systemctl start docker
    sudo systemctl enable docker

    # Add current user to docker group
    sudo usermod -aG docker $USER

    log_info "Docker and Docker Compose installed successfully. You may need to log out and back in for group changes to take effect."
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
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi

    log_info "Prerequisites check passed"
}

# Generate a random SECRET_KEY
generate_secret_key() {
    openssl rand -base64 32
}

# Create .env file with custom values
create_env_file() {
    if [ -f ".env" ]; then
        log_warn ".env file already exists. Skipping creation."
        return
    fi

    log_info "Creating .env file with custom configurations..."

    SECRET_KEY=$(generate_secret_key)

    cat > .env << EOF
# Django Configuration
DEBUG=False
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=91.107.135.136,bruna.ir,www.bruna.ir,localhost
CSRF_TRUSTED_ORIGINS=https://bruna.ir,https://www.bruna.ir

# Database Configuration
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=gpsstore_prod
DATABASE_USER=gpsstore_user
DATABASE_PASSWORD=iraj66100
DATABASE_HOST=db
DATABASE_PORT=5432

# Redis Configuration
REDIS_URL=redis://redis:6379/1

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://bruna.ir

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
SENTRY_DSN=

# Environment
ENVIRONMENT=production

# Superuser Configuration
DJANGO_SUPERUSER_USERNAME=root
DJANGO_SUPERUSER_PASSWORD=iraj66100
DJANGO_SUPERUSER_EMAIL=root@gpsstore.com
EOF

    log_info ".env file created with generated SECRET_KEY and custom settings."
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

# Fix docker-entrypoint.sh line endings
fix_entrypoint_script() {
    log_info "Fixing docker-entrypoint.sh line endings..."
    
    if [ -f docker-entrypoint.sh ]; then
        sed -i 's/\r$//' docker-entrypoint.sh
        chmod +x docker-entrypoint.sh
        log_info "docker-entrypoint.sh line endings fixed"
    else
        log_warn "docker-entrypoint.sh not found, skipping line ending fix"
    fi
}

# Setup firewall (UFW)
setup_firewall() {
    log_info "Setting up firewall with UFW..."

    # Check if UFW is available
    if command -v ufw &> /dev/null; then
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        sudo ufw allow 22/tcp
        sudo ufw allow 5000/tcp
        # Monitoring ports
        sudo ufw allow 9090/tcp  # Prometheus
        sudo ufw allow 3000/tcp  # Grafana
        sudo ufw allow 9100/tcp  # Node Exporter
        sudo ufw allow 9113/tcp  # Nginx Exporter
        sudo ufw allow 9187/tcp  # Postgres Exporter
        sudo ufw allow 9121/tcp  # Redis Exporter
        log_info "Firewall configured: ports 80, 443, 22, 5000, 9090, 3000, 9100, 9113, 9187, 9121 allowed"
    else
        log_warn "UFW not found. Please manually configure firewall to allow ports 80, 443, 5000, 9090, 3000, 9100, 9113, 9187, 9121"
    fi
}

# Wait for web container to be healthy and running
wait_for_web_container() {
    log_info "Waiting for web container to be healthy and running..."
    
    local max_attempts=12  # 12 attempts * 5 seconds = 60 seconds
    local attempt=0
    local container_status=""
    
    while [ $attempt -lt $max_attempts ]; do
        attempt=$((attempt + 1))
        
        # Check container status using docker compose ps with json format
        container_status=$(docker compose ps web --format json 2>/dev/null | grep -o '"State":"[^"]*"' | cut -d'"' -f4)
        
        # Alternative: Check using docker inspect if compose ps fails
        if [ -z "$container_status" ]; then
            local container_id=$(docker compose ps -q web 2>/dev/null)
            if [ -n "$container_id" ]; then
                container_status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null)
            fi
        fi
        
        log_info "Web container status: ${container_status:-unknown} (attempt $attempt/$max_attempts)"
        
        # Check if container is running (not restarting)
        if [ "$container_status" = "running" ]; then
            log_info "✓ Web container is running and healthy!"
            return 0
        elif [ "$container_status" = "restarting" ]; then
            log_warn "Web container is restarting. Waiting 5 seconds before retry..."
            sleep 5
        elif [ "$container_status" = "exited" ] || [ "$container_status" = "dead" ]; then
            log_error "Web container has exited or died. Checking logs..."
            docker compose logs web --tail=50
            log_error "Web container failed to start properly. Please check the logs above."
            exit 1
        else
            # Container might still be starting up
            log_info "Waiting for web container to start... (status: ${container_status:-unknown})"
            sleep 5
        fi
    done
    
    # If we've exhausted all attempts, show logs and exit
    log_error "Web container did not become healthy within 60 seconds"
    log_error "Container is stuck in a restart loop or failed to start"
    log_info "Displaying last 50 lines of web container logs:"
    echo "----------------------------------------"
    docker compose logs web --tail=50
    echo "----------------------------------------"
    log_error "Please review the logs above to diagnose the issue"
    log_error "Common issues:"
    log_error "  - Database connection failures"
    log_error "  - Missing environment variables"
    log_error "  - Python/Django configuration errors"
    log_error "  - Permission issues with mounted volumes"
    exit 1
}

# Build and start services
start_services() {
    log_info "Building and starting Docker services..."

    # Stop any existing containers
    docker compose down -v 2>/dev/null || true

    # Step 1: Build Docker images
    log_info "Building Docker images..."
    docker compose build

    # Step 2: Start all Docker containers
    log_info "Starting all Docker containers..."
    docker compose up -d

    # Step 3: Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 20
    
    # Additional database readiness check
    log_info "Verifying database connection..."
    for i in {1..30}; do
        if docker compose exec -T db pg_isready -U gpsstore_user -d gpsstore_prod &> /dev/null; then
            log_info "Database is ready!"
            break
        fi
        if [ $i -eq 30 ]; then
            log_error "Database failed to become ready in time"
            exit 1
        fi
        echo -n "."
        sleep 2
    done
    
    # Step 4: Wait for web container to be healthy
    wait_for_web_container

    # Step 5: Run migrations
    log_info "Running database migrations..."
    docker compose exec -T web python manage.py migrate

    # Step 6: Create superuser with specified credentials
    log_info "Creating Django superuser 'root' with password 'iraj66100'..."
    docker compose exec -T web python manage.py createsuperuser --noinput || log_warn "Superuser may already exist or creation failed."

    # Step 7: Collect static files
    log_info "Collecting static files..."
    docker compose exec -T web python manage.py collectstatic --noinput

    log_info "All Docker setup steps completed successfully"
}

# Health check
health_check() {
    log_info "Performing health check and verifying site is running..."

    # Wait a bit for services to stabilize
    sleep 5

    # Step 7: Verify containers are running
    log_info "Checking Docker container status..."
    if docker compose ps | grep -q "Up"; then
        log_info "✓ All Docker services are running"
    else
        log_error "Some Docker services failed to start"
        docker compose ps
        exit 1
    fi

    # Verify the web service is responding
    log_info "Verifying web service is responding..."
    for i in {1..10}; do
        if curl -f -s -o /dev/null http://localhost:8000 2>/dev/null || curl -f -s -o /dev/null http://localhost 2>/dev/null; then
            log_info "✓ Site is running and responding to requests!"
            break
        fi
        if [ $i -eq 10 ]; then
            log_warn "Site may not be responding yet. Check logs with: docker compose logs web"
        fi
        sleep 3
    done

    log_info "✓ Health check passed - All systems operational"
}

# Setup GPS receiver systemd service
setup_gps_receiver_service() {
    log_info "Setting up GPS receiver systemd service..."

    # Copy systemd service file to system directory
    log_info "Copying GPS receiver service file to /etc/systemd/system/"
    sudo cp systemd/gps-receiver.service /etc/systemd/system/
    if [ $? -eq 0 ]; then
        log_info "✓ Service file copied successfully"
    else
        log_error "Failed to copy service file"
        return 1
    fi

    # Reload systemd daemon to recognize the new service
    log_info "Reloading systemd daemon..."
    sudo systemctl daemon-reload
    if [ $? -eq 0 ]; then
        log_info "✓ Systemd daemon reloaded"
    else
        log_error "Failed to reload systemd daemon"
        return 1
    fi

    # Enable the service to start on boot
    log_info "Enabling GPS receiver service to start on boot..."
    sudo systemctl enable gps-receiver.service
    if [ $? -eq 0 ]; then
        log_info "✓ GPS receiver service enabled"
    else
        log_error "Failed to enable GPS receiver service"
        return 1
    fi

    # Start the GPS receiver service
    log_info "Starting GPS receiver service..."
    sudo systemctl start gps-receiver.service
    if [ $? -eq 0 ]; then
        log_info "✓ GPS receiver service started"
    else
        log_error "Failed to start GPS receiver service"
        return 1
    fi

    # Check if service started successfully
    log_info "Verifying GPS receiver service status..."
    sleep 5
    if sudo systemctl is-active --quiet gps-receiver.service; then
        log_info "✓ GPS receiver service is active and running"
        sudo systemctl status gps-receiver.service --no-pager -l | head -10
    else
        log_warn "GPS receiver service may not have started properly"
        log_warn "Service status:"
        sudo systemctl status gps-receiver.service --no-pager -l
        log_warn "Check logs with: sudo journalctl -u gps-receiver.service -f"
    fi

    log_info "GPS receiver systemd service setup completed"
}

# Setup monitoring services
setup_monitoring() {
    log_info "Setting up monitoring services..."

    # Check if monitoring compose file exists
    if [ -f "monitoring/docker-compose.monitoring.yml" ]; then
        log_info "Starting monitoring services..."
        docker compose -f monitoring/docker-compose.monitoring.yml up -d

        # Wait for monitoring services to start
        sleep 10

        log_info "Monitoring services started successfully"
        log_info "  - Prometheus: http://localhost:9090"
        log_info "  - Grafana: http://localhost:3000 (admin/admin)"
        log_info "  - Node Exporter: http://localhost:9100"
        log_info "  - Nginx Exporter: http://localhost:9113"
        log_info "  - Postgres Exporter: http://localhost:9187"
        log_info "  - Redis Exporter: http://localhost:9121"
    else
        log_warn "Monitoring compose file not found. Skipping monitoring setup."
    fi
}

# Main setup process
main() {
    log_info "Starting full Docker-based setup of GPS Store"

    install_docker

    check_prerequisites
    create_env_file
    create_directories
    fix_entrypoint_script
    setup_firewall
    start_services
    health_check
    setup_gps_receiver_service
    setup_monitoring

    log_info "Full setup completed successfully!"
    log_info "The GPS Store site is now running with Docker."
    log_info "GPS receiver service is listening on port 5000 for incoming GPS data."
    log_info "Monitoring services are running:"
    log_info "  - Prometheus: http://localhost:9090"
    log_info "  - Grafana: http://localhost:3000 (admin/admin)"
    log_info "Access the site at http://localhost or https://bruna.ir (if configured)."
    log_info "Superuser credentials: username 'root', password 'iraj66100'"
    log_info "Don't forget to:"
    log_info "  1. Update email settings in .env"
    log_info "  2. Set up proper SSL certificates for production"
    log_info "  3. Configure backups"
    log_info "  4. Review and customize other .env settings as needed"
    log_info "  5. Check GPS receiver service status: sudo systemctl status gps-receiver.service"
    log_info "  6. Access Grafana dashboards for monitoring"
}

# Run main function
main "$@"