#!/bin/bash
set -e

# This script runs as root to fix permissions, then switches to app user

# Wait for database to be ready
echo "Waiting for database..."
while ! python -c "import psycopg2; psycopg2.connect(host='${DATABASE_HOST:-db}', database='${DATABASE_NAME}', user='${DATABASE_USER}', password='${DATABASE_PASSWORD}')" 2>/dev/null; do
    echo "Database is unavailable - sleeping"
    sleep 1
done

echo "Database is up - executing commands"

# Fix permissions for mounted volumes (run as root)
echo "Fixing permissions..."
mkdir -p /app/staticfiles /app/media /app/logs
chown -R app:app /app/staticfiles /app/media /app/logs || true
chmod -R 755 /app/staticfiles /app/media /app/logs || true

# Collect static files as app user
echo "Collecting static files..."
su -s /bin/bash app -c "cd /app && python manage.py collectstatic --noinput" || {
    echo "Warning: collectstatic failed, trying with root..."
    # If collectstatic fails, try to fix permissions and retry
    chmod -R 777 /app/staticfiles || true
    su -s /bin/bash app -c "cd /app && python manage.py collectstatic --noinput"
}

echo "Running migrations..."
su -s /bin/bash app -c "cd /app && python manage.py migrate --noinput"

# Switch to app user and execute the main command
echo "Starting application as app user..."
# Change to app directory and switch user
cd /app
# Use runuser if available, otherwise use su with proper quoting
if command -v runuser >/dev/null 2>&1; then
    exec runuser -u app -- "$@"
else
    # Build command with proper quoting
    CMD=""
    for arg in "$@"; do
        # Escape single quotes and wrap in single quotes
        escaped_arg=$(printf '%s\n' "$arg" | sed "s/'/'\"'\"'/g")
        CMD="$CMD '$escaped_arg'"
    done
    exec su -s /bin/sh app -c "cd /app && exec $CMD"
fi

