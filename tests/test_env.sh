#!/usr/bin/env bash
# Boltrex (P2.25): variables para correr las pruebas contra el Mongo de Docker (con contraseña).
#   source tests/test_env.sh
# Exporta MONGO_URL con el usuario administrador de `.env` (las pruebas crean y borran BD
# boltrex_<x>test, algo que el usuario de la app no puede hacer). Nunca toca la BD `boltrex`.
_root="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
if [[ -f "$_root/.env" ]]; then
  _u=$(grep -E '^MONGO_ROOT_USER=' "$_root/.env" | cut -d= -f2-)
  _p=$(grep -E '^MONGO_ROOT_PASSWORD=' "$_root/.env" | cut -d= -f2-)
  export MONGO_URL="mongodb://${_u}:${_p}@localhost:27017/?directConnection=true&authSource=admin"
  echo "MONGO_URL de pruebas listo (usuario ${_u})."
else
  echo "No encuentro $_root/.env: créalo desde .env.example." >&2
fi
unset _root _u _p
