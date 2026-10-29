import random
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# List of Shayari
shayari_list = [
    "💖 *Mohabbat bhi ajeeb cheez hai…* \nKisi ko mile toh dard deta hai, \nKisi ko mile toh ilaj ban jata hai…",
    "💔 *Dil ki baat kehne ki ijaazat nahi hai,* \nIs mohabbat me itni shiddat nahi hai…",
    "🌙 *Chandni raaton me yaadon ka silsila rukta nahi,* \nJo door hote hain, zaroori nahi ke bhulaya jaye…",
    "❤️ *Mujhse ek waada karo, hamesha saath rahoge,* \nDukh aaye toh saath bitaoge, khushi aaye toh muskuraoge…",
    "😢 *Aansu bhi lete hain imtihaan, mohabbat ke raaste par…* \nKisi ko takleef dete hain, kisi ke zakhm bhar dete hain…",
    "🥀 *Mohabbat sirf kehne se nahi hoti,* \nUsko nibhana padta hai, apni jaan se bhi zyada…",
    "💞 *Tere bina adhura hoon,* \nJaise chaand bina roshni, jaise samundar bina lehar…",
    "🔥 *Meri mohabbat ka ehsaas toh tab hoga,* \nJab tere dil ko bhi dard hoga…",
    "💙 *Pyar ki chhoti si kahani hai,* \nEk dil hai, ek jaan hai, aur bas teri yaadon ki nishani hai…",
    "🌺 *Meri har saans teri mohabbat ki gawah hai,* \nAgar kabhi bhool jao toh dil se padh lena…"
]

@bot.on_message(filters.command("shayari") & filters.group)
async def send_shayari(client, message):
    user = message.from_user
    shayari = random.choice(shayari_list)

    # Fetch user profile photo
    profile_photos = await client.get_profile_photos(user.id, limit=1)
    if profile_photos:
        photo_id = profile_photos[0].file_id
    else:
        photo_id = None

    # Inline keyboard with "😍😍" button
    buttons = InlineKeyboardMarkup(
        [[InlineKeyboardButton("👑 Owner", url="https://t.me/govind_official_mp13")]]
    )

    # Send profile photo if available, otherwise send only text
    if photo_id:
        await message.reply_photo(
            photo_id, 
            caption=f"✨ *Shayari Time!* ✨\n\n{shayari}\n\n💫 *Dil se mehsoos karo!*",
            reply_markup=buttons
        )
    else:
        await message.reply_text(
            f"✨ *Shayari Time!* ✨\n\n{shayari}\n\n💫 *Dil se mehsoos karo!*",
            reply_markup=buttons
        )
