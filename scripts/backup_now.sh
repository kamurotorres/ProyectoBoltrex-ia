#!/usr/bin/env bash
# Boltrex (P2.25): respaldo manual de MongoDB a backups/ (en tu Mac o en el VPS).
#
#   scripts/backup_now.sh            # tu Mac (docker compose de desarrollo)
#   PROD=1 scripts/backup_now.sh     # VPS (usa el servicio `backup`, que además sube a Google Drive)
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
DB="${DB_NAME:-boltrex}"

if [[ "${PROD:-0}" == "1" ]]; then
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backup backup-now
  exit $?
fi

FILE="backups/${DB}-$(date +%Y%m%d-%H%M%S).archive.gz"
docker compose exec -T mongo sh -c \
  'mongodump --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db "'"${DB}"'" --archive --gzip' \
  > "$FILE"
echo "Respaldo creado: $FILE ($(du -h "$FILE" | cut -f1))"
