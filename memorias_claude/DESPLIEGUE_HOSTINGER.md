# Despliegue de Boltrex en Hostinger (VPS) — `boltrex.online`

Guía paso a paso para publicar Boltrex en internet con HTTPS, MongoDB con contraseña y respaldos diarios con copia en Google Drive. Preparada en el punto **P2.25** del backlog (2026-11-04).

> Arquitectura en el VPS: `Internet → Caddy (HTTPS, 80/443) → nginx (app + /api) → backend → MongoDB` + un contenedor de respaldos. **Solo Caddy publica puertos.** Ver `docker-compose.yml` + `docker-compose.prod.yml`.

---

## 0. Qué necesitas

| Qué | Recomendación (confirmada con Hostinger) |
|---|---|
| VPS | **KVM 2**: 2 vCPU, 8 GB RAM, 100 GB NVMe (el build de React y MongoDB caben con margen). KVM 1 solo para pruebas |
| Sistema | **Ubuntu 24.04 con la plantilla Docker** de Hostinger (trae Docker y Docker Compose) |
| Dominio | `boltrex.online` (comprado en Hostinger u otro registrador) |
| Google Drive | Una cuenta para la copia de los respaldos fuera del VPS |
| En tu Mac | Terminal con `ssh` (ya viene) y el código subido a GitHub (`kamurotorres/ProyectoBoltrex-ia`, **privado**) |

> ⚠️ El **hosting web compartido no sirve**: hace falta el VPS.

---

## 1. Subir el código a GitHub (desde tu Mac)

El VPS descarga el código del repositorio. Los secretos **no** se suben (`.env`, `backend/.env`, `backups/`, `deploy/backup/rclone/*` están en `.gitignore`).

```bash
cd ~/Documents/sistemas_pos_offline/proyecto-personal/ProyectoBoltrex-ia
git status                      # revisar que NO aparezcan .env ni backend/.env
git add -A && git commit -m "Boltrex listo para producción"
git push origin main
```

Recomendado: repositorio **privado** en GitHub (Settings → General → Danger Zone → Change visibility).

---

## 2. Contratar y preparar el VPS

1. hPanel → **VPS** → contratar **KVM 2** → sistema **Ubuntu 24.04 con Docker**. Anota la **IP** del VPS.
2. Elige una contraseña de root fuerte (solo se usará al inicio).

### 2.1 Acceso por SSH con clave (sin contraseña)
En **tu Mac**:
```bash
ssh-keygen -t ed25519 -C "boltrex-vps"          # Enter a todo (o pon una frase de paso)
ssh-copy-id root@IP_DEL_VPS                      # pide la contraseña de root una sola vez
ssh root@IP_DEL_VPS                              # ya entra sin contraseña
```
En el **VPS**, desactiva el acceso por contraseña **cuando confirmes que la clave funciona**:
```bash
sed -i 's/^#\?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#\?PermitRootLogin .*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
systemctl restart ssh
```
> Si pierdes la clave, Hostinger tiene consola web (hPanel → VPS → Terminal) para recuperar el acceso.

### 2.2 Firewall: solo 22, 80 y 443
```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw allow 443/udp
ufw --force enable && ufw status
```
> Docker publica puertos saltándose `ufw`: por eso en producción **solo Caddy** tiene `ports:` (Mongo, backend y frontend no publican nada). No agregues `ports:` a otros servicios.

### 2.3 Actualizaciones de seguridad automáticas
```bash
apt update && apt -y upgrade && apt -y install unattended-upgrades git
dpkg-reconfigure -plow unattended-upgrades       # responder "Yes"
```

---

## 3. Apuntar el dominio al VPS

En el panel DNS del dominio (hPanel → Dominios → `boltrex.online` → DNS):

| Tipo | Nombre | Valor | TTL |
|---|---|---|---|
| A | `@` | IP_DEL_VPS | 3600 |
| A | `www` | IP_DEL_VPS | 3600 *(opcional)* |

Comprobar (puede tardar de minutos a unas horas): `dig +short boltrex.online` → debe mostrar la IP del VPS.
**Caddy no podrá sacar el certificado HTTPS hasta que el dominio apunte al VPS.**

---

## 4. Descargar Boltrex y configurar los secretos (en el VPS)

```bash
mkdir -p /opt && cd /opt
git clone https://github.com/kamurotorres/ProyectoBoltrex-ia.git boltrex
cd /opt/boltrex
```
(Repositorio privado: GitHub pedirá usuario y un **token personal** como contraseña — GitHub → Settings → Developer settings → Personal access tokens → *Fine-grained*, solo lectura del repo.)

### 4.1 `.env` (Docker Compose)
```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_hex(24))"    # ejecútalo 2 veces: una por contraseña
nano .env
```
Rellena: `MONGO_ROOT_PASSWORD`, `MONGO_APP_PASSWORD` (las dos generadas, **solo letras y números**), `DOMAIN=boltrex.online`, `ACME_EMAIL=tu-correo`, `RCLONE_REMOTE=gdrive:boltrex-backups`.

### 4.2 `backend/.env` (aplicación)
```bash
cp backend/.env.example backend/.env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"  # para JWT_SECRET_KEY
nano backend/.env
```
- `JWT_SECRET_KEY` = el valor generado.
- `ADMIN_INITIAL_PASSWORD` = contraseña inicial del admin (mín. 8, no `admin123`; se pide cambiarla al entrar).
- `CORS_ORIGINS=https://boltrex.online` (descomentar la línea).
- La línea `MONGO_URL` de este archivo **no** se usa en Docker (la define `docker-compose.yml`); puedes dejarla tal cual.

```bash
chmod 600 .env backend/.env      # solo root puede leerlos
```

---

## 5. Copia de respaldos en Google Drive (rclone)

Se configura **una vez**. El VPS no tiene navegador, así que la autorización de Google se hace en tu Mac.

**En tu Mac** (sin Homebrew):
```bash
cd ~/Downloads
curl -LO https://downloads.rclone.org/rclone-current-osx-arm64.zip
unzip -o rclone-current-osx-arm64.zip && cd rclone-*-osx-arm64
xattr -d com.apple.quarantine rclone 2>/dev/null
./rclone authorize "drive" "eyJzY29wZSI6ImRyaXZlLmZpbGUifQ=="   # = {"scope":"drive.file"} en base64
```
Se abre el navegador → elige la cuenta de Google → Permitir. La terminal imprime un bloque `{"access_token":...}`: **cópialo completo**.
(`drive.file` = rclone solo ve los archivos que él mismo crea, no el resto de tu Drive.)

**En el VPS**:
```bash
cd /opt/boltrex
cat > deploy/backup/rclone/rclone.conf <<'EOF'
[gdrive]
type = drive
scope = drive.file
token = PEGA_AQUI_EL_BLOQUE_{"access_token":...}_EN_UNA_SOLA_LINEA
EOF
chmod 600 deploy/backup/rclone/rclone.conf
```

---

## 6. Levantar Boltrex

```bash
cd /opt/boltrex
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build    # 5-10 min la primera vez
docker compose -f docker-compose.yml -f docker-compose.prod.yml ps               # todo "healthy"/"running"
```
Para no escribir los `-f` cada vez:
```bash
echo 'alias bx="docker compose -f /opt/boltrex/docker-compose.yml -f /opt/boltrex/docker-compose.prod.yml --project-directory /opt/boltrex"' >> ~/.bashrc && source ~/.bashrc
bx ps        # equivale al comando largo
```

### 6.1 Cargar los datos iniciales (solo la primera vez)
```bash
PROD=1 scripts/seed_docker.sh
```

### 6.2 Verificar
- `https://boltrex.online` abre el login con candado 🔒 (si tarda, ver `bx logs caddy`: suele ser el DNS aún sin propagar).
- `http://boltrex.online` redirige solo a HTTPS.
- Entra con `admin@boltrex.com` + `ADMIN_INITIAL_PASSWORD` → te pide una contraseña nueva.
- Desde tu Mac, Mongo y el backend **no** deben responder: `nc -zv boltrex.online 27017` y `nc -zv boltrex.online 8000` → fallan (correcto).

### 6.3 Probar los respaldos
```bash
bx exec backup backup-now        # crea backups/boltrex-AAAAMMDD-HHMMSS.archive.gz y lo sube a Drive
ls -lh backups/
bx logs backup | tail            # "copia subida a gdrive:boltrex-backups"
```
En Google Drive aparece la carpeta **boltrex-backups**. A partir de ahí se hace solo **todos los días a las 3:00 a. m.** (hora de Colombia), se guardan **14 días en el VPS** y **30 en Drive**.

---

## 7. Operación diaria

| Tarea | Comando (en `/opt/boltrex`) |
|---|---|
| Estado | `bx ps` |
| Logs | `bx logs -f backend` (o `caddy`, `frontend`, `mongo`, `backup`) |
| Reiniciar | `bx restart backend` |
| **Actualizar a una versión nueva** | `git pull && bx up -d --build` |
| Respaldo manual | `bx exec backup backup-now` |
| **Restaurar un respaldo** | `PROD=1 scripts/restore_backup.sh backups/boltrex-AAAAMMDD-HHMMSS.archive.gz` (pide escribir RESTAURAR) y luego `bx restart backend` |
| Restaurar desde Drive (si el VPS se perdió) | Instalar Boltrex en el VPS nuevo (pasos 2–6), copiar el respaldo desde Drive a `backups/` y restaurar |
| Espacio en disco | `df -h` y `docker system df`; limpiar imágenes viejas: `docker image prune -f` |

**Segunda capa de respaldo**: activa las copias de seguridad de Hostinger (hPanel → VPS → Copias de seguridad / Snapshots) si tu plan las incluye.

---

## 8. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `required variable DOMAIN is missing` (o ACME_EMAIL, MONGO_…) | Falta en `.env` | Completar `.env` (paso 4.1) |
| El navegador dice "no seguro" / Caddy reintenta el certificado | El DNS aún no apunta al VPS o el puerto 80/443 está cerrado | `dig +short boltrex.online`, `ufw status`, `bx logs caddy` |
| `mongo` no llega a "healthy" en la 1.ª instalación | Contraseña con símbolos raros | Usar contraseñas alfanuméricas; si ya arrancó con otras: `bx down -v` (⚠️ borra la BD) y volver a levantar |
| Cambié las contraseñas de Mongo en `.env` y ya no conecta | Mongo crea los usuarios **solo la primera vez** (volumen vacío) | Volver a las contraseñas anteriores, o cambiarlas dentro de Mongo (`db.changeUserPassword`) |
| `⚠️ sin copia fuera del VPS` en `bx logs backup` | Falta `rclone.conf` o `RCLONE_REMOTE` | Paso 5 |
| `NO se pudo subir la copia` | Token de Google vencido/revocado | Repetir el paso 5 (rclone authorize) |
| El build se queda sin memoria | VPS pequeño | Usar KVM 2; o construir con los demás servicios parados |
