import asyncio

from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_DB_URI


MAX_CLONES = 2

client = AsyncIOMotorClient(MONGO_DB_URI)

db = client["musicbot"]
clone_col = db["clones"]

_save_lock = asyncio.Lock()


async def save_clone(
    owner_id: int,
    bot_token: str,
    bot_username: str = None,
):
    async with _save_lock:

        existing = await clone_col.find_one({
            "bot_token": bot_token
        })

        if existing:
            return False

        count = await clone_col.count_documents({
            "is_active": True
        })

        if count >= MAX_CLONES:
            return False

        await clone_col.insert_one({
            "owner_id": int(owner_id),
            "bot_token": bot_token,
            "bot_username": bot_username,
            "is_active": True,
        })

        return True


async def get_all_clones():
    cursor = clone_col.find(
        {"is_active": True}
    ).sort("_id", 1)

    return await cursor.to_list(length=100)


async def remove_clone(bot_token: str):
    await clone_col.update_one(
        {"bot_token": bot_token},
        {
            "$set": {
                "is_active": False
            }
        },
    )


async def is_token_exist(bot_token: str):
    data = await clone_col.find_one({
        "bot_token": bot_token
    })

    return bool(data)


async def count_active_clones():
    return await clone_col.count_documents({
        "is_active": True
    })
