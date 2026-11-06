# Boltrex

[![CI](https://github.com/kamurotorres/ProyectoBoltrex-ia/actions/workflows/ci.yml/badge.svg)](https://github.com/kamurotorres/ProyectoBoltrex-ia/actions/workflows/ci.yml)

Sistema de **punto de venta (POS) e inventario**: productos con listas de precios, clientes, proveedores, compras, ventas de contado y a crédito (Fios), devoluciones, control de caja con arqueo, reportes, dashboard, auditoría y roles con permisos.

| Parte | Tecnología |
|---|---|
| Backend | Python · FastAPI · MongoDB 6 (replica set, transacciones) |
| Frontend | React 19 · Tailwind · shadcn/ui, servido por nginx |
| Producción | Docker Compose · Caddy (HTTPS automático) · respaldos diarios |

## Levantar en local

```bash
cp .env.example .env                    # contraseñas de MongoDB
cp backend/.env.example backend/.env    # secreto de sesiones y contraseña inicial del admin
docker compose up -d --build
scripts/seed_docker.sh                  # módulos, roles, admin y catálogos (primera vez)
```

App en http://localhost:3000 · API en http://localhost:8000/docs · usuario `admin@boltrex.com` con la contraseña de `ADMIN_INITIAL_PASSWORD` (se pide cambiarla al entrar).

## Documentación

| Tema | Archivo |
|---|---|
| Cómo levantar el proyecto, variables y problemas frecuentes | [memorias_claude/LEVANTAR_PROYECTO.md](memorias_claude/LEVANTAR_PROYECTO.md) |
| Arquitectura, módulos, endpoints y convenciones | [memorias_claude/ARQUITECTURA_BIG_PICTURE.md](memorias_claude/ARQUITECTURA_BIG_PICTURE.md) |
| Despliegue en Hostinger (VPS) con `boltrex.online` | [memorias_claude/DESPLIEGUE_HOSTINGER.md](memorias_claude/DESPLIEGUE_HOSTINGER.md) |
| Mejoras realizadas y pendientes | [memorias_claude/BACKLOG_MEJORAS.md](memorias_claude/BACKLOG_MEJORAS.md) |
| Funcionalidades del negocio | [README_BOLTREX.md](README_BOLTREX.md) |

## Pruebas

Todas las baterías de integración con un solo comando (Mongo de Docker levantado; usa BD temporales y nunca toca `boltrex`):

```bash
scripts/run_all_tests.sh              # todas (≈ lo mismo que corre el CI)
scripts/run_all_tests.sh credit cash  # solo algunas
```

El CI de GitHub Actions (`.github/workflows/ci.yml`) las corre en cada push, junto con el lint y los builds de las imágenes.
Detalle en [LEVANTAR_PROYECTO.md §6](memorias_claude/LEVANTAR_PROYECTO.md).
