FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copiar requirements e instalar
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copiar código (.env, .venv, cachés y pruebas quedan fuera por .dockerignore: los secretos
# se montan en tiempo de ejecución, nunca van dentro de la imagen — P2.25)
COPY backend /app

# Sin privilegios de root (P2.25)
RUN useradd --create-home --uid 10001 boltrex && chown -R boltrex /app
USER boltrex

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
