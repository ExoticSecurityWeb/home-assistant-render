#!/bin/sh

set -eu

mkdir -p /config /backup

echo "=== Home Assistant B2 ==="

# Restaurer la configuration depuis B2
python3 /backup_b2.py restore || true

# La configuration Render est prioritaire
if [ -f /etc/secrets/configuration.yaml ]; then
    cp /etc/secrets/configuration.yaml /config/configuration.yaml
fi

echo "=== Configuration HTTP ==="
grep -A5 '^http:' /config/configuration.yaml || true
echo "=========================="

# Lancer la surveillance B2
python3 /backup_b2.py watch &

echo "Starting Home Assistant..."

exec /init