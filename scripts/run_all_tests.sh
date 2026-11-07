#!/usr/bin/env bash
# Boltrex (P2.24): corre TODAS las baterías de pruebas de integración con un solo comando.
# Lo usa el CI de GitHub Actions y sirve igual en el Mac:
#
#   scripts/run_all_tests.sh                 # todas (primero las unitarias de pytest, fase 7)
#   scripts/run_all_tests.sh credit cash     # solo esas (de la fase principal)
#   BOLTREX_SKIP_UNIT=1 scripts/run_all_tests.sh   # sin las unitarias (el CI las corre en su propio paso)
#
# - Nunca toca la BD real `boltrex`: usa BD temporales boltrex_ci*test y las borra al terminar.
# - Mongo: usa MONGO_URL si viene definido (CI); si no, el de tests/test_env.sh (Mongo de Docker con contraseña).
# - Arranca su propio backend de prueba en el puerto 8001 (o BOLTREX_TEST_PORT) y lo apaga.
# - session_check y login_throttle_check necesitan un backend con tiempos cortos: van en fases aparte.
# - Si algo falla, muestra las últimas líneas del log del backend y termina con código ≠ 0.
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PY:-backend/.venv/bin/python}"
UVICORN="${UVICORN:-backend/.venv/bin/uvicorn}"
PORT="${BOLTREX_TEST_PORT:-8001}"
API="http://localhost:${PORT}/api"
LOGDIR="${BOLTREX_TEST_LOGS:-$ROOT/.test-logs}"
mkdir -p "$LOGDIR"
rm -f "$LOGDIR"/*.log   # solo los logs de esta corrida

if [[ -z "${MONGO_URL:-}" ]]; then
  # shellcheck disable=SC1091
  source tests/test_env.sh >/dev/null
fi
export MONGO_URL="${MONGO_URL:-mongodb://localhost:27017/?directConnection=true}"

# Orden de la fase principal: factory_reset borra los datos de la BD → siempre de última.
MAIN=(indexes counters transactions stock_concurrency returns security_rbac references user_protection
      password_change sales_report client_identity pricing pagination dates audit dashboard product_price_lists
      cash credit adjustments alerts exports import purchases testers factory_reset)
if [[ $# -gt 0 ]]; then MAIN=("$@"); SPECIAL=0; else SPECIAL=1; fi

declare -a RESULTS=()
FAILED=0
BACKEND_PID=""

cleanup() {
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null && wait "$BACKEND_PID" 2>/dev/null
  "$PY" - <<'EOF' 2>/dev/null
import os, pymongo
c = pymongo.MongoClient(os.environ["MONGO_URL"], serverSelectionTimeoutMS=3000)
for n in c.list_database_names():
    if n.startswith("boltrex_ci") and n.endswith("test"):
        c.drop_database(n)
EOF
}
trap cleanup EXIT

start_backend() {   # $1 = DB, resto = VAR=valor para el backend
  local db="$1"; shift
  DB_NAME="$db" tests/prepare_test_db.sh >/dev/null || { echo "No se pudo preparar la BD $db"; exit 1; }
  env DB_NAME="$db" "$@" "$UVICORN" main:app --app-dir backend --port "$PORT" > "$LOGDIR/backend_$db.log" 2>&1 &
  BACKEND_PID=$!
  for _ in $(seq 1 60); do
    curl -sf "http://localhost:${PORT}/" >/dev/null 2>&1 && return 0
    kill -0 "$BACKEND_PID" 2>/dev/null || break
    sleep 0.5
  done
  echo "El backend de prueba no arrancó. Log:"; tail -50 "$LOGDIR/backend_$db.log"; exit 1
}

add_result() { RESULTS+=("$1"); echo "$1"; }

stop_backend() {
  [[ -n "$BACKEND_PID" ]] && kill "$BACKEND_PID" 2>/dev/null && wait "$BACKEND_PID" 2>/dev/null
  BACKEND_PID=""
}

run_battery() {   # $1 = nombre, $2 = DB, resto = VAR=valor para la prueba
  local name="$1" db="$2"; shift 2
  local out="$LOGDIR/${name}.log" start=$SECONDS
  env BOLTREX_API="$API" DB_NAME="$db" "$@" "$PY" "tests/${name}_check.py" > "$out" 2>&1
  local code=$? summary
  summary="$(grep -E '[0-9]+/[0-9]+ (pruebas )?OK' "$out" | tail -1)"
  if [[ $code -eq 0 ]]; then
    add_result "✅ ${name}: ${summary:-OK} ($((SECONDS - start)) s)"
  else
    FAILED=1
    add_result "❌ ${name}: ${summary:-código $code} ($((SECONDS - start)) s)"
    echo "::group::❌ ${name} — fallos"
    grep -E "^FAIL|Traceback|Error" -A3 "$out" | head -60
    echo "::endgroup::"
  fi
}

if [[ $SPECIAL -eq 1 && -z "${BOLTREX_SKIP_UNIT:-}" ]]; then
  echo "== Pruebas unitarias (pytest, sin Mongo)"
  start=$SECONDS
  if "$PY" -m pytest > "$LOGDIR/unit.log" 2>&1; then
    add_result "✅ unit (pytest): $(tail -1 "$LOGDIR/unit.log" | sed -E 's/=//g; s/^ +| +$//g') ($((SECONDS - start)) s)"
  else
    FAILED=1; add_result "❌ unit (pytest): $(tail -1 "$LOGDIR/unit.log" | sed -E 's/=//g; s/^ +| +$//g')"
    grep -E "^(FAILED|ERROR)" "$LOGDIR/unit.log" | head -30
  fi
fi

echo "== Fase principal (${#MAIN[@]} baterías)"
start_backend boltrex_cimaintest
for t in "${MAIN[@]}"; do run_battery "$t" boltrex_cimaintest; done
stop_backend

if [[ $SPECIAL -eq 1 ]]; then
  echo "== Sesiones (inactividad corta)"
  SESS=(SESSION_IDLE_MINUTES=0.1 ACCESS_TOKEN_EXPIRE_MINUTES=0.3)
  start_backend boltrex_cisesstest "${SESS[@]}"
  run_battery session boltrex_cisesstest "${SESS[@]}"
  stop_backend

  echo "== Bloqueo de login (tiempos cortos)"
  # Bloqueo de 6 s / ventana de 12 s: con 3 s la prueba de 20 intentos simultáneos quedaba justa en
  # máquinas lentas (el CI) y fallaba de forma intermitente.
  LT=(LOGIN_LOCK_MINUTES=0.1 LOGIN_WINDOW_MINUTES=0.2)
  start_backend boltrex_ciltest "${LT[@]}"
  run_battery login_throttle boltrex_ciltest "${LT[@]}"
  stop_backend

  if command -v node >/dev/null && [[ -d frontend/node_modules/@babel/core ]]; then
    echo "== Frontend sin navegador (permisos del menú, sintaxis e imports, formatos, carrito, formularios, lint)"
    for fc in "frontend_access:node tests/frontend_access_check.js" "frontend_syntax:node tests/frontend_syntax_check.js" \
              "frontend_format:node tests/frontend_format_check.js" \
              "frontend_cart:node tests/frontend_cart_check.js" "frontend_forms:node tests/frontend_forms_check.js" \
              "frontend_forms_render:node tests/frontend_forms_render_check.js" "frontend_lint:bash tests/frontend_lint_check.sh"; do
      name="${fc%%:*}"; cmd="${fc#*:}"
      if $cmd > "$LOGDIR/$name.log" 2>&1; then
        add_result "✅ $name: $(tail -1 "$LOGDIR/$name.log")"
      else
        FAILED=1; add_result "❌ $name"; grep -E "FAIL|error" "$LOGDIR/$name.log" | head -20
      fi
    done
  fi
fi

echo
echo "================ Resumen ================"
printf '%s\n' "${RESULTS[@]}"
if [[ -n "${GITHUB_STEP_SUMMARY:-}" ]]; then
  { echo "### Pruebas de integración"; printf -- '- %s\n' "${RESULTS[@]}"; } >> "$GITHUB_STEP_SUMMARY"
fi
if [[ $FAILED -ne 0 ]]; then
  echo
  echo "Hubo fallos. Últimas líneas del backend:"
  tail -40 "$LOGDIR"/backend_*.log 2>/dev/null | grep -v "bcrypt\|__about__" | tail -40
  exit 1
fi
echo "Todo en verde."
