
import asyncio
import logging

from database.mongodb import database
import os

LOGGER = logging.getLogger(__name__)

MAX_CLONES = max(1, int(os.getenv("MAX_CLONES", "5")))

clone_col = database["clones"]

_save_lock = asyncio.Lock()


async def save_clone(
    owner_id: int,
    bot_token: str,
    bot_username: str = None,
):
    owner_id = int(owner_id)
    bot_token = bot_token.strip()

    if not bot_token:
        return False

    async with _save_lock:
        existing = await clone_col.find_one(
            {"bot_token": bot_token}
        )

        if existing:
            if existing.get("is_active", True):
                return False

            await clone_col.update_one(
                {"_id": existing["_id"]},
                {
                    "$set": {
                        "is_active": True,
                        "owner_id": owner_id,
                        "bot_username": bot_username,
                    }
                },
            )
            return True

        count = await count_active_clones()

        if count >= MAX_CLONES:
            return False

        await clone_col.insert_one(
            {
                "owner_id": owner_id,
                "bot_token": bot_token,
                "bot_username": bot_username,
                "is_active": True,
            }
        )

        return True


async def get_all_clones():
    cursor = clone_col.find(
        {"is_active": True}
    ).sort("_id", 1)

    return await cursor.to_list(length=MAX_CLONES)


async def get_clone_by_token(bot_token: str):
    return await clone_col.find_one(
        {
            "bot_token": bot_token,
            "is_active": True,
        }
    )


async def remove_clone(bot_token: str):
    result = await clone_col.update_one(
        {
            "bot_token": bot_token,
            "is_active": True,
        },
        {
            "$set": {
                "is_active": False,
            }
        },
    )

    return result.modified_count > 0


async def is_token_exist(bot_token: str):
    data = await clone_col.find_one(
        {
            "bot_token": bot_token,
            "is_active": True,
        }
    )

    return bool(data)


async def count_active_clones():
    return await clone_col.count_documents(
        {"is_active": True}
    )


async def get_clones_by_owner(owner_id: int):
    cursor = clone_col.find(
        {
            "owner_id": int(owner_id),
            "is_active": True,
        }
    ).sort("_id", 1)

    return await cursor.to_list(length=MAX_CLONES)
