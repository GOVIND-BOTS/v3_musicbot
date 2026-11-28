import logging
import os

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import ServerSelectionTimeoutError
from pymongo.server_api import ServerApi

from config import MONGO_DB_URI

LOGGER = logging.getLogger("v3_musicbot.database")

mongo_client = AsyncIOMotorClient(
    MONGO_DB_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    server_api=ServerApi("1"),
    connectTimeoutMS=15000,
    serverSelectionTimeoutMS=20000,
    socketTimeoutMS=20000,
    retryWrites=True,
)

database = mongo_client[os.getenv("MONGO_DB_NAME", "v3_musicbot")]

users_collection = database["users"]
chats_collection = database["chats"]
settings_collection = database["settings"]
queue_collection = database["queues"]
playlists_collection = database["playlists"]
moderation_collection = database["moderation"]


async def ping_db():
    """Verify Atlas connectivity and provide actionable, secret-safe errors."""
    try:
        await mongo_client.admin.command("ping")
        return True
    except ServerSelectionTimeoutError as exc:
        message = str(exc)
        if "TLSV1_ALERT_INTERNAL_ERROR" in message or "SSL handshake failed" in message:
            LOGGER.error(
                "MongoDB TLS handshake failed. Check Atlas > Network Access: "
                "the Railway service's outbound IP must be allowed. For a short "
                "diagnostic only, Atlas can temporarily allow 0.0.0.0/0; remove "
                "that broad rule after testing. Also verify Railway can reach "
                "Atlas TCP port 27017. Database passwords are not the cause of "
                "a TLS handshake failure because authentication happens later."
            )
        else:
            LOGGER.error(
                "MongoDB server selection failed. Check Atlas cluster status, "
                "Network Access IP allowlist, DNS SRV resolution, and outbound "
                "TCP access to port 27017."
            )
        raise RuntimeError(
            "MongoDB is unreachable from this service. See the preceding "
            "MongoDB diagnostic log; verify Atlas Network Access and Railway "
            "outbound connectivity."
        ) from exc


async def add_user(user_id: int):
    await users_collection.update_one(
        {"_id": user_id},
        {"$setOnInsert": {"_id": user_id}},
        upsert=True,
    )


async def remove_user(user_id: int):
    await users_collection.delete_one({"_id": user_id})


async def get_users():
    return await users_collection.distinct("_id")


async def add_chat(chat_id: int):
    await chats_collection.update_one(
        {"_id": chat_id},
        {"$setOnInsert": {"_id": chat_id}},
        upsert=True,
    )


async def remove_chat(chat_id: int):
    await chats_collection.delete_one({"_id": chat_id})


async def get_chats():
    return await chats_collection.distinct("_id")


async def get_chat_settings(chat_id: int):
    return await settings_collection.find_one({"_id": chat_id}) or {"_id": chat_id}


async def update_chat_settings(chat_id: int, key: str, value):
    await settings_collection.update_one(
        {"_id": chat_id},
        {"$set": {key: value}},
        upsert=True,
    )


async def delete_chat_settings(chat_id: int):
    await settings_collection.delete_one({"_id": chat_id})


async def save_queue(chat_id: int, tracks: list):
    await queue_collection.update_one(
        {"_id": chat_id},
        {"$set": {"tracks": tracks}},
        upsert=True,
    )


async def get_queue(chat_id: int):
    data = await queue_collection.find_one({"_id": chat_id})
    return data.get("tracks", []) if data else []


async def clear_queue(chat_id: int):
    await queue_collection.delete_one({"_id": chat_id})


async def save_playlist(user_id: int, name: str, tracks: list):
    await playlists_collection.update_one(
        {"user_id": user_id, "name": name},
        {"$set": {"tracks": tracks}},
        upsert=True,
    )


async def get_playlist(user_id: int, name: str):
    data = await playlists_collection.find_one({"user_id": user_id, "name": name})
    return data.get("tracks", []) if data else []


async def get_user_playlists(user_id: int):
    return await playlists_collection.find(
        {"user_id": user_id},
        {"name": 1, "_id": 0},
    ).to_list(length=None)


async def delete_playlist(user_id: int, name: str):
    await playlists_collection.delete_one({"user_id": user_id, "name": name})


async def get_moderation_data(chat_id: int, user_id: int):
    return await moderation_collection.find_one(
        {"chat_id": chat_id, "user_id": user_id}
    ) or {"chat_id": chat_id, "user_id": user_id, "warnings": 0}


async def add_moderation_warning(chat_id: int, user_id: int):
    result = await moderation_collection.find_one_and_update(
        {"chat_id": chat_id, "user_id": user_id},
        {
            "$inc": {"warnings": 1},
            "$setOnInsert": {"chat_id": chat_id, "user_id": user_id},
        },
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return result.get("warnings", 0)


async def reset_moderation_warnings(chat_id: int, user_id: int):
    await moderation_collection.update_one(
        {"chat_id": chat_id, "user_id": user_id},
        {"$set": {"warnings": 0}},
        upsert=True,
    )


async def close_db():
    mongo_client.close()
