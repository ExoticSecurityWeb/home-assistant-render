#!/bin/sh

set -eu

mkdir -p /config /backup

echo "=== Home Assistant B2 ==="

# Restaurer uniquement si l'installation est vide.
python3 /backup_b2.py restore || true

# Configuration Render utilisée par Home Assistant.
if [ ! -f /config/configuration.yaml ] && [ -f /etc/secrets/configuration.yaml ]; then
    cp /etc/secrets/configuration.yaml /config/configuration.yaml
fi

# Backup automatique B2.
python3 /backup_b2.py watch &

echo "Starting Home Assistant..."

exec /init