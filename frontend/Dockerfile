# Stage 1: build
# P2.25: sin --platform forzado → imagen nativa (arm64 en tu Mac, amd64 en el VPS).
FROM node:18-alpine AS build
WORKDIR /app

# 1. Solo los archivos de dependencias (node_modules del host queda fuera por .dockerignore)
COPY frontend/package.json ./

# 2. Instalar
RUN npm install --legacy-peer-deps
# CRACO necesita ajv/ajv-keywords en una versión compatible
RUN npm install ajv ajv-keywords --legacy-peer-deps

# 3. Resto del código
COPY frontend/ ./

# 4. Construir
RUN npm run build

# Stage 2: nginx serve
FROM nginx:1.25-alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
# Carpeta para fragmentos opcionales (producción monta aquí realip.conf)
RUN mkdir -p /etc/nginx/snippets
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
