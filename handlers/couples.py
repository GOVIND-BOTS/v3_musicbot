import os
import uuid
import logging
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pyrogram import filters
from pyrogram.enums import ChatType, ParseMode
from pyrogram.errors import RPCError

logger = logging.getLogger(__name__)

DOWNLOAD_DIR = "downloads"
ASSET_DIR = "assets"
FONT_PATH = os.path.join(ASSET_DIR, "font.ttf")
FONT_BOLD_PATH = os.path.join(ASSET_DIR, "font2.ttf")

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def _font(size: int, bold: bool = False):
    path = FONT_BOLD_PATH if bold else FONT_PATH
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:
        return ImageFont.load_default()


def _make_avatar(path: str | None, size: int, label: str):
    """Return a circular avatar; generate a branded fallback if no photo exists."""
    if path and os.path.isfile(path):
        try:
            avatar = Image.open(path).convert("RGB")
            avatar = ImageOps.fit(avatar, (size, size), method=Image.Resampling.LANCZOS)
        except Exception:
            avatar = None
    else:
        avatar = None

    if avatar is None:
        avatar = Image.new("RGB", (size, size), (88, 38, 105))
        draw = ImageDraw.Draw(avatar)
        initials = (label or "V")[:1].upper()
        draw.text((size // 2, size // 2), initials, font=_font(size // 2, True),
                  fill=(255, 255, 255), anchor="mm")

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((2, 2, size - 3, size - 3), fill=255)
    result = avatar.convert("RGBA")
    result.putalpha(mask)
    return result


def _build_couples_card(first_avatar, second_avatar, output_path: str):
    """Build a V3 MUSIC couples card without relying on a missing template image."""
    width, height = 1100, 620
    image = Image.new("RGB", (width, height))
    pixels = image.load()

    # Deep violet-to-rose gradient background.
    for y in range(height):
        for x in range(width):
            blend = (x / (width - 1) * 0.55) + (y / (height - 1) * 0.25)
            blend = min(1.0, blend)
            pixels[x, y] = (
                int(18 + 62 * blend),
                int(12 + 13 * blend),
                int(42 + 48 * blend),
            )

    draw = ImageDraw.Draw(image, "RGBA")

    # Soft decorative rings and corner glows.
    for radius, alpha in ((250, 18), (205, 22), (160, 28)):
        draw.ellipse((width // 2 - radius, 105 - radius,
                      width // 2 + radius, 105 + radius),
                     outline=(255, 105, 175, alpha), width=3)

    draw.rounded_rectangle((35, 35, width - 35, height - 35),
                           radius=34, outline=(255, 190, 220, 115), width=3)

    title_font = _font(54, True)
    subtitle_font = _font(25)
    brand_font = _font(35, True)
    small_font = _font(20)

    draw.text((width // 2, 75), "TODAY'S COUPLES",
              font=title_font, fill=(255, 240, 248), anchor="mm")
    draw.text((width // 2, 125), "V3 MUSIC • LOVE IS IN THE AIR",
              font=subtitle_font, fill=(255, 180, 215), anchor="mm")

    avatar_size = 300
    first_x = 175
    second_x = width - 175 - avatar_size
    avatar_y = 205

    # Avatar frames.
    for x in (first_x, second_x):
        draw.ellipse((x - 10, avatar_y - 10, x + avatar_size + 10,
                      avatar_y + avatar_size + 10),
                     fill=(255, 105, 175, 70),
                     outline=(255, 220, 238, 240), width=7)

    image_rgba = image.convert("RGBA")
    image_rgba.alpha_composite(first_avatar, (first_x, avatar_y))
    image_rgba.alpha_composite(second_avatar, (second_x, avatar_y))
    image = image_rgba.convert("RGB")
    draw = ImageDraw.Draw(image)

    draw.text((width // 2, 350), "❤", font=_font(76, True),
              fill=(255, 92, 155), anchor="mm")
    draw.text((width // 2, 475), "MADE FOR EACH OTHER",
              font=subtitle_font, fill=(255, 224, 238), anchor="mm")

    # V3 MUSIC branding replaces the old BRANDED label.
    draw.rounded_rectangle((width // 2 - 130, 525, width // 2 + 130, 575),
                           radius=22, fill=(238, 55, 130))
    draw.text((width // 2, 550), "V3 MUSIC", font=brand_font,
              fill=(255, 255, 255), anchor="mm")
    draw.text((width // 2, 594), "POWERED BY V3 MUSIC",
              font=small_font, fill=(210, 190, 215), anchor="mm")

    image.save(output_path, "PNG", optimize=True)


async def _download_user_photo(client, user, path: str):
    try:
        fresh_user = await client.get_users(user.id)
        if fresh_user.photo:
            downloaded = await client.download_media(
                fresh_user.photo.big_file_id,
                file_name=path,
            )
            if downloaded and os.path.isfile(downloaded):
                return downloaded
    except Exception as exc:
        logger.debug("Could not download profile photo for %s: %s", user.id, exc)
    return None


def register_couples_handlers(app):
    @app.on_message(filters.command("couples") & filters.group)
    async def couples_command(client, message):
        status = await message.reply_text(
            "💞 ɢᴇɴᴇʀᴀᴛɪɴɢ ᴛᴏᴅᴀʏ's ᴄᴏᴜᴘʟᴇs..."
        )

        token = uuid.uuid4().hex
        first_path = os.path.join(DOWNLOAD_DIR, f"couple_{token}_1.jpg")
        second_path = os.path.join(DOWNLOAD_DIR, f"couple_{token}_2.jpg")
        output_path = os.path.join(DOWNLOAD_DIR, f"couple_{token}.png")

        try:
            members = []
            async for member in client.get_chat_members(message.chat.id, limit=50):
                user = member.user
                if user and not user.is_bot and not user.is_deleted:
                    members.append(user)

            if len(members) < 2:
                await status.edit_text(
                    "❌ At least 2 real members are required to select today's couple."
                )
                return

            # Select two distinct members.
            import random
            first_user, second_user = random.sample(members, 2)

            first_photo = await _download_user_photo(client, first_user, first_path)
            second_photo = await _download_user_photo(client, second_user, second_path)

            first_avatar = _make_avatar(
                first_photo, 300, first_user.first_name or "V"
            )
            second_avatar = _make_avatar(
                second_photo, 300, second_user.first_name or "V"
            )

            _build_couples_card(first_avatar, second_avatar, output_path)

            today = datetime.now().date()
            tomorrow = today + timedelta(days=1)
            caption = (
                "<b>💞 TODAY'S SELECTED COUPLE 🎉</b>\n"
                "━━━━━━━━━━━━━━━━━━\n\n"
                f"{first_user.mention} ❤️ {second_user.mention}\n\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"<b>📅 DATE:</b> {today.strftime('%d/%m/%Y')}\n"
                f"<b>💝 NEXT COUPLES:</b> {tomorrow.strftime('%d/%m/%Y')}\n\n"
                "<i>Powered by V3 MUSIC</i>"
            )

            await message.reply_photo(
                photo=output_path,
                caption=caption,
                parse_mode=ParseMode.HTML,
            )
            await status.delete()

        except RPCError as exc:
            logger.exception("Telegram error in /couples: %s", exc)
            try:
                await status.edit_text(
                    "❌ Telegram could not generate the couples image. Please try again."
                )
            except Exception:
                pass
        except Exception as exc:
            logger.exception("Unexpected /couples error: %s", exc)
            try:
                await status.edit_text(
                    "❌ Something went wrong while generating couples."
                )
            except Exception:
                pass
        finally:
            for path in (first_path, second_path, output_path):
                try:
                    if os.path.isfile(path):
                        os.remove(path)
                except OSError:
                    logger.warning("Could not remove temporary file: %s", path)

    logger.info("Couples handler registered")
