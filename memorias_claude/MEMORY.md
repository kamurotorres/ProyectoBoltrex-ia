# Índice de memorias de Claude — Boltrex

Una línea por memoria. Cada memoria es un archivo `.md` en esta carpeta.

- [Boltrex architecture](boltrex-architecture.md) — estado actual (P0+P1, P2.25/27/28/29/31 ✅), «Para retomar», pendientes del usuario, reglas de trabajo
- [Big picture de arquitectura](ARQUITECTURA_BIG_PICTURE.md) — v2: rutas, colecciones, flujos, convenciones; §12 inventario de todo lo agregado en P0+P1
- [Cómo levantar el proyecto](LEVANTAR_PROYECTO.md) — Docker / local, variables de entorno (`.env` raíz + `backend/.env`), seeding, problemas conocidos; §6 cómo correr las pruebas
- [Despliegue en Hostinger](DESPLIEGUE_HOSTINGER.md) — producción en VPS KVM 2 con `boltrex.online`: SSH, ufw, DNS, secretos, Google Drive (rclone), levantar, respaldos, actualizar, restaurar
- [Backlog de mejoras](BACKLOG_MEJORAS.md) — P0 y P1 ✅ (P1.40 resuelto en P2.31), P2.25, P2.27, P2.28, P2.29 y P2.31 ✅ + mejora de precios por lista; bitácora detallada de cada punto; UNA mejora a la vez, propuesta antes de tocar código y autorización del usuario
- [Mensajes al usuario](mensajes-al-usuario.md) — REGLA: toda acción bloqueada muestra en pantalla el motivo (detail en backend + getErrorMessage en frontend)
- [Entorno local del usuario](entorno-local.md) — quirks de la Mac del usuario (Python, npm, brew/Xcode, Docker)
