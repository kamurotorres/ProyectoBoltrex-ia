"""Entorno de las pruebas unitarias (mantenimiento fase 7).

Se definen ANTES de importar el backend:
- MONGO_URL apunta a un puerto donde no hay nada, con espera corta: estas pruebas no usan la base de
  datos, y si alguna la tocara por error falla en menos de un segundo en vez de leer/escribir datos reales.
- Secreto y zona horaria fijos para que los resultados no dependan del .env de cada equipo.
"""
import os

os.environ["MONGO_URL"] = "mongodb://127.0.0.1:9/?serverSelectionTimeoutMS=300&connectTimeoutMS=300"
os.environ["DB_NAME"] = "boltrex_unittest"
os.environ["JWT_SECRET_KEY"] = "clave-solo-para-pruebas-unitarias"
os.environ["BUSINESS_TZ_OFFSET_MINUTES"] = "300"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "720"
