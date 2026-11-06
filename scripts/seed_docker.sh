#!/usr/bin/env bash
# Boltrex (P2.25): carga inicial (módulos/roles/permisos + admin y catálogos) DENTRO de Docker,
# usando la imagen del backend. Sirve igual en tu Mac y en el VPS (donde Mongo no publica puertos).
#
#   scripts/seed_docker.sh            # tu Mac
#   PROD=1 scripts/seed_docker.sh     # VPS
#
# Requiere ADMIN_INITIAL_PASSWORD en backend/.env (contraseña del primer admin, se pide cambiarla
# al entrar). Es idempotente: si ya existen, no duplica nada.
set -euo pipefail
cd "$(dirname "$0")/.."
COMPOSE=(docker compose)
[[ "${PROD:-0}" == "1" ]] && COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)
[[ -n "${COMPOSE_PROJECT_NAME:-}" ]] && COMPOSE+=(-p "$COMPOSE_PROJECT_NAME")

for script in init_rbac.py seed_data.py; do
  echo "== ${script}"
  "${COMPOSE[@]}" run --rm --no-deps -T -v "$PWD":/repo -w /repo backend python "scripts/${script}" 2>&1 \
    | grep -v -E "bcrypt|__about__|^Traceback|^  File|^    |AttributeError: module 'bcrypt'" || true
done
echo "Listo. Entra con admin@boltrex.com y la contraseña de ADMIN_INITIAL_PASSWORD."
