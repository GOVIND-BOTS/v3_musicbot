"""Owner-only commands to switch the bot's profile photo."""
import io
import json
import logging
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pyrogram import filters

from config import BOT_TOKEN
from owner_manager import is_main_owner

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"


def _font(size, bold=True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for path in (f"/usr/share/fonts/truetype/dejavu/{name}", str(ASSET_DIR / "font.ttf")):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _make_avatar(brand):
    """Create the selected 640x640 neon avatar locally on first use."""
    is_bebo = brand == "bebo"
    accent = (235, 35, 255) if is_bebo else (0, 190, 255)
    secondary = (255, 105, 210) if is_bebo else (65, 115, 255)
    image = Image.new("RGB", (640, 640), (4, 6, 18))
    pixels = image.load()
    for y in range(640):
        for x in range(640):
            glow = max(0, 1 - (((x-320)**2 + (y-320)**2)**0.5)/470)
            pixels[x, y] = (4 + int(accent[0]*glow*.10),
                            6 + int(accent[1]*glow*.10),
                            18 + int(accent[2]*glow*.18))
    haze = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(haze).ellipse((55, 55, 585, 585), fill=(*accent, 85))
    image = Image.alpha_composite(image.convert("RGBA"), haze.filter(ImageFilter.GaussianBlur(52)))
    d = ImageDraw.Draw(image)

    # Neon frame, crown and headphone-wearing robot mascot.
    d.ellipse((43, 43, 597, 597), outline=(*accent, 255), width=9)
    d.ellipse((61, 61, 579, 579), outline=(*secondary, 180), width=3)
    d.polygon([(250, 150), (267, 95), (310, 132), (340, 82),
               (370, 132), (413, 95), (430, 150)], fill=(255, 194, 60, 255))
    d.rounded_rectangle((250, 145, 430, 174), radius=8,
                        fill=(255, 190, 55, 255), outline=(255, 235, 170, 255), width=3)
    d.arc((155, 155, 485, 485), 185, 355, fill=(*accent, 255), width=22)
    d.rounded_rectangle((145, 275, 205, 405), radius=22,
                        fill=(12, 18, 38, 255), outline=(*accent, 255), width=8)
    d.rounded_rectangle((435, 275, 495, 405), radius=22,
                        fill=(12, 18, 38, 255), outline=(*accent, 255), width=8)
    d.rounded_rectangle((205, 210, 435, 425), radius=70,
                        fill=(7, 13, 29, 255), outline=(190, 225, 255, 255), width=7)
    if is_bebo:
        d.arc((250, 270, 300, 325), 195, 345, fill=(*secondary, 255), width=10)
        d.arc((340, 270, 390, 325), 195, 345, fill=(*secondary, 255), width=10)
        d.arc((278, 315, 362, 380), 15, 165, fill=(255, 220, 245, 255), width=8)
        d.ellipse((228, 340, 250, 356), fill=(255, 90, 170, 190))
        d.ellipse((390, 340, 412, 356), fill=(255, 90, 170, 190))
    else:
        d.line((250, 292, 300, 292), fill=(*accent, 255), width=14)
        d.line((340, 292, 390, 292), fill=(*accent, 255), width=14)
        d.line([(260, 355), (280, 333), (300, 365), (320, 340),
                (340, 362), (360, 333), (385, 355)],
               fill=(210, 245, 255, 255), width=7, joint="curve")

    d.text((95, 205), "♪", font=_font(48), fill=(*accent, 255))
    d.text((485, 205), "♫", font=_font(48), fill=(*secondary, 255))
    title = "Bebo" if is_bebo else "V3MUSIC"
    font = _font(68 if is_bebo else 57)
    box = d.textbbox((0, 0), title, font=font, stroke_width=2)
    d.text(((640-(box[2]-box[0]))/2, 440), title, font=font,
           fill=(250, 252, 255, 255), stroke_width=2, stroke_fill=(*accent, 255))
    subfont = _font(25)
    sub = "MUSIC BOT"
    box = d.textbbox((0, 0), sub, font=subfont)
    d.text(((640-(box[2]-box[0]))/2, 525), sub, font=subfont, fill=(*secondary, 255))
    path = ASSET_DIR / f"{brand}_dp.jpg"
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(path, "JPEG", quality=94, optimize=True)
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
