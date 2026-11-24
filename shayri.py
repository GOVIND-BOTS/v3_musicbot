
import random
import logging

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

LOGGER = logging.getLogger(__name__)


shayari_list = [
    "💖 *Love is a strange thing…*\\nFor some, it brings pain,\\nFor others, it becomes a cure…",

    "💔 *I have no permission to speak my heart,*\\nYet this love has no lack of intensity…",

    "🌙 *The memories never fade on moonlit nights,*\\nDistance does not mean someone must be forgotten…",

    "❤️ *Promise me that you will always stay by my side,*\\nShare my sorrows and smile with me in happiness…",

    "😢 *Love puts every heart through a test…*\\nSome wounds cause pain, while others help heal…",

    "🥀 *Love is more than just words,*\\nIt takes devotion beyond measure to keep it alive…",

    "💞 *Without you, I feel incomplete,*\\nLike the moon without light or the ocean without waves…",

    "🔥 *You will understand the depth of my love,*\\nWhen your own heart feels the same ache…",

    "💙 *Ours is a little story of love,*\\nOne heart, one soul, and memories of you…",

    "🌺 *Every breath of mine bears witness to my love for you,*\\nIf you ever forget, read it with your heart…"
]


def register_shayari_handlers(app):

    @app.on_message(
        filters.regex(r"(?i)^/?shayari$") & filters.group
    )
    async def send_shayari(client, message):

        shayari = random.choice(shayari_list)

        buttons = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "👑 Owner",
                        url="https://t.me/govind_official_mp13",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Next Shayari",
                        callback_data="next_shayari",
                    )
                ],
            ]
        )

        caption = (
            "✨ *Shayari Time!* ✨\n\n"
            f"{shayari}\n\n"
            "💫 *Feel it with your heart!*"
        )

        try:
            user = message.from_user

            if user:
                photos = await client.get_profile_photos(
                    user.id,
                    limit=1,
                )

                if photos:
                    await message.reply_photo(
                        photo=photos[0].file_id,
                        caption=caption,
                        reply_markup=buttons,
                    )
                    return

            await message.reply_text(
                caption,
                reply_markup=buttons,
            )

        except Exception:
            LOGGER.exception("Shayari command failed")

            await message.reply_text(
                caption,
                reply_markup=buttons,
            )

    @app.on_callback_query(
        filters.regex("^next_shayari$")
    )
    async def next_shayari(client, callback_query):

        shayari = random.choice(shayari_list)

        caption = (
            "✨ *Shayari Time!* ✨\n\n"
            f"{shayari}\n\n"
            "💫 *Dil se mehsoos karo!*"
        )

        await callback_query.message.edit_caption(
            caption=caption
        )

        await callback_query.answer(
            "❤️ Here is a new shayari!"
        )
