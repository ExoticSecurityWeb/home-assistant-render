#!/bin/sh

set -eu

mkdir -p /config /backup

echo "=== Home Assistant B2 ==="

# Restauration B2 désactivée temporairement pour tester le démarrage HTTP.
echo "B2: restauration désactivée pour ce test."

# Configuration Render
if [ -f /etc/secrets/configuration.yaml ]; then
    cp /etc/secrets/configuration.yaml /config/configuration.yaml
fi

echo "=== Configuration HTTP ==="
grep -A6 '^http:' /config/configuration.yaml || true
echo "=========================="

# Surveillance et sauvegardes B2
python3 /backup_b2.py watch &

echo "Starting Home Assistant..."

exec /init