# Boltrex (P2.25): respaldos de MongoDB. Usa la imagen oficial de Mongo (trae mongodump/mongorestore)
# y añade rclone para subir una copia a Google Drive (fuera del VPS).
FROM mongo:6.0

RUN apt-get update \
    && apt-get install -y --no-install-recommends rclone ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY backup-now.sh /usr/local/bin/backup-now
COPY backup-loop.sh /usr/local/bin/backup-loop
RUN chmod +x /usr/local/bin/backup-now /usr/local/bin/backup-loop

ENV RCLONE_CONFIG=/config/rclone/rclone.conf
ENTRYPOINT ["/usr/local/bin/backup-loop"]
