#!/bin/bash
# Fix Docker entrypoint script line endings and rebuild containers

echo "=== Fixing Docker Entrypoint Line Endings ==="

# Check if dos2unix is available
if command -v dos2unix &> /dev/null; then
    echo "Converting docker-entrypoint.sh to Unix line endings..."
    dos2unix docker-entrypoint.sh
elif command -v sed &> /dev/null; then
    echo "Using sed to convert line endings..."
    sed -i 's/\r$//' docker-entrypoint.sh
else
    echo "Warning: Neither dos2unix nor sed found. Trying perl..."
    perl -pi -e 's/\r\n/\n/g' docker-entrypoint.sh
fi

echo "✓ Line endings fixed"

# Ensure script is executable
chmod +x docker-entrypoint.sh
echo "✓ Set executable permissions"

# Rebuild containers
echo ""
echo "=== Rebuilding Containers ==="
docker compose down
docker compose build --no-cache web
docker compose up -d

echo ""
echo "=== Checking Status ==="
sleep 5
docker compose ps

echo ""
echo "=== Checking Web Container Logs ==="
docker compose logs web --tail=30

echo ""
echo "=== Done! ==="
echo "If the web container is now running properly, try accessing your site again."