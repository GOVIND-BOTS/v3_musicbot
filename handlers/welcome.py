import os
import tempfile
import logging

from pyrogram import filters
from pyrogram.types import (
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.enums import ChatMemberStatus
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)

WELCOME_IMAGE = "assets/welcome.png"

# Sirf yeh 2 cheezein change karni hain
BOT_OWNER_USERNAME = "govind_officialmp13"               
SUPPORT_GROUP = "https://t.me/GOVIND_BOTS"   
CHANNEL_LINK = "https://t.me/GOVIND_USERBOT_UPDATE"         


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
    base_w, base_h = 1536, 1024
    sx = image.width / base_w
    sy = image.height / base_h

    def pos(x, y):
        return (int(x * sx), int(y * sy))

    draw = ImageDraw.Draw(image)

    # Profile Photo
    if user_photo and os.path.isfile(user_photo):
        try:
            avatar = Image.open(user_photo).convert("RGB")
            w, h = avatar.size
            crop = min(w, h)
            left = (w - crop) // 2
            top = (h - crop) // 2
            avatar = avatar.crop((left, top, left + crop, top + crop))

            diameter = int(445 * sx)
            avatar = avatar.resize((diameter, diameter), Image.Resampling.LANCZOS)

            mask = Image.new("L", (diameter, diameter), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, diameter - 1, diameter - 1), fill=255)

            center_x, center_y = pos(448, 448)
            x = center_x - diameter // 2
            y = center_y - diameter // 2
            image.paste(avatar, (x, y), mask)
        except Exception as e:
            LOGGER.warning(f"Failed to process user photo: {e}")

    # User Details
    name = " ".join(p for p in (user.first_name, user.last_name) if p) or "Unknown"
    user_id = str(user.id)
    username = f"@{user.username}" if user.username else "Not set"
    group_name = chat.title or "Unknown Group"
    joined = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%d %b %Y")

    values = [
        (name,       308, (0, 210, 255, 255)),
        (user_id,    373, (255, 45, 230, 255)),
        (username,   438, (0, 255, 210, 255)),
        (group_name, 503, (255, 190, 30, 255)),
        (joined,     568, (255, 65, 220, 255)),
    ]

    for _, y, _ in values:
        x1, y1 = pos(1080, y - 7)
        x2, y2 = pos(1465, y + 46)
        draw.rounded_rectangle((x1, y1, x2, y2), radius=int(6 * sx), fill=(5, 3, 24, 255))

    draw = ImageDraw.Draw(image)
    for text, y, color in values:
        x, y_pos = pos(1095, y)
        font = fit_font(draw, text, max_width=int(340 * sx), size=int(26 * sx))
        draw.text((x, y_pos), text, font=font, fill=color)

    output = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    output_path = output.name
    output.close()
    image.convert("RGB").save(output_path, "PNG")
    return output_path


def register_welcome_handlers(app):
    @app.on_chat_member_updated(filters.group)
    async def welcome_new_member(client, member: ChatMemberUpdated):
        try:
            if not member.new_chat_member:
                return

            new_status = member.new_chat_member.status
            old_status = member.old_chat_member.status if member.old_chat_member else None

            if new_status not in (ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED):
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

                welcome_path = create_welcome_image(user_photo, user, chat)

                # ========== GROUP OWNER AUTOMATIC DETECT ==========
                owner_btn = None
                try:
                    admins = await client.get_chat_administrators(chat.id)
                    for admin in admins:
                        if admin.status == ChatMemberStatus.OWNER:
                            owner_btn = InlineKeyboardButton(
                                "👑 Group Owner",
                                user_id=admin.user.id
                            )
                            break
                except Exception as e:
                    LOGGER.warning(f"Could not fetch group owner: {e}")

                # Agar owner nahi mila to fallback
                if not owner_btn:
                    owner_btn = InlineKeyboardButton(
                        "👑 Group Owner",
                        url=f"https://t.me/{chat.username}" if chat.username else "https://t.me/"
                    )

                
                buttons = [
                    [
                        owner_btn,
                        InlineKeyboardButton(
                            "👨‍💻 Bot Owner",
                            url=f"https://t.me/{BOT_OWNER_USERNAME}"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🛠 Support Group",
                            url=SUPPORT_GROUP
                        ),
                        InlineKeyboardButton(
                            "📢 Channel",
                            url=CHANNEL_LINK
                        ),
                    ],
                ]

                markup = InlineKeyboardMarkup(buttons)

                await client.send_photo(
                    chat.id,
                    photo=welcome_path,
                    caption=f"**✨ Welcome** {user.mention} **to** **{chat.title}**!",
                    reply_markup=markup,
                )

            except Exception as e:
                LOGGER.exception(f"Welcome message failed in {chat.id}")
                try:
                    await client.send_message(
                        chat.id,
                        f"**✨ Welcome** {user.mention} **to** **{chat.title}**!",
                    )
                except Exception:
                    pass

            finally:
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
