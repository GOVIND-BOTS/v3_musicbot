import os

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument

from config import MONGO_DB_URI

MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "v3_musicbot")

mongo_client = AsyncIOMotorClient(
    MONGO_DB_URI,
    serverSelectionTimeoutMS=10000,
)

database = mongo_client[MONGO_DB_NAME]
anti_abuse_collection = database["anti_abuse"]


async def get_chat_settings(chat_id):
    data = await anti_abuse_collection.find_one(
        {"chat_id": chat_id, "type": "settings"}
    )

    if not data:
        return {
            "enabled": False,
            "banned_words": [],
            "mute_seconds": 3600,
        }

    return data


async def update_chat_settings(chat_id, values):
    await anti_abuse_collection.update_one(
        {"chat_id": chat_id, "type": "settings"},
        {
            "$set": values,
            "$setOnInsert": {
                "chat_id": chat_id,
                "type": "settings",
            },
        },
        upsert=True,
    )


async def add_banned_word(chat_id, word):
    await anti_abuse_collection.update_one(
        {"chat_id": chat_id, "type": "settings"},
        {
            "$addToSet": {"banned_words": word.lower()},
            "$setOnInsert": {
                "chat_id": chat_id,
                "type": "settings",
                "enabled": False,
                "mute_seconds": 3600,
            },
        },
        upsert=True,
    )


async def remove_banned_word(chat_id, word):
    await anti_abuse_collection.update_one(
        {"chat_id": chat_id, "type": "settings"},
        {"$pull": {"banned_words": word.lower()}},
    )


async def add_warning(chat_id, user_id):
    data = await anti_abuse_collection.find_one_and_update(
        {
            "chat_id": chat_id,
            "type": "warning",
            "user_id": user_id,
        },
        {
            "$inc": {"warnings": 1},
            "$setOnInsert": {
                "chat_id": chat_id,
                "type": "warning",
                "user_id": user_id,
            },
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )

    return data["warnings"]


async def get_warnings(chat_id, user_id):
    data = await anti_abuse_collection.find_one(
        {
            "chat_id": chat_id,
            "type": "warning",
            "user_id": user_id,
        }
    )

    return data.get("warnings", 0) if data else 0


async def reset_warnings(chat_id, user_id):
    await anti_abuse_collection.update_one(
        {
            "chat_id": chat_id,
            "type": "warning",
            "user_id": user_id,
        },
        {"$set": {"warnings": 0}},
    )
