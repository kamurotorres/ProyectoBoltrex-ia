from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from core.config import MONGO_URL, DB_NAME

# tz_aware: las fechas vuelven con zona (UTC) y la API las entrega con '+00:00' (P1.19).
client = AsyncIOMotorClient(MONGO_URL, tz_aware=True)
db: AsyncIOMotorDatabase = client[DB_NAME]

def get_db() -> AsyncIOMotorDatabase:
    return db
