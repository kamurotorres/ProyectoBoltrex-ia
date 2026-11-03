from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from core.config import MONGO_URL, DB_NAME

client = AsyncIOMotorClient(MONGO_URL)
db: AsyncIOMotorDatabase = client[DB_NAME]

def get_db() -> AsyncIOMotorDatabase:
    return db
