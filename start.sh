#!/bin/sh

set -eu

mkdir -p /config /backup

echo "=== Home Assistant B2 ==="

# Restaurer depuis B2
python3 /backup_b2.py restore || true

# Configuration Render
if [ -f /etc/secrets/configuration.yaml ]; then
    cp /etc/secrets/configuration.yaml /config/configuration.yaml
fi

# Forcer le port Render dans la configuration HA
PORT="${PORT:-10000}"

python3 - "$PORT" <<'PY'
import sys
from pathlib import Path

port = sys.argv[1]
path = Path("/config/configuration.yaml")

text = path.read_text() if path.exists() else ""

if "http:" not in text:
    text += "\nhttp:\n"

lines = text.splitlines()
result = []
in_http = False
server_port_found = False
server_host_found = False

for line in lines:
    stripped = line.strip()

    if stripped == "http:":
        in_http = True
        result.append(line)
        continue

    if in_http and line and not line.startswith((" ", "\t")):
        in_http = False

    if in_http and stripped.startswith("server_port:"):
        result.append("  server_port: " + port)
        server_port_found = True
    elif in_http and stripped.startswith("server_host:"):
        result.append("  server_host: 0.0.0.0")
        server_host_found = True
    else:
        result.append(line)

if not server_port_found:
    for i, line in enumerate(result):
        if line.strip() == "http:":
            result.insert(i + 1, "  server_port: " + port)
            break

if not server_host_found:
    for i, line in enumerate(result):
        if line.strip() == "http:":
            result.insert(i + 2, "  server_host: 0.0.0.0")
            break

path.write_text("\n".join(result) + "\n")
PY

echo "=== Port Home Assistant ==="
grep -A4 '^http:' /config/configuration.yaml || true
echo "============================"

# Backup B2
python3 /backup_b2.py watch &

echo "Starting Home Assistant..."

exec /init