import asyncio
import random
from pyrogram import filters
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import UserNotParticipant

spam_chats = []

EMOJI = [
    "🦋🦋🦋🦋🦋", "🧚🌸🧋🍬🫖", "🥀🌷🌹🌺💐", "🌸🌿💮🌱🌵",
    "❤️💚💙💜🖤", "💓💕💞💗💖", "🌸💐🌺🌹🦋", "🍎🍓🍒🍑🌶️",
]

TAGMES = [
    "**Hey Baby Kaha Ho 🥱**",
    "**Oye So Gye Kya Online Aao 😊**",
    "**Vc Chalo Baten Karte Hain 😃**",
    "**Khana Kha Liye Ji..?? 🥲**",
    "**Ghar Me Sab Kaise Hain Ji 🥺**",
    "**Pta Hai Bohot Miss Kar Rhi Thi Aapko 🤭**",
    "**Oye Hal Chal Kesa Hai..?? 🤨**",
    "**Hello Ji Namaste 😛**",
    "**Hello Baby Kkrh..? 🤔**",
    "**Aur Batao Kaise Ho Baby 😇**",
    "**Mere Se Dosthi Krogen..?? 🤔**",
    "**Sone Chal Gye Kya 🙄**",
    "**Ek Song Play Kro Na Plss 😕**",
    "**Aap Kaha Se Ho..?? 🙃**",
    "**Nice To Meet Uh ☺**",
    "**Hello 🙊**",
    "**Bol Na Kuch Yrr 🥲**",
    "**I Love You 🙈**",
    "**Do You Love Me..? 👀**",
    "**Khush Raha Karo ✌️**",
]


def register_tagall_handlers(app):
    @app.on_message(filters.command(["tagall", "all", "tagmember"], prefixes=["/", "@", "#"]))
    async def mentionall(client, message):
        chat_id = message.chat.id

        if message.chat.type == ChatType.PRIVATE:
            return await message.reply("Yeh command sirf groups mein kaam karta hai!")

        # Admin check
        is_admin = False
        try:
            participant = await client.get_chat_member(chat_id, message.from_user.id)
            if participant.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                is_admin = True
        except UserNotParticipant:
            pass

        if not is_admin:
            return await message.reply("Sirf admin is command ko use kar sakte hain.")

        if chat_id in spam_chats:
            return await message.reply("Pehle current process stop karo (`/cancel`).")

        spam_chats.append(chat_id)
        usrnum = 0
        usrtxt = ""

        async for usr in client.get_chat_members(chat_id):
            if chat_id not in spam_chats:
                break
            if usr.user.is_bot:
                continue

            usrnum += 1
            usrtxt += f"[{usr.user.first_name}](tg://user?id={usr.user.id}) "

            if usrnum == 5:  # 5 members per message (spam kam)
                txt = f"{usrtxt}\n{random.choice(TAGMES)}"
                try:
                    await client.send_message(chat_id, txt)
                except Exception:
                    pass
                await asyncio.sleep(3)
                usrnum = 0
                usrtxt = ""

        try:
            spam_chats.remove(chat_id)
        except Exception:
            pass

    @app.on_message(filters.command(["cancel", "stop"]))
    async def cancel_spam(client, message):
        if message.chat.id not in spam_chats:
            return await message.reply("Koi active mention process nahi hai.")

        is_admin = False
        try:
            participant = await client.get_chat_member(message.chat.id, message.from_user.id)
            if participant.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                is_admin = True
        except Exception:
            pass

        if not is_admin:
            return await message.reply("Sirf admin stop kar sakte hain.")

        try:
            spam_chats.remove(message.chat.id)
        except Exception:
            pass
        await message.reply("Mention process stopped.")
