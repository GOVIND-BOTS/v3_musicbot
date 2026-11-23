import os
import re

from config import MAIN_OWNER_ID
from database.mongodb import settings_collection


async def get_public_owner():
    """Return the public owner profile; the secure main owner stays in env."""
    try:
        record = await settings_collection.find_one({"_id": "public_owner"}) or {}
    except Exception:
        record = {}
    username = (record.get("username") or os.getenv("PUBLIC_OWNER_USERNAME", "")).strip().lstrip("@")
    user_id = record.get("user_id") or MAIN_OWNER_ID
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        user_id = MAIN_OWNER_ID
    return {"user_id": user_id, "username": username or None}


async def get_owner_url():
    profile = await get_public_owner()
    if profile["username"]:
        return f"https://t.me/{profile['username']}"
    return f"tg://user?id={profile['user_id']}"


def is_main_owner(user_id):
    try:
        return int(user_id) == int(MAIN_OWNER_ID)
    except (TypeError, ValueError):
        return False


async def set_public_owner(value):
    """Only called by the main-owner-only handler."""
    value = str(value or "").strip()
    if value.lower() in {"default", "reset", "main"}:
        await settings_collection.delete_one({"_id": "public_owner"})
        return await get_public_owner()

    if value.startswith("@"):
        value = value[1:]
    if re.fullmatch(r"[A-Za-z0-9_]{5,32}", value):
        await settings_collection.update_one(
            {"_id": "public_owner"},
            {"$set": {"username": value, "user_id": MAIN_OWNER_ID}},
            upsert=True,
        )
    elif value.isdigit() and 5 <= len(value) <= 15:
        await settings_collection.update_one(
            {"_id": "public_owner"},
            {"$set": {"user_id": int(value), "username": None}},
            upsert=True,
        )
    else:
        raise ValueError("Use @username, a numeric Telegram user ID, or default.")
    return await get_public_owner()
