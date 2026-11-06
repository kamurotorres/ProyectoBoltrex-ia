#!/bin/sh
# Boltrex (P2.25): ejecuta backup-now todos los días a las BACKUP_HOUR:00 (zona TZ).
# Un fallo se registra en el log del contenedor y se reintenta al día siguiente (no se detiene).
set -u
HOUR="${BACKUP_HOUR:-3}"
echo "[backup] programado a diario a las ${HOUR}:00 (${TZ:-UTC}); se conservan ${BACKUP_KEEP_DAYS:-14} días."

while true; do
  now=$(date +%s)
  next=$(date -d "today ${HOUR}:00" +%s)
  [ "$next" -le "$now" ] && next=$(date -d "tomorrow ${HOUR}:00" +%s)
  echo "[backup] próximo respaldo: $(date -d "@${next}" '+%Y-%m-%d %H:%M %Z')"
  sleep $((next - now))
  /usr/local/bin/backup-now || echo "[backup] ❌ el respaldo falló (código $?); se reintentará mañana." >&2
  sleep 61
done
