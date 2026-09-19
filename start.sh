#!/bin/sh

set -eu

mkdir -p /config /backup

echo "=== Home Assistant B2 ==="

# Restore only when this is a fresh installation.
python3 /backup_b2.py restore || true

# Keep the Render Secret File available.
# Never overwrite a restored configuration.
if [ ! -f /config/configuration.yaml ] && [ -f /etc/secrets/configuration.yaml ]; then
    cp /etc/secrets/configuration.yaml /config/configuration.yaml
fi

# Start automatic backup watcher.
python3 /backup_b2.py watch &

echo "Starting Home Assistant..."

exec /init