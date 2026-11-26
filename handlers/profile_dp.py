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
    """Create a neon circular music-logo avatar locally."""
    is_bebo = brand == "bebo"
    accent = (235, 20, 255) if is_bebo else (0, 185, 255)
    secondary = (255, 75, 190) if is_bebo else (70, 110, 255)
    image = Image.new("RGB", (640, 640), (2, 3, 12))
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((25, 25, 615, 615), fill=(*accent, 105))
    image = Image.alpha_composite(image.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(65)))
    d = ImageDraw.Draw(image)

    # Circular neon badge and subtle music-note decorations.
    d.ellipse((42, 42, 598, 598), fill=(3, 4, 15, 255), outline=(*accent, 255), width=10)
    d.ellipse((57, 57, 583, 583), outline=(*secondary, 210), width=3)
    for x, y in ((105, 235), (505, 235), (115, 455), (510, 455)):
        d.text((x, y), "♪", font=_font(43), fill=(*accent, 255))

    # Gold crown.
    crown = [(235, 175), (250, 95), (300, 145), (320, 75),
             (342, 145), (392, 95), (405, 175)]
    d.polygon(crown, fill=(255, 190, 35, 255), outline=(255, 230, 130, 255))
    d.rounded_rectangle((235, 165, 405, 190), radius=7,
                        fill=(255, 190, 35, 255), outline=(255, 230, 130, 255), width=3)
    for x, y in ((250, 95), (320, 75), (392, 95)):
        d.ellipse((x-7, y-7, x+7, y+7), fill=(255, 245, 185, 255))

    # Large headphones framing the logo text.
    d.arc((170, 125, 470, 430), 185, 355, fill=(*secondary, 255), width=24)
    d.rounded_rectangle((155, 260, 210, 385), radius=20,
                        fill=(8, 15, 35, 255), outline=(*accent, 255), width=9)
    d.rounded_rectangle((430, 260, 485, 385), radius=20,
                        fill=(8, 15, 35, 255), outline=(*accent, 255), width=9)
    d.rounded_rectangle((170, 280, 195, 365), radius=10, fill=(*secondary, 255))
    d.rounded_rectangle((445, 280, 470, 365), radius=10, fill=(*secondary, 255))

    title = "Bebo" if is_bebo else "V3MUSIC"
    title_font = _font(78 if is_bebo else 61)
    bbox = d.textbbox((0, 0), title, font=title_font, stroke_width=2)
    tw = bbox[2] - bbox[0]
    d.text(((640-tw)/2, 355), title, font=title_font,
           fill=(250, 250, 255, 255), stroke_width=2, stroke_fill=(*accent, 255))
    sub = "Music Bot" if is_bebo else "MUSIC BOT"
    sub_font = _font(38 if is_bebo else 31)
    bbox = d.textbbox((0, 0), sub, font=sub_font)
    sw = bbox[2] - bbox[0]
    d.text(((640-sw)/2, 465), sub, font=sub_font, fill=(*secondary, 255))
    tagline = "Feel The Music" if is_bebo else "Music Without Limits"
    tag_font = _font(20, False)
    bbox = d.textbbox((0, 0), tagline, font=tag_font)
    d.text(((640-(bbox[2]-bbox[0]))/2, 535), tagline, font=tag_font,
           fill=(225, 230, 250, 255))

    path = ASSET_DIR / f"{brand}_dp.jpg"
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, "JPEG", quality=96, optimize=True)
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
    @app.on_message(filters.regex(r"(?i)^bebo$"))
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

    @app.on_message(filters.regex(r"(?i)^v3music$"))
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
