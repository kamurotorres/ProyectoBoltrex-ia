#!/usr/bin/env bash
# Lint del frontend (mantenimiento fase 4): falla con nombres sin definir; avisa imports sin usar.
#   tests/frontend_lint_check.sh
set -uo pipefail
cd "$(dirname "$0")/../frontend"
out=$(npx --no-install eslint -c ../tests/eslint.frontend.cjs --ignore-pattern "src/components/ui/**" src 2>&1 | grep -v "Definition for rule")
errors=$(printf '%s\n' "$out" | grep -cE "^\s+[0-9]+:[0-9]+\s+error" || true)
warnings=$(printf '%s\n' "$out" | grep -cE "^\s+[0-9]+:[0-9]+\s+warning" || true)
printf '%s\n' "$out" | grep -E "^/|error" | grep -B1 -E "\serror\s" || true
echo
if [ "$errors" -gt 0 ]; then echo "FAIL $errors error(es) de lint"; echo "0/1 pruebas OK"; exit 1; fi
echo "OK sin errores ($warnings aviso(s) de variables sin usar)"; echo "1/1 pruebas OK"
