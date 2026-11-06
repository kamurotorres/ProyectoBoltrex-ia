#!/usr/bin/env bash
# Boltrex (P2.25): restaurar un respaldo de MongoDB (archivo .archive.gz de backups/).
#
#   scripts/restore_backup.sh backups/boltrex-20261105-030000.archive.gz          # tu Mac
#   PROD=1 scripts/restore_backup.sh backups/boltrex-20261105-030000.archive.gz   # VPS
#
# ⚠️ REEMPLAZA la base actual (DB_NAME) por la del respaldo. Pide escribir RESTAURAR para confirmar.
set -euo pipefail
cd "$(dirname "$0")/.."

FILE="${1:-}"
if [[ -z "$FILE" || ! -f "$FILE" ]]; then
  echo "Uso: scripts/restore_backup.sh <archivo .archive.gz>" >&2
  echo "Respaldos disponibles:" >&2
  ls -1t backups/*.archive.gz 2>/dev/null | head -20 >&2 || echo "  (ninguno en backups/)" >&2
  exit 1
fi
DB="${DB_NAME:-boltrex}"
COMPOSE=(docker compose)
[[ "${PROD:-0}" == "1" ]] && COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

echo "Vas a REEMPLAZAR la base '${DB}' con: ${FILE}"
if [[ "${CONFIRM:-}" != "RESTAURAR" ]]; then
  read -r -p "Escribe RESTAURAR para continuar: " answer
  [[ "$answer" == "RESTAURAR" ]] || { echo "Cancelado."; exit 1; }
fi

"${COMPOSE[@]}" exec -T mongo sh -c \
  'mongorestore --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --drop --archive --gzip --nsInclude "'"${DB}"'.*"' \
  < "$FILE"
echo "Restaurado '${DB}' desde ${FILE}. Reinicia el backend: ${COMPOSE[*]} restart backend"
