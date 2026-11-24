
import logging
from io import BytesIO

from pyrogram import filters
from pyrogram.enums import ChatType
from pyrogram.errors import SessionPasswordNeeded
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import API_ID, API_HASH

LOG = logging.getLogger(__name__)
FLOW = {}


def menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Pyrogram", callback_data="gensess|pyro"),
            InlineKeyboardButton("Telegram", callback_data="gensess|tele"),
        ],
        [InlineKeyboardButton("Cancel", callback_data="gensess|cancel")],
    ])


def account_menu(kind):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "User Account",
                callback_data=f"gensess|{kind}_user"
            ),
            InlineKeyboardButton(
                "Bot Account",
                callback_data=f"gensess|{kind}_bot"
            ),
        ],
        [InlineKeyboardButton("Cancel", callback_data="gensess|cancel")],
    ])


def session_file(session, filename):
    """Create an in-memory TXT file without exposing the session in chat."""
    file = BytesIO(session.encode("utf-8"))
    file.name = filename
    file.seek(0)
    return file


async def close_worker(state):
    if not state:
        return

    worker = state.get("worker")
    if not worker:
        return

    try:
        if state.get("started"):
            await worker.stop()
        else:
            await worker.disconnect()
    except Exception:
        try:
            await worker.disconnect()
        except Exception:
            pass


async def send_user_session_to_saved_messages(kind, worker, session):
    """Send the generated user session to that account's own Saved Messages."""

    if kind == "pyro_user":
        filename = "pyrogram_user_session.txt"
        caption = (
            "🔐 <b>Pyrogram User Session Generated</b>\n\n"
            "This is your personal session file. Keep it private and secure."
        )
        await worker.send_document(
            chat_id="me",
            document=session_file(session, filename),
            caption=caption,
        )

    elif kind == "tele_user":
        filename = "telethon_user_session.txt"
        caption = (
            "🔐 <b>Telethon User Session Generated</b>\n\n"
            "This is your personal session file. Keep it private and secure."
        )
        await worker.send_file(
            entity="me",
            file=session_file(session, filename),
            caption=caption,
            force_document=True,
        )


async def send_bot_session_to_requester(client, uid, kind, session):
    """Bot accounts have no personal Saved Messages, so send the file to requester."""

    if kind == "pyro_bot":
        filename = "pyrogram_bot_session.txt"
        caption = (
            "🔐 <b>Pyrogram Bot Session Generated</b>\n\n"
            "Keep this file private. Anyone with this session may control your bot."
        )
    else:
        filename = "telethon_bot_session.txt"
        caption = (
            "🔐 <b>Telethon Bot Session Generated</b>\n\n"
            "Keep this file private. Anyone with this session may control your bot."
        )

    await client.send_document(
        chat_id=uid,
        document=session_file(session, filename),
        caption=caption,
        protect_content=True,
    )


def register_string_session_handlers(app):

    @app.on_message(filters.command("genstring") & filters.private)
    async def genstring(_, message):
        if not message.from_user:
            return

        uid = message.from_user.id

        if uid in FLOW:
            old_state = FLOW.pop(uid, None)
            await close_worker(old_state)

        await message.reply_text(
            "🔐 <b>String Session Generator</b>\n\n"
            "Choose your session type below.\n\n"
            "Generate sessions only for accounts or bots you own. "
            "Your login code and password are private credentials.",
            reply_markup=menu(),
        )

    @app.on_callback_query(filters.regex(r"^gensess\|"))
    async def choose(_, query):
        if (
            not query.message
            or query.message.chat.type != ChatType.PRIVATE
        ):
            return await query.answer(
                "Please open /genstring in your private chat.",
                show_alert=True,
            )

        uid = query.from_user.id
        kind = query.data.split("|", 1)[1]

        await query.answer()

        if kind == "cancel":
            state = FLOW.pop(uid, None)
            await close_worker(state)
            return await query.message.edit_text("❎ Session generation cancelled.")

        if kind in ("pyro", "tele"):
            FLOW[uid] = {
                "library": kind,
                "stage": "account_type",
            }

            label = "Pyrogram" if kind == "pyro" else "Telegram"

            return await query.message.edit_text(
                f"Choose your {label} account type:",
                reply_markup=account_menu(kind),
            )

        if kind not in (
            "pyro_user",
            "pyro_bot",
            "tele_user",
            "tele_bot",
        ):
            return await query.answer(
                "Invalid option.",
                show_alert=True,
            )

        FLOW[uid] = {
            "kind": kind,
            "stage": "credential",
        }

        if kind.endswith("_bot"):
            prompt = (
                "Send the bot token obtained from @BotFather "
                "for a bot you own."
            )
        else:
            prompt = (
                "Send your phone number with country code.\n"
                "Example: +919876543210"
            )

        await query.message.edit_text(
            prompt + "\n\n/cancel to stop."
        )

    @app.on_message(filters.private & filters.command("cancel"))
    async def cancel(_, message):
        if not message.from_user:
            return

        uid = message.from_user.id
        state = FLOW.pop(uid, None)

        await close_worker(state)

        await message.reply_text(
            "❎ Session generation cancelled."
        )

    @app.on_message(
        filters.private
        & filters.text
        & ~filters.command(["genstring", "cancel"])
    )
    async def input_step(client, message):
        if not message.from_user:
            return

        uid = message.from_user.id
        state = FLOW.get(uid)

        if not state:
            return

        value = (message.text or "").strip()

        # Delete sensitive input messages where possible.
        try:
            await message.delete()
        except Exception:
            pass

        kind = state["kind"]
        stage = state["stage"]

        try:

            # -----------------------------------------
            # PYROGRAM BOT ACCOUNT
            # -----------------------------------------
            if stage == "credential" and kind == "pyro_bot":
                from pyrogram import Client

                worker = Client(
                    "string_pyro_bot",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    bot_token=value,
                    in_memory=True,
                    no_updates=True,
                )

                await worker.start()

                state["worker"] = worker
                state["started"] = True

                session = await worker.export_session_string()

                await send_bot_session_to_requester(
                    client,
                    uid,
                    kind,
                    session,
                )

                await close_worker(state)
                FLOW.pop(uid, None)

                return await client.send_message(
                    uid,
                    "✅ <b>Pyrogram bot session file sent successfully.</b>",
                )

            # -----------------------------------------
            # TELETHON BOT ACCOUNT
            # -----------------------------------------
            if stage == "credential" and kind == "tele_bot":
                from telethon import TelegramClient
                from telethon.sessions import StringSession

                worker = TelegramClient(
                    StringSession(),
                    API_ID,
                    API_HASH,
                )

                await worker.start(bot_token=value)

                state["worker"] = worker
                state["started"] = True

                session = worker.session.save()

                await send_bot_session_to_requester(
                    client,
                    uid,
                    kind,
                    session,
                )

                await close_worker(state)
                FLOW.pop(uid, None)

                return await client.send_message(
                    uid,
                    "✅ <b>Telethon bot session file sent successfully.</b>",
                )

            # -----------------------------------------
            # USER ACCOUNT: SEND LOGIN CODE
            # -----------------------------------------
            if stage == "credential":

                state["phone"] = value

                if kind == "pyro_user":
                    from pyrogram import Client

                    worker = Client(
                        "string_pyro_user",
                        api_id=API_ID,
                        api_hash=API_HASH,
                        in_memory=True,
                        no_updates=True,
                    )

                    await worker.connect()

                    sent = await worker.send_code(value)

                    state.update({
                        "worker": worker,
                        "phone_hash": sent.phone_code_hash,
                        "stage": "code",
                    })

                elif kind == "tele_user":
                    from telethon import TelegramClient
                    from telethon.sessions import StringSession

                    worker = TelegramClient(
                        StringSession(),
                        API_ID,
                        API_HASH,
                    )

                    await worker.connect()

                    sent = await worker.send_code_request(value)

                    state.update({
                        "worker": worker,
                        "phone_hash": sent.phone_code_hash,
                        "stage": "code",
                    })

                return await client.send_message(
                    uid,
                    "📩 Enter the Telegram login code you received.\n"
                    "Do not include spaces.",
                )

            # -----------------------------------------
            # USER ACCOUNT: VERIFY LOGIN CODE
            # -----------------------------------------
            if stage == "code":

                worker = state["worker"]

                if kind == "pyro_user":
                    try:
                        await worker.sign_in(
                            state["phone"],
                            state["phone_hash"],
                            value.replace(" ", ""),
                        )

                    except SessionPasswordNeeded:
                        state["stage"] = "password"

                        return await client.send_message(
                            uid,
                            "🔒 Enter your Two-Step Verification password.",
                        )

                    session = await worker.export_session_string()

                else:
                    from telethon.errors import SessionPasswordNeededError

                    try:
                        await worker.sign_in(
                            state["phone"],
                            value.replace(" ", ""),
                            phone_code_hash=state["phone_hash"],
                        )

                    except SessionPasswordNeededError:
                        state["stage"] = "password"

                        return await client.send_message(
                            uid,
                            "🔒 Enter your Two-Step Verification password.",
                        )

                    session = worker.session.save()

                # Important: Send before disconnecting the user account.
                await send_user_session_to_saved_messages(
                    kind,
                    worker,
                    session,
                )

                await close_worker(state)
                FLOW.pop(uid, None)

                return await client.send_message(
                    uid,
                    "✅ <b>Session generated successfully!</b>\n\n"
                    "Your session file has been sent to your Telegram "
                    "<b>Saved Messages</b>.",
                )

            # -----------------------------------------
            # USER ACCOUNT: TWO-STEP VERIFICATION
            # -----------------------------------------
            if stage == "password":

                worker = state["worker"]

                if kind == "pyro_user":
                    await worker.check_password(value)
                    session = await worker.export_session_string()

                else:
                    await worker.sign_in(password=value)
                    session = worker.session.save()

                # Keep the authenticated user client connected until
                # its session file reaches its own Saved Messages.
                await send_user_session_to_saved_messages(
                    kind,
                    worker,
                    session,
                )

                await close_worker(state)
                FLOW.pop(uid, None)

                return await client.send_message(
                    uid,
                    "✅ <b>Session generated successfully!</b>\n\n"
                    "Your session file has been sent to your Telegram "
                    "<b>Saved Messages</b>.",
                )

        except Exception as exc:
            LOG.warning(
                "String session generation failed (%s)",
                type(exc).__name__,
            )

            await close_worker(state)
            FLOW.pop(uid, None)

            await client.send_message(
                uid,
                "❌ <b>Session generation failed.</b>\n\n"
                "Check your credentials, login code, "
                "Two-Step Verification password, and API settings. "
                "Then try /genstring again.\n\n"
                "Secret values are not written to the logs.",
            )
