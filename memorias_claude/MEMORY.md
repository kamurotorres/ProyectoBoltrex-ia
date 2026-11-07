# Índice de memorias de Claude — Boltrex

Una línea por memoria. Cada memoria es un archivo `.md` en esta carpeta.

- [Boltrex architecture](boltrex-architecture.md) — estado actual (P0, P1, P2 ✅, mantenimiento 7/7 ✅, formato colombiano, Compras estilo POS, menú por grupos; main `1e7dc50`), **«Para retomar» → 2026-11-08 verificar la app módulo por módulo**, git, pendientes del usuario, reglas (responder en español)
- [Big picture de arquitectura](ARQUITECTURA_BIG_PICTURE.md) — v2: rutas, colecciones, flujos y CONVENCIONES (capas, errores, formularios RHF+zod, dinero `core/money`/`lib/format`, `components/commerce`, menú en `lib/access.js`, pruebas unitarias)
- [Cómo levantar el proyecto](LEVANTAR_PROYECTO.md) — Docker / local, variables de entorno (`.env` raíz + `backend/.env`), seeding, problemas conocidos; §6 cómo correr las pruebas (pytest + `scripts/run_all_tests.sh`)
- [Despliegue en Hostinger](DESPLIEGUE_HOSTINGER.md) — producción en VPS KVM 2 con `boltrex.online`: SSH, ufw, DNS, secretos, Google Drive (rclone), levantar, respaldos, actualizar, restaurar
- [Backlog de mejoras](BACKLOG_MEJORAS.md) — P0, P1, P2 ✅ + mantenimiento 7/7 ✅ + P2.37 Compras + P2.39 menú; pendientes: P2.23 E2E, P2.38 cámara del celular, P3; bitácora detallada; UNA mejora a la vez, propuesta antes de tocar código y autorización del usuario
- [Mensajes al usuario](mensajes-al-usuario.md) — REGLA: toda acción bloqueada muestra en pantalla el motivo (detail en backend + getErrorMessage en frontend)
- [Entorno local del usuario](entorno-local.md) — quirks de la Mac del usuario (Python, npm, brew/Xcode, Docker) + cómo probar la app real en Chrome headless con API simulada
