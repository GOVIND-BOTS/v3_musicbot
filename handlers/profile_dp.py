"""Main-owner-only commands for switching the bot's profile photo.

Place the two matching JPEG files in the repository's assets/ directory:
    assets/bebo_dp.jpg
    assets/v3music_dp.jpg
"""
import io
import json
import logging
from pathlib import Path

import aiohttp
from PIL import Image, ImageOps
from pyrogram import filters

from config import BOT_TOKEN
from owner_manager import is_main_owner

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"

PROFILE_PHOTOS = {
    "bebo": ASSET_DIR / "bebo_dp.jpg",
    "v3music": ASSET_DIR / "v3music_dp.jpg",
}

TELEGRAM_AVATAR_SIZE = (640, 640)


def _prepare_profile_photo(path):
    """Return a Telegram-ready square JPEG in memory."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source)
        if image.mode in ("RGBA", "LA") or "transparency" in image.info:
            rgba = image.convert("RGBA")
            background = Image.new("RGBA", rgba.size, (0, 0, 0, 255))
            background.alpha_composite(rgba)
            image = background.convert("RGB")
        else:
            image = image.convert("RGB")

        image = ImageOps.fit(
            image,
            TELEGRAM_AVATAR_SIZE,
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=95, optimize=True)
        output.seek(0)
        return output


async def _set_bot_photo(brand):
    """Upload the selected, normalized JPEG using Telegram's Bot API."""
    path = PROFILE_PHOTOS[brand]
    if not path.is_file():
        raise FileNotFoundError(
            f"Profile photo not found: {path}. "
            "Add the matching image to the repository's assets/ folder."
        )

    photo = _prepare_profile_photo(path)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyProfilePhoto"
    payload = {"type": "static", "photo": "attach://avatar"}
    timeout = aiohttp.ClientTimeout(total=45)

    form = aiohttp.FormData()
    form.add_field(
        "photo", json.dumps(payload), content_type="application/json"
    )
    form.add_field(
        "avatar",
        photo,
        filename=f"{brand}_profile.jpg",
        content_type="image/jpeg",
    )

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, data=form) as response:
            result = await response.json(content_type=None)

    if not isinstance(result, dict) or not result.get("ok"):
        reason = (
            result.get("description", "Telegram rejected the profile photo.")
            if isinstance(result, dict)
            else "Invalid response from Telegram."
        )
        raise RuntimeError(reason)
    return True


def register_profile_dp_handlers(app):
    async def change_photo(message, brand):
        if not message.from_user or not is_main_owner(message.from_user.id):
            return await message.reply_text(
                "⛔ Only the main owner can change the bot profile photo."
            )

        label = "Bebo Music Bot" if brand == "bebo" else "V3MUSIC"
        emoji = "💜" if brand == "bebo" else "💙"
        status = await message.reply_text(
            f"{emoji} Updating {label} profile photo..."
        )
        try:
            await _set_bot_photo(brand)
            await status.edit_text(
                f"✅ {label} profile photo updated successfully! {emoji}"
            )
        except Exception as exc:
            LOGGER.exception("%s profile photo update failed", label)
            await status.edit_text(
                f"❌ Could not update {label} profile photo: {exc}"
            )

    @app.on_message(filters.regex(r"(?i)^/?bebo(?:@\w+)?$"))
    async def set_bebo_dp(client, message):
        await change_photo(message, "bebo")

    @app.on_message(filters.regex(r"(?i)^/?(?:v3|v3music)(?:@\w+)?$"))
    async def set_v3music_dp(client, message):
        await change_photo(message, "v3music")
