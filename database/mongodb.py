import os
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_DB_URI

mongo_client = AsyncIOMotorClient(MONGO_DB_URI, serverSelectionTimeoutMS=10000)
database = mongo_client[os.getenv("MONGO_DB_NAME", "v3_musicbot")]
users_collection = database["users"]
chats_collection = database["chats"]
settings_collection = database["settings"]
queue_collection = database["queues"]
playlists_collection = database["playlists"]

async def ping_db():
    await mongo_client.admin.command("ping")
    return True

async def add_user(user_id: int):
    await users_collection.update_one({"_id": user_id}, {"$setOnInsert": {"_id": user_id}}, upsert=True)

async def remove_user(user_id: int):
    await users_collection.delete_one({"_id": user_id})

async def get_users():
    return await users_collection.distinct("_id")

async def add_chat(chat_id: int):
    await chats_collection.update_one({"_id": chat_id}, {"$setOnInsert": {"_id": chat_id}}, upsert=True)

async def remove_chat(chat_id: int):
    await chats_collection.delete_one({"_id": chat_id})

async def get_chats():
    return await chats_collection.distinct("_id")

async def get_chat_settings(chat_id: int):
    return await settings_collection.find_one({"_id": chat_id}) or {"_id": chat_id}

async def update_chat_settings(chat_id: int, key: str, value):
    await settings_collection.update_one({"_id": chat_id}, {"$set": {key: value}}, upsert=True)

async def delete_chat_settings(chat_id: int):
    await settings_collection.delete_one({"_id": chat_id})

async def save_queue(chat_id: int, tracks: list):
    await queue_collection.update_one({"_id": chat_id}, {"$set": {"tracks": tracks}}, upsert=True)

async def get_queue(chat_id: int):
    data = await queue_collection.find_one({"_id": chat_id})
    return data.get("tracks", []) if data else []

async def clear_queue(chat_id: int):
    await queue_collection.delete_one({"_id": chat_id})

async def save_playlist(user_id: int, name: str, tracks: list):
    await playlists_collection.update_one({"user_id": user_id, "name": name}, {"$set": {"tracks": tracks}}, upsert=True)

async def get_playlist(user_id: int, name: str):
    data = await playlists_collection.find_one({"user_id": user_id, "name": name})
    return data.get("tracks", []) if data else []

async def get_user_playlists(user_id: int):
    return await playlists_collection.find({"user_id": user_id}, {"name": 1, "_id": 0}).to_list(length=None)

async def delete_playlist(user_id: int, name: str):
    await playlists_collection.delete_one({"user_id": user_id, "name": name})

async def close_db():
    mongo_client.close()
