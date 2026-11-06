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
