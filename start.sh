#!/bin/sh

set -eu

mkdir -p /config /backup

echo "=== Home Assistant B2 ==="

# Restore the latest backup.
python3 /backup_b2.py restore || true

# Always use the Render configuration.yaml.
# This contains the HTTP/port configuration required by Render.
if [ -f /etc/secrets/configuration.yaml ]; then
    cp /etc/secrets/configuration.yaml /config/configuration.yaml
fi

# Start automatic backup watcher.
python3 /backup_b2.py watch &

echo "Starting Home Assistant..."

exec /init