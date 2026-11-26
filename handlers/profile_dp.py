"""Main-owner-only commands for switching the bot's profile photo."""
import json
import logging
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pyrogram import filters

from config import BOT_TOKEN
from owner_manager import is_main_owner

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "assets"


def _font(size, bold=True):
    """Load a widely available font, with a Pillow fallback."""
    candidates = (
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")
        if bold else
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")
    )
    for font_path in candidates:
        try:
            return ImageFont.truetype(font_path, size=size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _make_avatar(brand):
    """Generate a branded neon avatar without relying on external assets."""
    is_bebo = brand == "bebo"
    accent = (225, 35, 255) if is_bebo else (0, 180, 255)
    secondary = (255, 95, 205) if is_bebo else (65, 115, 255)

    image = Image.new("RGB", (640, 640), (2, 3, 13))
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse((24, 24, 616, 616), fill=(*accent, 125))
    image = Image.alpha_composite(
        image.convert("RGBA"),
        glow.filter(ImageFilter.GaussianBlur(58)),
    )
    draw = ImageDraw.Draw(image)

    # Neon circular frame.
    draw.ellipse((35, 35, 605, 605), fill=(3, 5, 17, 255),
                 outline=(*accent, 255), width=11)
    draw.ellipse((52, 52, 588, 588), outline=(*secondary, 220), width=3)

    # Music notes around the badge.
    note_font = _font(58)
    for x, y in ((82, 225), (505, 220), (95, 440), (505, 445)):
        draw.text((x, y), "♪", font=note_font, fill=(*accent, 255),
                  stroke_width=1, stroke_fill=(*secondary, 255))

    # Gold crown.
    crown = [(225, 177), (242, 100), (292, 145), (320, 68),
             (348, 145), (398, 100), (415, 177)]
    draw.polygon(crown, fill=(255, 190, 35, 255),
                 outline=(255, 232, 145, 255))
    draw.rounded_rectangle((225, 166, 415, 194), radius=8,
                           fill=(255, 190, 35, 255),
                           outline=(255, 232, 145, 255), width=4)
    for x, y in ((242, 100), (320, 68), (398, 100)):
        draw.ellipse((x - 8, y - 8, x + 8, y + 8),
                     fill=(255, 250, 210, 255))

    # Headphones and a glossy dark centre panel.
    draw.arc((155, 125, 485, 455), 185, 355,
             fill=(*secondary, 255), width=25)
    draw.rounded_rectangle((145, 255, 215, 405), radius=24,
                           fill=(7, 18, 43, 255),
                           outline=(*accent, 255), width=9)
    draw.rounded_rectangle((425, 255, 495, 405), radius=24,
                           fill=(7, 18, 43, 255),
                           outline=(*accent, 255), width=9)
    draw.rounded_rectangle((165, 280, 195, 380), radius=13,
                           fill=(*secondary, 255))
    draw.rounded_rectangle((445, 280, 475, 380), radius=13,
                           fill=(*secondary, 255))
    draw.rounded_rectangle((205, 205, 435, 410), radius=70,
                           fill=(4, 8, 22, 255),
                           outline=(190, 225, 255, 255), width=8)
    # Friendly glowing eyes.
    eye_y = 292
    for x in (270, 370):
        draw.arc((x - 24, eye_y - 15, x + 24, eye_y + 25),
                 195, 345, fill=(*accent, 255), width=10)

    title = "Bebo" if is_bebo else "V3MUSIC"
    title_size = 82 if is_bebo else 65
    title_font = _font(title_size)
    title_box = draw.textbbox((0, 0), title, font=title_font, stroke_width=2)
    while title_box[2] - title_box[0] > 540 and title_size > 40:
        title_size -= 2
        title_font = _font(title_size)
        title_box = draw.textbbox((0, 0), title, font=title_font, stroke_width=2)
    title_width = title_box[2] - title_box[0]
    draw.text(((640 - title_width) / 2, 405), title, font=title_font,
              fill=(250, 250, 255, 255), stroke_width=3,
              stroke_fill=(*accent, 255))

    subtitle = "Music Bot" if is_bebo else "MUSIC BOT"
    subtitle_font = _font(38 if is_bebo else 34)
    subtitle_box = draw.textbbox((0, 0), subtitle, font=subtitle_font)
    subtitle_width = subtitle_box[2] - subtitle_box[0]
    draw.text(((640 - subtitle_width) / 2, 500), subtitle,
              font=subtitle_font, fill=(*secondary, 255))

    tagline = "Feel The Music" if is_bebo else "Music Without Limits"
    tagline_font = _font(20, bold=False)
    tagline_box = draw.textbbox((0, 0), tagline, font=tagline_font)
    tagline_width = tagline_box[2] - tagline_box[0]
    draw.text(((640 - tagline_width) / 2, 555), tagline,
              font=tagline_font, fill=(225, 230, 250, 255))

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / f"{brand}_dp.jpg"
    image.convert("RGB").save(path, "JPEG", quality=95, optimize=True)
    return path


async def _set_bot_photo(brand):
    """Upload the selected photo using Telegram's Bot API."""
    path = _make_avatar(brand)
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setMyProfilePhoto"
    payload = {"type": "static", "photo": "attach://avatar"}
    timeout = aiohttp.ClientTimeout(total=45)

    with path.open("rb") as photo:
        form = aiohttp.FormData()
        form.add_field("photo", json.dumps(payload),
                       content_type="application/json")
        form.add_field("avatar", photo, filename=f"{brand}_dp.jpg",
                       content_type="image/jpeg")
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, data=form) as response:
                result = await response.json(content_type=None)

    if not isinstance(result, dict) or not result.get("ok"):
        reason = result.get("description", "Telegram rejected the profile photo.") if isinstance(result, dict) else "Invalid response from Telegram."
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
        except Exception:
            LOGGER.exception("%s profile photo update failed", label)
            await status.edit_text(
                f"❌ Could not update {label} profile photo. "
                "Check the bot API response and logs."
            )

    @app.on_message(filters.regex(r"(?i)^/?bebo(?:@\w+)?$"))
    async def set_bebo_dp(client, message):
        await change_photo(message, "bebo")

    @app.on_message(filters.regex(r"(?i)^/?(?:v3|v3music)(?:@\w+)?$"))
    async def set_v3music_dp(client, message):
        await change_photo(message, "v3music")
