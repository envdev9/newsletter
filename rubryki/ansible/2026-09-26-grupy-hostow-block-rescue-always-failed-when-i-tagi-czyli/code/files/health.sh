#!/bin/sh
# Healthcheck: 0 = OK, 3 = DEGRADED (debug logging), 2 = brak pliku. Wywolanie: sh health.sh <plik>
if [ ! -f "$1" ]; then
  echo "brak pliku konfiguracji"
  exit 2
fi
if grep -q '^log_level = DEBUG$' "$1"; then
  echo "degraded: wlaczone logowanie DEBUG"
  exit 3
fi
echo "healthy"
exit 0
