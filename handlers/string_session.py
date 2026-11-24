import logging
from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.errors import SessionPasswordNeeded
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import API_ID, API_HASH

LOG = logging.getLogger(__name__)
FLOW = {}

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Pyrogram", callback_data="gensess|pyro"),
         InlineKeyboardButton("Telegram", callback_data="gensess|tele")],
        [InlineKeyboardButton("Cancel", callback_data="gensess|cancel")]
    ])

def account_menu(kind):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("User Account", callback_data=f"gensess|{kind}_user"),
         InlineKeyboardButton("Bot Account", callback_data=f"gensess|{kind}_bot")],
        [InlineKeyboardButton("Cancel", callback_data="gensess|cancel")]
    ])

async def close_worker(state):
    worker = state.get("worker") if state else None
    if worker:
        try:
            await worker.disconnect()
        except Exception:
            pass

def register_string_session_handlers(app):
    @app.on_message(filters.command("genstring") & filters.private)
    async def genstring(_, message):
        if not message.from_user:
            return
        uid = message.from_user.id
        if uid in FLOW:
            await close_worker(FLOW.pop(uid, None))
        await message.reply_text(
            "🔐 <b>String Session Generator</b>\nChoose the session type. "
            "Available to all users in private chat. Generate sessions only for accounts/bots you own. OTP/password and generated sessions are secrets; the result is sent only to your own chat.",
            reply_markup=menu()
        )

    @app.on_callback_query(filters.regex(r"^gensess\\|"))
    async def choose(_, query):
        if not query.message or query.message.chat.type != ChatType.PRIVATE:
            return await query.answer("Please open /genstring in this private chat.", show_alert=True)
        uid = query.from_user.id
        kind = query.data.split("|", 1)[1]
        await query.answer()
        if kind == "cancel":
            state = FLOW.pop(uid, None)
            await close_worker(state)
            return await query.message.edit_text("❎ Cancelled.")
        if kind in ("pyro", "tele"):
            FLOW[uid] = {"library": kind, "stage": "account_type"}
            label = "Pyrogram" if kind == "pyro" else "Telegram"
            return await query.message.edit_text(
                f"Choose {label} account type:",
                reply_markup=account_menu(kind)
            )
        if kind not in ("pyro_user", "pyro_bot", "tele_user", "tele_bot"):
            return await query.answer("Invalid option.", show_alert=True)
        FLOW[uid] = {"kind": kind, "stage": "credential"}
        prompt = "Send a bot token for a bot you own from @BotFather." if kind.endswith("_bot") else "Send your phone number with country code, e.g. +919876543210."
        await query.message.edit_text(prompt + "\\n\\n/cancel to stop.")

    @app.on_message(filters.private & filters.command("cancel"))
    async def cancel(_, message):
        if not message.from_user:
            return
        uid = message.from_user.id
        state = FLOW.pop(uid, None)
        await close_worker(state)
        await message.reply_text("❎ Session generation cancelled.")

    @app.on_message(filters.private & filters.text & ~filters.command(["genstring", "cancel"]))
    async def input_step(client, message):
        if not message.from_user:
            return
        uid = message.from_user.id
        state = FLOW.get(uid)
        if not state:
            return
        value = (message.text or "").strip()
        try:
            await message.delete()
        except Exception:
            pass
        kind, stage = state["kind"], state["stage"]
        try:
            if stage == "credential" and kind == "pyro_bot":
                from pyrogram import Client
                worker = Client("string_pyro_bot", api_id=API_ID, api_hash=API_HASH,
                                bot_token=value, in_memory=True, no_updates=True)
                await worker.start()
                session = await worker.export_session_string()
                await worker.stop()
                FLOW.pop(uid, None)
                return await client.send_message(uid, "<b>Pyrogram bot session generated.</b>\n<code>" + session + "</code>", protect_content=True)

            if stage == "credential" and kind == "tele_bot":
                from telethon import TelegramClient
                from telethon.sessions import StringSession
                worker = TelegramClient(StringSession(), API_ID, API_HASH)
                await worker.start(bot_token=value)
                session = worker.session.save()
                await worker.disconnect()
                FLOW.pop(uid, None)
                return await client.send_message(uid, "<b>Telethon bot session generated.</b>\n<code>" + session + "</code>", protect_content=True)

            if stage == "credential":
                state["phone"] = value
                if kind == "pyro_user":
                    from pyrogram import Client
                    worker = Client("string_pyro_user", api_id=API_ID, api_hash=API_HASH, in_memory=True, no_updates=True)
                    await worker.connect()
                    sent = await worker.send_code(value)
                    state.update(worker=worker, phone_hash=sent.phone_code_hash, stage="code")
                else:
                    from telethon import TelegramClient
                    from telethon.sessions import StringSession
                    worker = TelegramClient(StringSession(), API_ID, API_HASH)
                    await worker.connect()
                    sent = await worker.send_code_request(value)
                    state.update(worker=worker, phone_hash=sent.phone_code_hash, stage="code")
                return await client.send_message(uid, "📩 Telegram OTP send karo. Spaces ke bina.")

            if stage == "code":
                worker = state["worker"]
                if kind == "pyro_user":
                    try:
                        await worker.sign_in(state["phone"], state["phone_hash"], value.replace(" ", ""))
                    except SessionPasswordNeeded:
                        state["stage"] = "password"
                        return await client.send_message(uid, "🔒 2-Step Verification password bhejo.")
                    session = await worker.export_session_string()
                else:
                    from telethon.errors import SessionPasswordNeededError
                    try:
                        await worker.sign_in(state["phone"], value.replace(" ", ""), phone_code_hash=state["phone_hash"])
                    except SessionPasswordNeededError:
                        state["stage"] = "password"
                        return await client.send_message(uid, "🔒 2-Step Verification password bhejo.")
                    session = worker.session.save()
                await worker.disconnect()
                FLOW.pop(uid, None)
                return await client.send_message(uid, "<b>Session generated. Keep it secret:</b>\n<code>" + session + "</code>", protect_content=True)

            if stage == "password":
                worker = state["worker"]
                if kind == "pyro_user":
                    await worker.check_password(value)
                    session = await worker.export_session_string()
                else:
                    await worker.sign_in(password=value)
                    session = worker.session.save()
                await worker.disconnect()
                FLOW.pop(uid, None)
                return await client.send_message(uid, "<b>Session generated. Keep it secret:</b>\n<code>" + session + "</code>", protect_content=True)
        except Exception as exc:
            LOG.warning("String session generation failed (%s)", type(exc).__name__)
            await close_worker(state)
            FLOW.pop(uid, None)
            await client.send_message(uid, "❌ Login/session generation failed. Credentials, OTP, 2FA or API settings check karke /genstring retry karo. Secret values logs mein nahi likhe gaye.")
