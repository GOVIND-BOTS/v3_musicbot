import random
from pyrogram import filters
from pyrogram.types import ChatPermissions, ChatPrivileges
from pyrogram.enums import ChatType, ChatMemberStatus


# Random replies jab command incomplete ho
ADISA_TEXT = [
    "hey please don't disturb me.",
    "who are you?",
    "aap kon ho?",
    "aap mere owner to nhi lgte",
    "hey tum mera name kyu le rhe ho meko sone do",
    "ha bolo kya kaam hai",
    "dekho abhi mai busy hu",
    "hey i am busy",
    "aapko smj nhi aata kya",
    "leave me alone",
    "dude what happened?",
]

STRICT_TXT = [
    "i can't restrict against my besties",
    "are you serious i am not restrict to my friends",
    "mai apne dosto ko kyu restrict karu",
    "hey stupid admin",
    "i can't, he is my closest friend",
    "i love him please don't restrict this user",
]

# Keywords
BAN = ["ban", "boom"]
UNBAN = ["unban"]
MUTE = ["mute", "silent", "shut"]
UNMUTE = ["unmute", "speak", "free"]
KICK = ["kick", "out", "nikaal", "nikal"]
PROMOTE = ["promote", "adminship"]
DEMOTE = ["demote", "lelo"]


async def is_admin(client, chat_id, user_id):
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


def register_adisa_handlers(app, sudoers=None):
    """
    sudoers: set/list of sudo user ids (optional)
    """
    if sudoers is None:
        sudoers = set()
@app.on_message(
    filters.command(["adisa", "disa", "disha"], prefixes=["", "/", "!"])
    & filters.group
)
    async def adisa_handler(client, message):
        # Admin check
        if not await is_admin(client, message.chat.id, message.from_user.id):
            return await message.reply("Sirf admin is command ko use kar sakte hain.")

        reply = message.reply_to_message
        chat_id = message.chat.id

        # Agar sirf "adisa" / "disa" likha hai
        if len(message.text.split()) < 2:
            return await message.reply(random.choice(ADISA_TEXT))

        # Command ke baad ka text
        bruh = message.text.split(maxsplit=1)[1].lower()
        data = bruh.split()

        if not reply:
            return await message.reply("Kisi user ke message pe reply karke command do.")

        user_id = reply.from_user.id
        user_mention = reply.from_user.mention

        # ---------- BAN ----------
        for word in data:
            if word in BAN:
                if user_id in sudoers:
                    return await message.reply(random.choice(STRICT_TXT))
                try:
                    await client.ban_chat_member(chat_id, user_id)
                    await message.reply(f"OK, {user_mention} ko chod diya bhosdi wale ko ✅")
                except Exception as e:
                    await message.reply(f"Ban failed: {e}")
                return

        # ---------- UNBAN ----------
        for word in data:
            if word in UNBAN:
                try:
                    await client.unban_chat_member(chat_id, user_id)
                    await message.reply(f"OK, {user_mention} ko unban kar diya ✅")
                except Exception as e:
                    await message.reply(f"Unban failed: {e}")
                return

        # ---------- KICK ----------
        for word in data:
            if word in KICK:
                if user_id in sudoers:
                    return await message.reply(random.choice(STRICT_TXT))
                try:
                    await client.ban_chat_member(chat_id, user_id)
                    await client.unban_chat_member(chat_id, user_id)
                    await message.reply(f"{user_mention} ko nikaal diya ✅")
                except Exception as e:
                    await message.reply(f"Kick failed: {e}")
                return

        # ---------- MUTE ----------
        for word in data:
            if word in MUTE:
                if user_id in sudoers:
                    return await message.reply(random.choice(STRICT_TXT))
                try:
                    await client.restrict_chat_member(
                        chat_id,
                        user_id,
                        ChatPermissions(can_send_messages=False),
                    )
                    await message.reply(f"{user_mention} chud gya bsdka ✅")
                except Exception as e:
                    await message.reply(f"Mute failed: {e}")
                return

        # ---------- UNMUTE ----------
        for word in data:
            if word in UNMUTE:
                try:
                    await client.restrict_chat_member(
                        chat_id,
                        user_id,
                        ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_other_messages=True,
                            can_send_polls=True,
                            can_add_web_page_previews=True,
                            can_invite_users=True,
                        ),
                    )
                    await message.reply(f"{user_mention} ko chup kar diya ✅")
                except Exception as e:
                    await message.reply(f"Unmute failed: {e}")
                return

        # ---------- PROMOTE ----------
        for word in data:
            if word in PROMOTE:
                try:
                    await client.promote_chat_member(
                        chat_id,
                        user_id,
                        privileges=ChatPrivileges(
                            can_change_info=False,
                            can_invite_users=True,
                            can_delete_messages=True,
                            can_restrict_members=False,
                            can_pin_messages=True,
                            can_promote_members=False,
                            can_manage_chat=True,
                            can_manage_video_chats=True,
                        ),
                    )
                    await message.reply(f"{user_mention} ko promote kar diya ✅")
                except Exception as e:
                    await message.reply(f"Promote failed: {e}")
                return

        # ---------- DEMOTE ----------
        for word in data:
            if word in DEMOTE:
                try:
                    await client.promote_chat_member(
                        chat_id,
                        user_id,
                        privileges=ChatPrivileges(
                            can_change_info=False,
                            can_invite_users=False,
                            can_delete_messages=False,
                            can_restrict_members=False,
                            can_pin_messages=False,
                            can_promote_members=False,
                            can_manage_chat=False,
                            can_manage_video_chats=False,
                        ),
                    )
                    await message.reply(f"{user_mention} ko demote kar diya ✅")
                except Exception as e:
                    await message.reply(f"Demote failed: {e}")
                return

        # Agar koi valid keyword nahi mila
        await message.reply(random.choice(ADISA_TEXT))
