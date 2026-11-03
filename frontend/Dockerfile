# Stage 1: build
# Forzamos la plataforma a linux/amd64 para asegurar compatibilidad
FROM --platform=linux/amd64 node:18-alpine AS build
WORKDIR /app

# Copiar archivos de dependencias
#antes COPY frontend/package.json frontend/package-lock.json* frontend/yarn.lock* /app/

# Instalar dependencias y construir
#antes COPY frontend/ /app/
#antes RUN npm install --legacy-peer-deps
#antes RUN npm run build

# 1. Copiar SOLO archivos de dependencias
COPY frontend/package.json ./
#COPY frontend/package.json frontend/package-lock.json* ./

# 2. Instalar (npm install creará los node_modules correctos para Linux)
RUN npm cache clean --force
RUN npm install --legacy-peer-deps
# --- SOLUCIÓN ESPECÍFICA PARA AJV ---
# Forzamos la instalación de ajv y sus keywords que CRACO está buscando
RUN npm install ajv ajv-keywords --legacy-peer-deps

# 3. AHORA copiar el resto del código (excluyendo lo del .dockerignore)
COPY frontend/ ./

# 4. Construir
RUN npm run build

# Stage 2: nginx serve
# También forzamos la plataforma aquí
FROM --platform=linux/amd64 nginx:1.25-alpine
# Copiamos desde la etapa de build a la carpeta de nginx
COPY --from=build /app/build /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]