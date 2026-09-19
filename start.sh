#!/bin/sh

mkdir -p /config

if [ -f /etc/secrets/configuration.yaml ]; then
    cp /etc/secrets/configuration.yaml /config/configuration.yaml
fi

exec /init
