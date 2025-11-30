# Use Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=gps_store.settings

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    libpq-dev \
    nginx \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Create directories for static files and media
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Copy and set permissions for entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app \
    && chmod -R 755 /app/logs /app/staticfiles /app/media

# Change entrypoint script ownership to root
RUN chown root:root /docker-entrypoint.sh

# Note: Entrypoint script runs as root to fix permissions, then switches to app user
# collectstatic is now run in entrypoint script after volumes are mounted
# This ensures proper permissions for mounted volumes

# Keep as root for entrypoint (it will switch to app user)
# USER app

# Expose port
EXPOSE 8000
EXPOSE 5000

# Use entrypoint script
ENTRYPOINT ["/docker-entrypoint.sh"]

# Run gunicorn with config file
CMD ["gunicorn", "--config", "gunicorn.conf.py", "gps_store.asgi:application"]