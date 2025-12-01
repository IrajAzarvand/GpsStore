#!/bin/bash

# Create backups directory if it doesn't exist
mkdir -p ./backups

# Get timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="./backups/gpsstore_backup_$TIMESTAMP.sql"

echo "Starting database backup..."
echo "Target file: $BACKUP_FILE"

# Run pg_dump inside the db container
# We use sh -c to access environment variables inside the container
# POSTGRES_USER and POSTGRES_DB are set in the container by docker-compose
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' > "$BACKUP_FILE"

# Check if backup was successful
if [ $? -eq 0 ] && [ -s "$BACKUP_FILE" ]; then
    echo "✅ Backup completed successfully!"
    echo "📁 File size: $(du -h "$BACKUP_FILE" | cut -f1)"
    echo "📍 Location: $BACKUP_FILE"
else
    echo "❌ Backup failed or file is empty!"
    # Check if the file is empty (which happens on failure sometimes)
    if [ ! -s "$BACKUP_FILE" ]; then
        rm "$BACKUP_FILE"
    fi
    # Print container logs if failed
    echo "Last 20 lines of db logs:"
    docker compose logs --tail=20 db
    exit 1
fi
