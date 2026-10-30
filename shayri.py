
import random
import logging

from pyrogram import filters
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

LOGGER = logging.getLogger(__name__)


shayari_list = [
    "💖 *Mohabbat bhi ajeeb cheez hai…*\nKisi ko mile toh dard deta hai,\nKisi ko mile toh ilaj ban jata hai…",

    "💔 *Dil ki baat kehne ki ijaazat nahi hai,*\nIs mohabbat me itni shiddat nahi hai…",

    "🌙 *Chandni raaton me yaadon ka silsila rukta nahi,*\nJo door hote hain, zaroori nahi ke bhulaya jaye…",

    "❤️ *Mujhse ek waada karo, hamesha saath rahoge,*\nDukh aaye toh saath bitaoge, khushi aaye toh muskuraoge…",

    "😢 *Aansu bhi lete hain imtihaan, mohabbat ke raaste par…*\nKisi ko takleef dete hain, kisi ke zakhm bhar dete hain…",

    "🥀 *Mohabbat sirf kehne se nahi hoti,*\nUsko nibhana padta hai, apni jaan se bhi zyada…",

    "💞 *Tere bina adhura hoon,*\nJaise chaand bina roshni, jaise samundar bina lehar…",

    "🔥 *Meri mohabbat ka ehsaas toh tab hoga,*\nJab tere dil ko bhi dard hoga…",

    "💙 *Pyar ki chhoti si kahani hai,*\nEk dil hai, ek jaan hai, aur bas teri yaadon ki nishani hai…",

    "🌺 *Meri har saans teri mohabbat ki gawah hai,*\nAgar kabhi bhool jao toh dil se padh lena…"
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
            "💫 *Dil se mehsoos karo!*"
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
            "❤️ New Shayari!"
        )
