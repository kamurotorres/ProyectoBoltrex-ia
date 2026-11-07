---
name: entorno-local
description: Quirks de la Mac del usuario (macOS 27 arm64) que afectan levantar Boltrex
metadata:
  type: project
---

Estado al 2026-11-03:
- macOS 27, Apple Silicon. Python por defecto 3.14 → usar `/opt/homebrew/bin/python3.12` (venv en `backend/.venv` ya creado con deps).
- Caché de npm del usuario corrupta (EEXIST) → instalar con `--cache` alternativo. `frontend/node_modules` ya instalado.
- Homebrew no instala MongoDB: Xcode 26.5 demasiado viejo para macOS 27 (taps mongodb/brew ya marcados como confiables).
- Docker Desktop instalado; el CLI puede no estar en PATH del shell de Claude → usar `/Applications/Docker.app/Contents/Resources/bin/docker`.
- MongoDB oficial 8.0.34 descargado (no ejecutado) en `~/mongodb/`; el auto-mode bloqueó ejecutarlo.
- `backend/.env` creado localmente con JWT aleatorio.
- **2026-11-03: proyecto levantado con Docker y funcionando** (mongo + backend + frontend, seeding hecho, login admin OK). Volumen `proyectoboltrex-ia_mongo_data` ya tiene datos: no repetir seeding salvo tras `docker compose down -v`.

**Why:** evita repetir el diagnóstico del entorno.
**How to apply:** preferir el camino Docker de [[LEVANTAR_PROYECTO]]; el usuario prefiere ejecutar él mismo los comandos de instalación/arranque.

## Probar la app real en un navegador (sin tocar datos) — 2026-11-07
- Hay Google Chrome en `/Applications/Google Chrome.app` y el módulo `ws` en `frontend/node_modules`: se puede abrir el frontend de Docker (`http://localhost:3000`) en Chrome headless (`--remote-debugging-port`) y controlarlo por CDP. Con `Fetch.enable` (`*/api/*`) se **simulan** las respuestas de la API (p. ej. `/auth/me` con un admin de prueba + `localStorage.token`), así no se usa el backend ni datos ni contraseñas reales. Si la app llama al backend en otro origen, responder también los OPTIONS con `Access-Control-Allow-Headers: Authorization, Content-Type`.
- Sirve para reproducir problemas visuales/de interacción (`Input.dispatchMouseEvent` mouseWheel/clics, `Runtime.evaluate` para medir). Se usó para el «el menú no baja con la rueda»: en Chrome funcionaba en todos los estados → era cómo lo estaba usando el usuario (no había error).
- Playwright NO está instalado (solo sus navegadores en `~/Library/Caches/ms-playwright`): para probar WebKit/Firefox habría que instalar `playwright-core` en el scratchpad.
