#!/bin/sh
# Udawana migracja bazy: pierwszy raz "stosuje", potem nic do roboty.
# Wywolanie: sh migrate.sh <katalog>
marker="$1/migrated.marker"
if [ -f "$marker" ]; then
  echo "nothing to do"
  exit 0
fi
touch "$marker"
echo "applied 1 migration"
exit 0
