"""Owner-only commands to switch the bot's profile photo."""
import json
import logging
from pathlib import Path

import aiohttp
import aiohttp
from pyrogram import filters

from config import BOT_TOKEN
from owner_manager import is_main_owner

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"


def _make_avatar(brand):
    """Return the separately uploaded, high-quality brand DP."""
    if brand not in {"bebo", "v3music"}:
        raise ValueError("Unknown profile photo.")
    path = ASSET_DIR / f"{brand}_dp.jpg"
    if not path.is_file():
        raise FileNotFoundError(
            f"Missing {path.name}. Upload it to the repository assets/ folder."
        )
    return path


async def _set_bot_photo(brand):
    """Set the bot's own photo through the official Telegram Bot API."""
    path = _make_avatar(brand)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyProfilePhoto"
    form = aiohttp.FormData()
    form.add_field("photo", json.dumps({
        "type": "static", "photo": "attach://avatar"
    }), content_type="application/json")
    with path.open("rb") as photo:
        form.add_field("avatar", photo, filename=f"{brand}_dp.jpg",
                       content_type="image/jpeg")
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=45)
        ) as session:
            async with session.post(url, data=form) as response:
                result = await response.json(content_type=None)
    if not result.get("ok"):
        raise RuntimeError(result.get("description", "Telegram rejected the profile photo."))
    return True


def register_profile_dp_handlers(app):
    @app.on_message(filters.command(["bebo"]))
    async def set_bebo_dp(client, message):
        if not message.from_user or not is_main_owner(message.from_user.id):
            return await message.reply_text("⛔ Only the main owner can change the bot profile photo.")
        status = await message.reply_text("💜 Updating Bebo Music Bot profile photo...")
        try:
            await _set_bot_photo("bebo")
            await status.edit_text("✅ Bebo Music Bot profile photo updated successfully! 💜")
        except Exception as error:
            LOGGER.exception("Bebo profile photo update failed")
            await status.edit_text(f"❌ Could not update Bebo profile photo: {error}")

    @app.on_message(filters.command(["v3music", "v3"]))
    async def set_v3music_dp(client, message):
        if not message.from_user or not is_main_owner(message.from_user.id):
            return await message.reply_text("⛔ Only the main owner can change the bot profile photo.")
        status = await message.reply_text("💙 Updating V3MUSIC profile photo...")
        try:
            await _set_bot_photo("v3music")
            await status.edit_text("✅ V3MUSIC profile photo updated successfully! 💙")
        except Exception as error:
            LOGGER.exception("V3MUSIC profile photo update failed")
            await status.edit_text(f"❌ Could not update V3MUSIC profile photo: {error}")
