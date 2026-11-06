---
name: boltrex-architecture
description: Boltrex POS/inventario (FastAPI+Mongo backend, React frontend, nacido en Emergent) — estado actual, reglas de trabajo con el usuario y siguiente paso; detalle en ARQUITECTURA_BIG_PICTURE.md
metadata:
  type: project
---

Proyecto principal: `ProyectoBoltrex-ia/` = repo con 2 apps desplegables (`backend/` FastAPI + motor + MongoDB replica set `rs0`, `frontend/` React 19 CRA/CRACO + shadcn servido por nginx con proxy `/api`) + scripts de seeding, pruebas de integración y docs. Generado originalmente en Emergent; el backend era un `server.py` monolítico partido con `split_server.py`.

**Leer antes de trabajar:** [[ARQUITECTURA_BIG_PICTURE]] (v2; §12 = inventario de todo lo agregado en P0+P1), [[LEVANTAR_PROYECTO]] (variables de entorno, §6 cómo correr las pruebas), [[BACKLOG_MEJORAS]] (bitácora detallada por punto).

## Estado (2026-11-04)
- **P0 (1–7) y P1 (8–19) completos**, más el complemento de paginación en Categorías, Listas de precios, Formas de pago y Facturas. **P1.40 ✅** resuelto en P2.31 (excedente abonado → efectivo desde la caja).
- Hecho, en una línea por bloque: RBAC en backend · transacciones, stock atómico, devoluciones validadas, consecutivos, referencias por nombre, índices únicos · anti-escalada · límite de login · sin `admin123` (`ADMIN_INITIAL_PASSWORD` + cambio obligatorio) · sesiones en servidor con inactividad 1 h y máx. 12 h · auditoría de todo el sistema (solo Administrador) · rutas/botones por permiso (`lib/access.js`) · reportes con ventas netas y días locales · clientes por tipo + número · IVA por producto 0–100 y precios obligatorios ≥ costo con fallback a `default` · paginación real + export CSV completo · fechas nativas.
- **P2.25 ✅ (2026-11-04)**: listo para producción en **Hostinger VPS KVM 2** con dominio **`boltrex.online`** (por comprar): `docker-compose.prod.yml` (Caddy HTTPS, respaldos diarios + Google Drive), Mongo con contraseña también en el Mac, imágenes nativas. Guía: [[DESPLIEGUE_HOSTINGER]]. Dev = `docker-compose.yml` + `docker-compose.override.yml`; `.env` en la raíz (contraseñas de Mongo) + `backend/.env`.
- Datos actuales = de **prueba** (solo seeders); el usuario lo confirmó en P1.19.
- **Cambios sin commit** (el usuario no ha pedido commit).
- **P2.29 ✅ (2026-11-04)**: Dashboard con gráficas SVG propias (`core/dashboard.py`, `components/charts/Charts.js`); vendedor ve solo lo suyo; ganancia = (venta sin IVA − compra) × cant. con `items[].unit_cost`. Falta que el usuario lo revise visualmente.
- **P2.31 ✅ (2026-11-05)**: control de caja por cajero con interruptor «Exigir caja abierta», reembolsos en efectivo y arqueo por denominaciones; **P1.40 resuelto** (excedente abonado se devuelve en efectivo). Falta revisión visual del usuario.
- **P2.27 ✅ (2026-11-05)**: sin rastros de Emergent (incluía un script externo y PostHog de Emergent en cada página); pestaña «Boltrex» con ícono propio; login con fondo propio.
- **P2.30 ✅ (2026-11-05)**: cartera con vencimientos (plazo por defecto 7 y «por vencer» 5 en Config. Sistema; plazo y cupo por cliente — solo admin —; POS avisa vencidas sin bloquear y rechaza lo que supere el cupo; Fios con antigüedad, filtros y CSV; KPI «Cartera vencida»). Falta revisión visual.
- **P2.32 ✅ (2026-11-05)**: ajustes de inventario (entrada / salida / conteo físico, AJU-000001, solo Administrador por defecto, motivos en el módulo dinámico «Motivos de ajuste», pérdidas aparte en Inventario). Falta revisión visual.
- **P2.34 ✅ (2026-11-05)**: campana de alertas (stock bajo/agotado, créditos vencidos y por vencer) con «visto» por usuario; stock mínimo general (Config. Sistema) + por producto; aviso del POS al vender. Solo dentro de la app (correo/Telegram: más adelante). Falta revisión visual.
- **P2.33 ✅ (2026-11-05)**: exportar a Excel / PDF / CSV en Reportes (ventas, inventario), Compras, Fios (cartera y estado de cuenta del cliente), Ajustes y Caja (cierre A4); PDF máx. 3.000 filas; cada exportación auditada. Falta revisión visual.
- **Siguiente**: el usuario elige; candidatos P2.24 (CI con GitHub Actions), P2.20–P2.23/P2.26 (mantenimiento). Fuera de P2: P3 (estrategia, Android offline, multi-sucursal). P2.21 está avanzado (getErrorMessage ya en casi todas las pantallas). Para desplegar hace falta **commit + push** (hay ~100 cambios sin commit; solo si el usuario lo pide).

## Para retomar
- 2026-11-05 (noche): **P2.33 exportar a Excel/PDF** hecho (ver bitácora). Pendiente del usuario: reconstruir y probar los botones «Exportar ▾», «Estado de cuenta ▾» y «Descargar ▾» de la caja.
- 2026-11-05 (noche): **P2.34 alertas** hecho (ver bitácora). Pendiente del usuario: reconstruir y revisar la campana, el aviso del POS, Config. Sistema → Inventario, stock mínimo en Productos.
- 2026-11-05 (noche): **P2.32 ajustes de inventario** hecho (ver bitácora). Pendiente del usuario: reconstruir y revisar Inventario (pestaña Ajustes, botón Ajustar, tarjeta del mes) y Motivos de Ajuste.
- 2026-11-05: **P2.30 cartera con vencimientos** hecha y **revisada visualmente por el usuario** ✅. Decisiones confirmadas por el usuario: (1) plazo y cupo del cliente **solo los cambia el Administrador**; (2) en **Fios todos ven toda la cartera** (si el cajero que vendió no está, otro debe poder registrar el abono); solo el KPI del Dashboard filtra por vendedor.
- **Al volver (noche del 2026-11-05)**: el usuario quiere repasar **qué falta**. Presentar resumen: pendientes de backlog P2.32 (ajustes de inventario), P2.24 (CI), P2.33 (Excel/PDF), P2.34 (notificaciones), P2.20–P2.23, P2.26; pendientes del usuario: comprar VPS KVM 2 + dominio `boltrex.online`, y pedir commit + push (~100 cambios sin commit) antes de desplegar.
- 2026-11-05: hecha la mejora pedida de **precios por lista en productos** (sin repetidos, máximo = listas parametrizadas, opción A para listas inactivas) y el fix del texto `))}` en el formulario de producto.
- 2026-11-05: **P2.31 control de caja** y **P2.27 limpieza de Emergent** hechos (ver bitácora). Pendiente del usuario: reconstruir (`docker compose up -d --build frontend backend`) y revisar Caja, POS con el interruptor, Config. Sistema, Devoluciones, la pestaña «Boltrex» y el login nuevo.

### Notas del cierre del 2026-11-04
- **Próximo punto acordado: P2.31 — control de caja** (apertura, cierre, arqueo, conciliación por forma de pago). Empezar mostrando la **propuesta** (revisar antes cómo se registran ventas de contado, abonos de Fios y devoluciones por forma de pago) y esperar autorización.
- Pendientes del usuario: (1) reconstruir (`docker compose up -d --build backend frontend`) y **revisar visualmente el Dashboard** (P2.29) también con un usuario Vendedor; (2) decidir/comprar el **VPS KVM 2** y el dominio `boltrex.online`; (3) cuando vaya a desplegar, pedir **commit + push** (hay ~100 cambios sin commit; revisar que no suba secretos).
- El stack de desarrollo del usuario **ya corre con Mongo autenticado** (lo recreó el 2026-11-04): para pruebas usar `source tests/test_env.sh`.
- P1.40 ✅ resuelto dentro de P2.31.

## Reglas de trabajo con el usuario
- Memorias SIEMPRE en `ProyectoBoltrex-ia/memorias_claude/` y actualizarlas al cerrar cada punto (el usuario lo pidió explícitamente).
- **Una mejora a la vez**: mostrar la propuesta (cómo quedará, opciones con recomendación) **antes de tocar código** → esperar autorización → implementar → probar → marcar ✅ en el backlog con su bitácora → avisar y esperar.
- Toda acción bloqueada debe mostrar en pantalla el motivo ([[mensajes-al-usuario]]).
- El usuario prefiere ejecutar él los comandos de Docker (`docker compose up -d --build backend frontend`); dárselos listos para copiar.
- Pruebas siempre contra una BD temporal `boltrex_<x>test` y backend en `:8001`, nunca contra `boltrex`; `source tests/test_env.sh` primero (Mongo con contraseña) y preparar la BD **antes** de arrancar ese backend.
- Al reemplazar bloques JSX con scripts, buscar además **textos JSX sueltos** (p. ej. `))}`): la comprobación de sintaxis de Babel no los detecta porque son JSX válido (pasó en Productos el 2026-11-05).
- Para validar Docker sin tocar el stack del usuario: proyecto aislado `docker compose -p boltrexverify …` con otros puertos, y `down -v --rmi local` al terminar.

**Why:** el usuario pidió un big picture reutilizable y un proceso controlado, punto por punto.
**How to apply:** partir de estos documentos; verificar en el código que lo descrito siga igual antes de recomendar cambios.
