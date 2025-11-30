#!/bin/bash

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker and try again."
    exit 1
fi

echo "Stopping and removing all Docker containers and networks related to the project..."
docker compose down --volumes --remove-orphans

echo "Removing Docker images associated with the project..."
docker compose down --rmi all

echo "Deleting the SQLite database file (db.sqlite3) if it exists..."
if [ -f "db.sqlite3" ]; then
    rm -f db.sqlite3
    echo "Database file deleted."
else
    echo "Database file not found, skipping deletion."
fi

echo "Rebuilding and starting the Docker services from scratch..."
docker compose up --build -d

echo "Restarting gps-receiver systemd service..."
sudo systemctl restart gps-receiver
if [ $? -ne 0 ]; then
    echo "Error: Failed to restart gps-receiver service."
    exit 1
fi

echo "Waiting for database to be ready..."
sleep 20
echo "Verifying database connection..."
for i in {1..30}; do
    if docker compose exec -T db pg_isready -U gpsstore_user -d gpsstore_prod &> /dev/null; then
        echo "Database is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Database failed to become ready in time"
        exit 1
    fi
    echo -n "."
    sleep 2
done

echo "Running database migrations..."
docker compose exec -T web python manage.py migrate

echo "Collecting static files..."
docker compose exec -T web python manage.py collectstatic --noinput

echo "Creating Django superuser..."
docker compose exec -T web python manage.py createsuperuser --noinput || echo "Superuser may already exist or creation failed."

echo "Quick redeployment completed successfully."