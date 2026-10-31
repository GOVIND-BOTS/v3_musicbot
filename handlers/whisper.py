from pyrogram import filters
from pyrogram.types import (
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pyrogram.errors import PeerIdInvalid, UserIsBlocked, UserDeactivated

whisper_db = {}


def register_whisper_handlers(app):
    bot_username = None

    async def get_bot_username():
        nonlocal bot_username
        if bot_username is None:
            me = await app.get_me()
            bot_username = me.username
        return bot_username

    @app.on_inline_query()
    async def whisper_inline(client, inline_query):
        data = inline_query.query.strip()
        username = await get_bot_username()

        switch_btn = InlineKeyboardMarkup(
            [[InlineKeyboardButton("💬 Start Whisper", switch_inline_query_current_chat="")]]
        )

        # Empty query → help
        if not data:
            results = [
                InlineQueryResultArticle(
                    title="💬 Whisper",
                    description=f"@{username} username/id your message",
                    input_message_content=InputTextMessageContent(
                        f"**Usage:**\n\n`@{username} username your message`\n\n"
                        f"**Example:**\n`@{username} @username Hello secret`"
                    ),
                    reply_markup=switch_btn,
                )
            ]
            return await inline_query.answer(results, cache_time=1)

        parts = data.split(None, 1)
        if len(parts) < 2:
            results = [
                InlineQueryResultArticle(
                    title="⚠️ Incomplete",
                    description="Username + message dono chahiye",
                    input_message_content=InputTextMessageContent(
                        f"**Usage:**\n`@{username} username your message`"
                    ),
                    reply_markup=switch_btn,
                )
            ]
            return await inline_query.answer(results, cache_time=1)

        target, msg = parts[0], parts[1]

        try:
            user = await client.get_users(target)
        except (PeerIdInvalid, IndexError, KeyError, ValueError):
            results = [
                InlineQueryResultArticle(
                    title="❌ User not found",
                    description="Invalid username or ID",
                    input_message_content=InputTextMessageContent(
                        "❌ Invalid username or user ID."
                    ),
                    reply_markup=switch_btn,
                )
            ]
            return await inline_query.answer(results, cache_time=1)

        key = f"{inline_query.from_user.id}_{user.id}"
        whisper_db[key] = msg

        whisper_btn = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔒 Open Whisper",
                        callback_data=f"whisper_{inline_query.from_user.id}_{user.id}",
                    )
                ]
            ]
        )

        one_time_btn = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔥 One-Time Whisper",
                        callback_data=f"whisper_{inline_query.from_user.id}_{user.id}_one",
                    )
                ]
            ]
        )

        results = [
            InlineQueryResultArticle(
                title=f"💬 Whisper to {user.first_name}",
                description="Normal whisper (multiple reads allowed)",
                input_message_content=InputTextMessageContent(
                    f"🔒 **Whisper** for {user.mention}\n\n"
                    f"Only they can open this message."
                ),
                reply_markup=whisper_btn,
            ),
            InlineQueryResultArticle(
                title=f"🔥 One-Time Whisper to {user.first_name}",
                description="Message disappears after reading once",
                input_message_content=InputTextMessageContent(
                    f"🔥 **One-Time Whisper** for {user.mention}\n\n"
                    f"Only they can open this. Message will be deleted after reading."
                ),
                reply_markup=one_time_btn,
            ),
        ]

        await inline_query.answer(results, cache_time=1)

    @app.on_callback_query(filters.regex(r"^whisper_(\d+)_(\d+)(_one)?$"))
    async def whisper_callback(client, query: CallbackQuery):
        data = query.data.split("_")
        from_user_id = int(data[1])
        to_user_id = int(data[2])
        one_time = len(data) > 3 and data[3] == "one"
        user_id = query.from_user.id

        # Sirf sender, receiver (aur optionally owner) open kar sakte hain
        if user_id not in (from_user_id, to_user_id):
            return await query.answer(
                "❌ Ye whisper aapke liye nahi hai!",
                show_alert=True,
            )

        key = f"{from_user_id}_{to_user_id}"
        msg = whisper_db.get(key)

        if not msg:
            return await query.answer(
                "⚠️ Whisper delete ho chuka hai ya expire ho gaya.",
                show_alert=True,
            )

        await query.answer(msg, show_alert=True)

        # One-time → message hata do
        if one_time and user_id == to_user_id:
            whisper_db.pop(key, None)
            try:
                await query.edit_message_text(
                    "🔥 **One-Time Whisper** read ho chuka hai."
                )
            except Exception:
                pass
