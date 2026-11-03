from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI

client = AsyncIOMotorClient(MONGO_DB_URI)
db = client["musicbot"]
clone_col = db["clones"]


async def save_clone(owner_id: int, bot_token: str, bot_username: str = None):
    await clone_col.update_one(
        {"bot_token": bot_token},
        {
            "$set": {
                "owner_id": owner_id,
                "bot_token": bot_token,
                "bot_username": bot_username,
                "is_active": True,
            }
        },
        upsert=True,
    )


async def get_all_clones():
    cursor = clone_col.find({"is_active": True})
    return await cursor.to_list(length=100)


async def remove_clone(bot_token: str):
    await clone_col.update_one(
        {"bot_token": bot_token},
        {"$set": {"is_active": False}}
    )


async def is_token_exist(bot_token: str):
    data = await clone_col.find_one({"bot_token": bot_token})
    return bool(data)
