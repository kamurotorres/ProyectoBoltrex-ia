# Cómo levantar Boltrex (backend + frontend + MongoDB)

Guía para dejar el proyecto completo corriendo en local en macOS (Apple Silicon).
Dos caminos: **A. Docker** (recomendado: levanta los 3 servicios) o **B. Local sin Docker** (para desarrollar con recarga en caliente).

Arquitectura de referencia: [ARQUITECTURA_BIG_PICTURE.md](ARQUITECTURA_BIG_PICTURE.md).

> ✅ **Camino A verificado el 2026-11-03** en MacBook Apple Silicon (macOS 27, Docker 29.9.2, Compose v5.6.1): build ~3 min, 3 contenedores arriba, seeding OK y login con el admin funcionando. El camino B aún no se ha probado de punta a punta.

---

## 0. Requisitos

| Herramienta | Para qué | Comprobar |
|---|---|---|
| Docker Desktop (abierto) | Camino A | `docker --version` y `docker compose version` |
| Python **3.11 o 3.12** | Scripts de seeding (y backend en camino B) | `python3.12 --version` — **no usar 3.13/3.14**: algunas dependencias fijadas en `requirements.txt` no tienen soporte |
| Node 18+ y npm | Solo camino B | `node --version` |
| MongoDB 6+ | Solo camino B (en A lo pone Docker) | `mongod --version` |

Puertos que deben estar libres: **3000** (frontend), **8000** (backend), **27017** (MongoDB).
Si ya tienes un MongoDB local corriendo en 27017, deténlo antes del camino A (o cambia el puerto publicado en `docker-compose.yml`).

> Si la terminal dice `docker: command not found`, en Docker Desktop → Settings → Advanced activa la instalación de las herramientas CLI, o añade `/Applications/Docker.app/Contents/Resources/bin` al `PATH`.

---

## 1. Configuración (una sola vez)

> **Desde 2026-11-04 (P2.25)** hay **dos** archivos de variables: `.env` en la raíz (Docker Compose: contraseñas de MongoDB) y `backend/.env` (la app). Plantillas: `.env.example` y `backend/.env.example`. Mongo ahora exige usuario y contraseña, también en tu Mac. Producción en Hostinger: ver [DESPLIEGUE_HOSTINGER.md](DESPLIEGUE_HOSTINGER.md).
>
> **Primera vez tras el cambio a Mongo con contraseña** (borra los datos de prueba):
> ```bash
> docker compose down -v && docker compose up -d --build && scripts/seed_docker.sh
> ```

Todos los comandos se ejecutan desde la carpeta raíz del repo.

### 1.0 `.env` de la raíz (Docker Compose)
```bash
cp .env.example .env     # y reemplazar las contraseñas (solo letras y números)
python3 -c "import secrets; print(secrets.token_hex(24))"
```
`MONGO_ROOT_*` = administrador de Mongo (respaldos, pruebas); `MONGO_APP_*` = usuario con el que se conecta la app. Los usuarios se crean **solo la primera vez** (volumen vacío): cambiar luego las contraseñas en `.env` no cambia las de Mongo.

Desde la carpeta raíz:

```bash
cd ~/Documents/sistemas_pos_offline/proyecto-personal/ProyectoBoltrex-ia
```

### 1.1 `backend/.env`
El repo **no** lo incluye (está en `.gitignore`), pero el backend y los scripts lo necesitan. Contenido:

```env
MONGO_URL=mongodb://boltrex_app:<MONGO_APP_PASSWORD>@localhost:27017/boltrex?directConnection=true&authSource=admin
DB_NAME=boltrex
JWT_SECRET_KEY=<cadena-larga-aleatoria>
```

Generar un secreto: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.

**Obligatoria para crear el primer admin (desde 2026-11-04):**

```env
ADMIN_INITIAL_PASSWORD=<contraseña de al menos 8 caracteres, no admin123>
```

Ya no existe la contraseña `admin123`. Los scripts del paso 2.2 usan esta variable para crear `admin@boltrex.com`, y si falta se detienen explicando qué agregar. Al primer ingreso el sistema **obliga a cambiarla**; después puedes borrar la línea del `.env`. Si una instalación antigua aún tiene `admin123`, el backend lo detecta al arrancar y también pide cambiarla.

Variables opcionales de seguridad (desde 2026-11-04):

| Variable | Default | Para qué |
|---|---|---|
| `ALLOW_PUBLIC_REGISTRATION` | `false` | `true` reactiva `POST /api/auth/register` (cualquiera crea un usuario Vendedor) |
| `CORS_ORIGINS` | `http://localhost:3000` | Orígenes permitidos, separados por comas. En Docker no hace falta (mismo origen vía nginx) |
| `REACT_APP_ALLOW_REGISTRATION` (frontend, en build) | — | `true` muestra el enlace "Regístrate" en el login |
| `LOGIN_MAX_ATTEMPTS` / `LOGIN_IP_MAX_ATTEMPTS` | `5` / `20` | Intentos fallidos permitidos por cuenta / por equipo antes del bloqueo |
| `LOGIN_WINDOW_MINUTES` / `LOGIN_LOCK_MINUTES` | `15` / `15` | Ventana en que se cuentan los fallos / duración del bloqueo (admiten decimales) |
| `SESSION_IDLE_MINUTES` | `60` | Sin ninguna acción durante este tiempo la sesión se cierra y hay que volver a entrar |
| `SESSION_WARNING_MINUTES` | `5` | Minutos antes del cierre por inactividad en que aparece el aviso "Seguir conectado" |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `720` | Duración máxima de una sesión (12 h) aunque haya actividad |
| `AUDIT_RETENTION_DAYS` | `180` | Días que se conserva la bitácora de auditoría (6 meses); `0` = para siempre. Al cambiarlo se aplica al reiniciar el backend |

**Sesiones**: cambiar la contraseña, los roles o desactivar a un usuario cierra sus sesiones abiertas; cada usuario puede usar "Cerrar sesión en todos los equipos" en el menú lateral.

**Auditoría**: menú **Auditoría** (solo rol Administrador) muestra quién hizo qué, cuándo, desde qué IP, navegador y dispositivo, con el antes/después de cada cambio. El factory reset no la borra.

**Cuenta bloqueada por intentos fallidos**: se desbloquea sola al pasar el tiempo, o al instante si un administrador le cambia la contraseña desde **Usuarios**.

Los usuarios nuevos los crea el administrador en **Usuarios** (menú lateral) y les asigna un rol.

- `MONGO_URL=localhost` sirve para el camino B y para correr los scripts desde tu máquina.
- En Docker, `docker-compose.yml` **sobrescribe** `MONGO_URL=mongodb://mongo:27017/?replicaSet=rs0` (dentro de la red de Docker, Mongo se llama `mongo`, no `localhost`).
- **MongoDB corre como replica set `rs0`** (desde 2026-11-04) porque las ventas, compras, devoluciones y abonos usan transacciones. El healthcheck lo inicializa solo. Desde el Mac hay que conectar con `?directConnection=true`: el miembro del replica set se anuncia como `mongo:27017`, nombre que solo existe dentro de Docker.
- En el camino B con un `mongod` propio sin `--replSet`, todo funciona pero **sin atomicidad** (el backend lo avisa en el log). Para tener transacciones: `mongod --replSet rs0` y luego `mongosh --eval "rs.initiate()"`.

### 1.2 Entorno virtual de Python (para los scripts de seeding y el camino B)

```bash
cd backend
python3.12 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
cd ..
```

---

## 2. Camino A — Docker (recomendado)

### 2.1 Construir y levantar
Con Docker Desktop abierto:

```bash
docker compose up -d --build
```

- La primera construcción es **lenta** (5–15 min): las imágenes fuerzan `linux/amd64` y en Apple Silicon se emulan con Rosetta. Las siguientes son rápidas por la caché.
- Levanta 3 contenedores: `mongo` (27017), `backend` (8000), `frontend` (nginx en 3000 → 80).
- **Desde 2026-11-04, 8000 y 27017 solo se publican en `127.0.0.1`**: funcionan desde tu Mac (`localhost`), pero no desde otros equipos de la red. Desde otro equipo se entra solo por `http://<ip-del-mac>:3000`. Es intencional: Mongo no tiene contraseña y el backend confía en la cabecera `X-Real-IP` que pone nginx. ⚠️ En un VPS (Hostinger) **no quitar** el `127.0.0.1:`: Docker se salta el firewall `ufw`.
- Avisos inofensivos: `the attribute version is obsolete` y `The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64)` — este último indica emulación con Rosetta; funciona, solo algo más lento.
- `GET http://localhost:3000/api/auth/me` sin token devuelve **403**: es lo esperado y confirma que el proxy nginx → backend funciona.

Comprobar:
```bash
docker compose ps                 # los 3 servicios en estado "running"
docker compose logs -f backend    # Ctrl+C para salir
```

### 2.2 Cargar datos iniciales (solo la primera vez, con la BD vacía)

**Recomendado (desde P2.25):** dentro de Docker, sin necesidad del entorno de Python:
```bash
scripts/seed_docker.sh
```
Alternativa con el venv (usa `MONGO_URL` de `backend/.env`, ahora con usuario y contraseña):
Los scripts no van dentro de la imagen; se ejecutan desde tu máquina contra el Mongo del contenedor (publicado en `localhost:27017`):

```bash
backend/.venv/bin/python scripts/init_rbac.py    # módulos, roles y permisos (idempotente)
backend/.venv/bin/python scripts/seed_data.py    # usuario admin + catálogos por defecto
```

### 2.3 Verificar
| Qué | URL |
|---|---|
| API viva | http://localhost:8000/ → `{"message":"Welcome to Boltrex API"}` |
| Documentación de la API (Swagger) | http://localhost:8000/docs |
| Aplicación | http://localhost:3000 |

Login: **`admin@boltrex.com`** con la contraseña de `ADMIN_INITIAL_PASSWORD` (rol Administrador). Al entrar te pedirá una contraseña nueva. Cualquier usuario puede cambiar la suya con el botón **Contraseña** del menú lateral.
Recarga la página (F5) después de entrar: debe mantener la sesión.

### 2.4 Operación diaria
```bash
docker compose up -d                  # arrancar
docker compose down                   # parar (los datos persisten en el volumen mongo_data)
docker compose up -d --build backend  # reconstruir tras cambiar código del backend
docker compose up -d --build frontend # reconstruir tras cambiar código del frontend
docker compose down -v                # ⚠️ parar y BORRAR la base de datos (luego repetir 2.2)
```

En Docker **no hay recarga en caliente**: cada cambio de código exige reconstruir el servicio. Para desarrollar, usa el camino B.

---

## 3. Camino B — Local sin Docker (desarrollo)

Necesita MongoDB corriendo en `localhost:27017` (instalación propia, o solo el contenedor: `docker compose up -d mongo`).

Terminal 1 — backend (recarga automática):
```bash
cd backend
.venv/bin/uvicorn main:app --reload --port 8000
```

Primera vez — datos iniciales (desde la raíz del repo):
```bash
backend/.venv/bin/python scripts/init_rbac.py
backend/.venv/bin/python scripts/seed_data.py
```

Terminal 2 — frontend (recarga automática):
```bash
cd frontend
npm install --legacy-peer-deps      # solo la primera vez
REACT_APP_BACKEND_URL=http://localhost:8000 npm start
```

Abre http://localhost:3000. `REACT_APP_BACKEND_URL` es **obligatoria** en este modo: sin ella el frontend llama a `/api` relativo, y eso solo funciona detrás del nginx de Docker.

---

## 4. Problemas conocidos y soluciones

| Síntoma | Causa | Solución |
|---|---|---|
| `pip install` falla compilando paquetes | Python 3.13/3.14 | Usar Python 3.11/3.12 para el venv |
| `npm error EEXIST ... _cacache` | Caché de npm corrupta | `npm install --legacy-peer-deps --cache /tmp/npm-cache-boltrex` (caché nueva) |
| `brew install mongodb-community` → "untrusted tap" | Homebrew exige confiar en el tap | `brew trust --formula mongodb/brew/mongodb-community` y `.../mongodb-database-tools` |
| `brew` → "Your Xcode is too outdated" | Xcode más viejo que macOS | Actualizar Xcode, o usar Mongo en Docker |
| Backend en Docker no conecta a Mongo | `MONGO_URL=localhost` dentro del contenedor | Ya resuelto: compose define `MONGO_URL=mongodb://mongo:27017` |
| `KeyError: 'MONGO_URL'` en los scripts | Falta `backend/.env` | Crear el archivo (paso 1.1) |
| Login OK pero F5 cierra la sesión | Bug en `/auth/me` (importaba `server_rbac`) | Corregido el 2026-11-03 en `backend/routers/auth.py` |
| Desde otro equipo no abre `:8000` o no conecta a `:27017` | Publicados solo en `127.0.0.1` a propósito | Usar la app por `:3000`; Swagger y Mongo solo desde el propio Mac (o un túnel SSH en el servidor) |
| Script dice `falta ADMIN_INITIAL_PASSWORD` | Ya no hay contraseña por defecto | Agregarla a `backend/.env` (paso 1.1) y repetir |
| Tras entrar solo aparece "Cambiar contraseña" / "Debes cambiar tu contraseña antes de continuar" | Contraseña inicial o `admin123` | Cambiarla en esa pantalla; luego todo funciona |
| Vuelve al login con "Tu sesión se cerró por inactividad" / "Tu sesión expiró" / "Tu sesión fue cerrada" | Inactividad (`SESSION_IDLE_MINUTES`), duración máxima, o cierre por cambio de contraseña/roles/desactivación | Volver a iniciar sesión; ajustar las variables si los tiempos no sirven |
| "No tienes acceso a …" al abrir una sección, o aviso "Solo lectura" | El rol no tiene permiso de ver (o solo de ver) esa sección (P1.13) | Darle el permiso en **Roles y Permisos**; la pantalla se actualiza sola al volver a la pestaña o en la siguiente acción |
| `required variable MONGO_ROOT_PASSWORD is missing` (u otra) | Falta el `.env` de la raíz | `cp .env.example .env` y completar (paso 1.0) |
| `mongo` no llega a healthy / el backend no conecta tras activar contraseñas | El volumen de datos es anterior (Mongo sin usuarios) | `docker compose down -v && docker compose up -d --build && scripts/seed_docker.sh` (borra los datos) |
| Las pruebas fallan con `Unauthorized` | Falta `source tests/test_env.sh` | Ver §6 |
| `Address already in use` en 27017/8000/3000 | Otro proceso en el puerto | `lsof -iTCP:<puerto> -sTCP:LISTEN` y detenerlo |
| El menú lateral sale vacío | El usuario no tiene roles/permisos | Ejecutar `init_rbac.py` y entrar con el admin |

---

| Log del backend: `No se pudo crear el índice único ...: hay datos duplicados` | La BD tiene registros repetidos (p. ej. dos productos con el mismo código) | El log muestra los valores duplicados: corregirlos/eliminarlos y `docker compose restart backend`. El sistema funciona igual mientras tanto, pero sin esa garantía de unicidad |
| Un usuario ve el menú pero recibe "No tienes permiso para realizar esta acción" | Desde 2026-11-04 el backend aplica RBAC | Darle el permiso en **Roles y Permisos**; volver a iniciar sesión |
| "El registro público está desactivado" | `ALLOW_PUBLIC_REGISTRATION` en `false` | Crear el usuario desde **Usuarios**, o activar la variable |

## 5. Cambios hechos al repo para que levante (2026-11-03)
- `docker-compose.yml`: añadido `environment: MONGO_URL=mongodb://mongo:27017` al servicio `backend`.
- `backend/routers/auth.py`: `from server_rbac import ...` → `from routers.rbac import ...` (arregla `/auth/me`).
- Creado `backend/.env` local (no versionado).

---

## 6. Pruebas automáticas (desde 2026-11-04)

Nunca contra la BD real `boltrex`: cada batería usa una BD temporal `boltrex_<x>test` y un backend de prueba en el puerto **8001**.

**Forma corta (P2.24, recomendada):** `scripts/run_all_tests.sh` — prepara las BD, arranca/apaga el backend de prueba, corre las 23 baterías de la fase principal + `session` y `login_throttle` (con sus tiempos cortos) + `frontend_access`, muestra un resumen ✅/❌, guarda logs en `.test-logs/` y borra las BD `boltrex_ci*test`. Con argumentos corre solo esas baterías (`scripts/run_all_tests.sh credit cash`). Es lo mismo que corre el CI de GitHub Actions (`.github/workflows/ci.yml`). Funciona con el bash 3.2 de macOS.

Forma manual (una batería a la vez):

```bash
cd ~/Documents/sistemas_pos_offline/proyecto-personal/ProyectoBoltrex-ia
# 0) Mongo tiene contraseña (P2.25): MONGO_URL con el administrador de .env
source tests/test_env.sh
# 1) Preparar la BD de prueba ANTES de arrancar el backend (crea los índices al arrancar)
DB_NAME=boltrex_qatest tests/prepare_test_db.sh
# 2) Backend de prueba (otra terminal)
source tests/test_env.sh
DB_NAME=boltrex_qatest backend/.venv/bin/uvicorn main:app --app-dir backend --port 8001
# 3) Correr una batería (o todas en un for)
BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_qatest backend/.venv/bin/python tests/pagination_check.py
for t in indexes counters transactions stock_concurrency returns security_rbac references user_protection \
         password_change sales_report client_identity pricing pagination dates audit \
         dashboard product_price_lists cash credit adjustments alerts exports factory_reset; do
  BOLTREX_API=http://localhost:8001/api DB_NAME=boltrex_qatest backend/.venv/bin/python tests/${t}_check.py | tail -1
done
node tests/frontend_access_check.js   # mapa de rutas/permisos del frontend, sin navegador
```

- `factory_reset_check` borra los datos de la BD de prueba: dejarla de última.
- `session_check` y `login_throttle_check` necesitan un backend con tiempos cortos (`SESSION_IDLE_MINUTES=0.1 ACCESS_TOKEN_EXPIRE_MINUTES=0.3` / `LOGIN_LOCK_MINUTES=0.05 LOGIN_WINDOW_MINUTES=0.1`); ver el docstring de cada una.
- El admin de prueba usa `BOLTREX_ADMIN_PASSWORD` (por defecto `Prueba-Admin-2026`).
- Al terminar: borrar las BD `boltrex_*test` (no se borra `boltrex`).
- El build local del frontend (`npm run build`) falla por un `ajv` roto en `node_modules`; el build real se hace en Docker (el Dockerfile instala `ajv`). Para revisar sintaxis sin build se usa el parser de Babel.
