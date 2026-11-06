#!/bin/sh
# Boltrex (P2.25): un respaldo ahora mismo.
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backup backup-now
# - Archivo: /backups/boltrex-AAAAMMDD-HHMMSS.archive.gz (mongodump comprimido de la base DB_NAME).
# - Borra los respaldos locales con más de BACKUP_KEEP_DAYS días.
# - Si existe rclone.conf y RCLONE_REMOTE (p. ej. gdrive:boltrex-backups), sube la copia y borra
#   en el remoto lo que tenga más de RCLONE_KEEP_DAYS días.
set -eu

DB="${DB_NAME:-boltrex}"
KEEP="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="/backups/${DB}-${STAMP}.archive.gz"

echo "[backup] $(date '+%Y-%m-%d %H:%M:%S %Z') iniciando respaldo de '${DB}'..."
mongodump --host mongo --port 27017 \
  --username "${MONGO_ROOT_USER}" --password "${MONGO_ROOT_PASSWORD}" --authenticationDatabase admin \
  --db "${DB}" --archive="${FILE}.tmp" --gzip --quiet
mv "${FILE}.tmp" "${FILE}"
echo "[backup] OK: ${FILE} ($(du -h "${FILE}" | cut -f1))"

# Retención local
find /backups -maxdepth 1 -name "${DB}-*.archive.gz" -mtime +"${KEEP}" -print -delete | sed 's/^/[backup] borrado (antiguo): /' || true

# Copia fuera del VPS
if [ -n "${RCLONE_REMOTE:-}" ] && [ -f "${RCLONE_CONFIG:-/config/rclone/rclone.conf}" ]; then
  if rclone copy "${FILE}" "${RCLONE_REMOTE}" --quiet; then
    echo "[backup] copia subida a ${RCLONE_REMOTE}"
    rclone delete "${RCLONE_REMOTE}" --min-age "${RCLONE_KEEP_DAYS:-30}d" --include "${DB}-*.archive.gz" --quiet || true
  else
    echo "[backup] ⚠️ NO se pudo subir la copia a ${RCLONE_REMOTE}: revisa rclone.conf (el respaldo local sí se hizo)." >&2
    exit 2
  fi
else
  echo "[backup] ⚠️ sin copia fuera del VPS: falta RCLONE_REMOTE o deploy/backup/rclone/rclone.conf (ver guía)."
fi
