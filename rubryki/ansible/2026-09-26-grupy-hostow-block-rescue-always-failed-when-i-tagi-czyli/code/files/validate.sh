#!/bin/sh
# Walidator konfiguracji: port musi byc liczba. Wywolanie: sh validate.sh <plik>
if grep -Eq '^port = [0-9]+$' "$1"; then
  echo "config OK"
  exit 0
fi
echo "config INVALID: port nie jest liczba" >&2
exit 2
