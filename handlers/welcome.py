
import os
import tempfile
import logging

from datetime import datetime
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont
from pyrogram import filters
from pyrogram.types import ChatMemberUpdated
from pyrogram.enums import ChatMemberStatus

LOGGER = logging.getLogger(__name__)

WELCOME_IMAGE = "assets/welcome.png"

# Actual template dimensions
BASE_WIDTH = 1536
BASE_HEIGHT = 864


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


def fit_font(draw, text, max_width, size=26):
    while size >= 13:
        font = get_font(size)
        bbox = draw.textbbox((0, 0), text, font=font)

        if bbox[2] - bbox[0] <= max_width:
            return font

        size -= 1

    return get_font(13)


def create_welcome_image(user_photo, user, chat):
    if not os.path.exists(WELCOME_IMAGE):
        raise FileNotFoundError(
            f"Welcome template not found: {WELCOME_IMAGE}"
        )

    image = Image.open(WELCOME_IMAGE).convert("RGBA")

    sx = image.width / BASE_WIDTH
    sy = image.height / BASE_HEIGHT

    def pos(x, y):
        return int(x * sx), int(y * sy)

    draw = ImageDraw.Draw(image)

    # -----------------------------------------
    # USER PROFILE PHOTO - PERFECT CIRCLE
    # -----------------------------------------

    if user_photo and os.path.isfile(user_photo):
        try:
            avatar = Image.open(user_photo).convert("RGB")

            width, height = avatar.size
            crop_size = min(width, height)

            left = (width - crop_size) // 2
            top = (height - crop_size) // 2

            avatar = avatar.crop((
                left,
                top,
                left + crop_size,
                top + crop_size,
            ))

            diameter = int(420 * sx)

            avatar = avatar.resize(
                (diameter, diameter),
                Image.Resampling.LANCZOS,
            )

            # Circular mask
            mask = Image.new("L", (diameter, diameter), 0)

            mask_draw = ImageDraw.Draw(mask)
            mask_draw.ellipse(
                (0, 0, diameter - 1, diameter - 1),
                fill=255,
            )

            # Correct center for 1536x864 template
            center_x, center_y = pos(445, 420)

            x = center_x - diameter // 2
            y = center_y - diameter // 2

            image.paste(avatar, (x, y), mask)

        except Exception:
            LOGGER.exception("Failed to process user profile photo")

    # -----------------------------------------
    # USER INFORMATION
    # -----------------------------------------

    name = " ".join(
        part for part in (user.first_name, user.last_name) if part
    ) or "Unknown"

    user_id = str(user.id)

    username = (
        f"@{user.username}"
        if user.username
        else "Not Set"
    )

    group_name = chat.title or "Unknown Group"

    joined = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%d %b %Y")

    # Row center positions for the actual template
    values = [
        (name, 315, (0, 210, 255, 255)),
        (user_id, 380, (255, 45, 230, 255)),
        (username, 445, (0, 255, 210, 255)),
        (group_name, 510, (255, 190, 30, 255)),
        (joined, 575, (255, 65, 220, 255)),
    ]

    # -----------------------------------------
    # COVER OLD SAMPLE INFORMATION
    # -----------------------------------------

    draw = ImageDraw.Draw(image)

    for _, center_y, _ in values:
        x1, y1 = pos(1080, center_y - 27)
        x2, y2 = pos(1465, center_y + 27)

        draw.rounded_rectangle(
            (x1, y1, x2, y2),
            radius=int(7 * sx),
            fill=(5, 3, 24, 255),
        )

    # -----------------------------------------
    # DRAW NEW INFORMATION
    # -----------------------------------------

    draw = ImageDraw.Draw(image)

    for text, center_y, color in values:
        x, y = pos(1095, center_y)

        font = fit_font(
            draw,
            text,
            max_width=int(350 * sx),
            size=int(26 * sx),
        )

        draw.text(
            (x, y),
            text,
            font=font,
            fill=color,
            anchor="lm",
        )

    # -----------------------------------------
    # SAVE IMAGE
    # -----------------------------------------

    output = tempfile.NamedTemporaryFile(
        suffix=".png",
        delete=False,
    )

    output_path = output.name
    output.close()

    image.convert("RGB").save(
        output_path,
        format="PNG",
        quality=95,
    )

    return output_path


# =============================================
# WELCOME HANDLER
# =============================================

def register_welcome_handlers(app):

    @app.on_chat_member_updated(filters.group)
    async def welcome_new_member(client, member: ChatMemberUpdated):
        try:
            if not member.new_chat_member:
                return

            new_status = member.new_chat_member.status

            old_status = (
                member.old_chat_member.status
                if member.old_chat_member
                else None
            )

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

            if user.is_bot:
                return

            user_photo = None
            welcome_path = None

            try:
                if user.photo:
                    user_photo = await client.download_media(
                        user.photo.big_file_id,
                        file_name=f"temp_{user.id}.jpg",
                    )

                welcome_path = create_welcome_image(
                    user_photo,
                    user,
                    chat,
                )

                await client.send_photo(
                    chat.id,
                    photo=welcome_path,
                    caption=(
                        f"**✨ Welcome** {user.mention} "
                        f"**to** **{chat.title}**!"
                    ),
                )

            except Exception:
                LOGGER.exception(
                    "Welcome message failed in chat %s",
                    chat.id,
                )

                try:
                    await client.send_message(
                        chat.id,
                        (
                            f"**✨ Welcome** {user.mention} "
                            f"**to** **{chat.title}**!"
                        ),
                    )
                except Exception:
                    LOGGER.exception("Fallback welcome message failed")

            finally:
                for file_path in (user_photo, welcome_path):
                    if file_path and os.path.isfile(file_path):
                        try:
                            os.remove(file_path)
                        except OSError:
                            LOGGER.warning(
                                "Could not remove temporary file: %s",
                                file_path,
                            )

        except Exception:
            LOGGER.exception("Error in welcome handler")
