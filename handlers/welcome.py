import os
import tempfile
import logging

from pyrogram import filters
from pyrogram.types import ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)

# Welcome template image path
WELCOME_IMAGE = "assets/welcome.png"


def get_font(size):
    paths = [
        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]

    for path in paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    return ImageFont.load_default()


def fit_font(draw, text, max_width, size=27):
    while size >= 13:
        font = get_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)

        if bbox[2] - bbox[0] <= max_width:
            return font

        size -= 1

    return get_font(13)


def create_welcome_image(user_photo, user, chat):
    if not os.path.exists(WELCOME_IMAGE):
        raise FileNotFoundError(f"Welcome template not found: {WELCOME_IMAGE}")

    image = Image.open(WELCOME_IMAGE).convert("RGBA")

    # Scale all coordinates according to original template.
    base_w, base_h = 1536, 1024
    sx = image.width / base_w
    sy = image.height / base_h

    def pos(x, y):
        return (int(x * sx), int(y * sy))

    draw = ImageDraw.Draw(image)

    # --------------------------------
    # MEMBER PROFILE PHOTO - FULL CIRCLE
    # --------------------------------
    if user_photo and os.path.isfile(user_photo):
        try:
            avatar = Image.open(user_photo).convert("RGB")

            w, h = avatar.size
            crop = min(w, h)

            left = (w - crop) // 2
            top = (h - crop) // 2

            avatar = avatar.crop((
                left, top, left + crop, top + crop
            ))

            diameter = int(460 * sx)
            avatar = avatar.resize(
                (diameter, diameter),
                Image.Resampling.LANCZOS,
            )

            mask = Image.new("L", (diameter, diameter), 0)
            ImageDraw.Draw(mask).ellipse(
                (0, 0, diameter - 1, diameter - 1),
                fill=255,
            )

            # Center of the neon circular frame.
            center_x, center_y = pos(440, 445)

            x = center_x - diameter // 2
            y = center_y - diameter // 2

            image.paste(avatar, (x, y), mask)
        except Exception as e:
            LOGGER.warning(f"Failed to process user photo: {e}")

    # --------------------------------
    # MEMBER DETAILS
    # --------------------------------
    name = " ".join(
        p for p in (user.first_name, user.last_name) if p
    ) or "Unknown"

    user_id = str(user.id)
    username = f"@{user.username}" if user.username else "Not set"
    group_name = chat.title or "Unknown Group"

    joined = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%d %b %Y")

    values = [
        (name, 299, (0, 210, 255, 255)),
        (user_id, 364, (255, 45, 230, 255)),
        (username, 429, (0, 255, 210, 255)),
        (group_name, 494, (255, 190, 30, 255)),
        (joined, 559, (255, 65, 220, 255)),
    ]

    # Cover ONLY the value column, not the labels.
    for _, y, _ in values:
        x1, y1 = pos(1080, y - 5)
        x2, y2 = pos(1460, y + 48)

        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=int(5 * sx),
            fill=(5, 3, 24, 255),
        )

    # Draw dynamic values in their own column.
    draw = ImageDraw.Draw(image)

    for text, y, color in values:
        x, y_pos = pos(1095, y)

        font = fit_font(
            draw,
            text,
            max_width=int(345 * sx),
            size=int(27 * sx),
        )

        draw.text(
            (x, y_pos),
            text,
            font=font,
            fill=color,
            stroke_width=0,
        )

    output = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
    )

    output_path = output.name
    output.close()

    image.convert("RGB").save(output_path, "PNG")

    return output_path


def register_welcome_handlers(app):
    @app.on_chat_member_updated(filters.group)
    async def welcome_new_member(client, member: ChatMemberUpdated):
        try:
            # Only when a new user joins
            if not member.new_chat_member:
                return

            new_status = member.new_chat_member.status
            old_status = member.old_chat_member.status if member.old_chat_member else None

            # Check if user actually joined
            if new_status not in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.RESTRICTED,
            ):
                return

            if old_status in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
                ChatMemberStatus.RESTRICTED,
            ):
                return

            user = member.new_chat_member.user
            chat = member.chat

            # Ignore bots
            if user.is_bot:
                return

            user_photo = None
            welcome_path = None

            try:
                # Download user profile photo
                if user.photo:
                    user_photo = await client.download_media(
                        user.photo.big_file_id,
                        file_name=f"temp_{user.id}.jpg",
                    )

                # Create welcome image
                welcome_path = create_welcome_image(user_photo, user, chat)

                # Send welcome photo
                await client.send_photo(
                    chat.id,
                    photo=welcome_path,
                    caption=f"**✨ Welcome** {user.mention} **to** **{chat.title}**!",
                )

            except Exception as e:
                LOGGER.exception(f"Welcome message failed in {chat.id}")
                # Fallback text welcome
                try:
                    await client.send_message(
                        chat.id,
                        f"**✨ Welcome** {user.mention} **to** **{chat.title}**!",
                    )
                except Exception:
                    pass

            finally:
                # Cleanup temp files
                if user_photo and os.path.exists(user_photo):
                    try:
                        os.remove(user_photo)
                    except Exception:
                        pass

                if welcome_path and os.path.exists(welcome_path):
                    try:
                        os.remove(welcome_path)
                    except Exception:
                        pass

        except Exception:
            LOGGER.exception("Error in welcome handler")
