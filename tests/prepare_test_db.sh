#!/usr/bin/env bash
# Prepara una BD de PRUEBA desde cero para las baterías tests/*_check.py.
#
#   DB_NAME=boltrex_sectest tests/prepare_test_db.sh
#
# - Solo acepta nombres boltrex_<algo>test: nunca toca la BD real `boltrex`.
# - Borra esa BD de prueba, carga RBAC + datos iniciales con el admin de prueba
#   (contraseña BOLTREX_ADMIN_PASSWORD, por defecto Prueba-Admin-2026) y le quita el
#   cambio obligatorio de contraseña para que las baterías puedan operar.
#   password_change_check.py vuelve a activarlo por su cuenta para probarlo.
# - Ejecutarlo ANTES de arrancar el backend de prueba: el backend crea los índices al
#   arrancar y, si la BD se borra con él corriendo, quedan sin crear (indexes_check falla).
set -euo pipefail
cd "$(dirname "$0")/.."

: "${DB_NAME:?Define DB_NAME=boltrex_<algo>test}"
if [[ ! "$DB_NAME" =~ ^boltrex_[a-z0-9]+test$ ]]; then
  echo "Negado: DB_NAME debe ser boltrex_<algo>test (recibido: $DB_NAME)" >&2
  exit 1
fi
# P2.25: Mongo con contraseña → si no viene MONGO_URL, se arma con el administrador de `.env`.
if [[ -z "${MONGO_URL:-}" ]]; then
  source tests/test_env.sh >/dev/null
fi
export MONGO_URL="${MONGO_URL:-mongodb://localhost:27017/?directConnection=true}"
export ADMIN_INITIAL_PASSWORD="${BOLTREX_ADMIN_PASSWORD:-Prueba-Admin-2026}"
PY="${PY:-backend/.venv/bin/python}"

$PY - <<'EOF'
import os, pymongo
pymongo.MongoClient(os.environ["MONGO_URL"]).drop_database(os.environ["DB_NAME"])
EOF
$PY scripts/init_rbac.py >/dev/null
$PY scripts/seed_data.py | tail -1
$PY - <<'EOF'
import os, pymongo
db = pymongo.MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
db.users_extended.update_one({"email": "admin@boltrex.com"}, {"$set": {"must_change_password": False}})
print(f"BD de prueba {os.environ['DB_NAME']} lista (admin@boltrex.com / BOLTREX_ADMIN_PASSWORD).")
EOF
