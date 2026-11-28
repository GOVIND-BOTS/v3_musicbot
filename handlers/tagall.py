import asyncio
import html
import logging

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import FloodWait

LOGGER = logging.getLogger(__name__)

SPAM_CHATS = {}
TAG_BATCH_SIZE = 5
TAG_DELAY_SECONDS = 7


def _is_group(message):
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


async def _is_admin(client, chat_id, user_id):
    if not user_id:
        return False
    try:
        member = await client.get_chat_member(chat_id, user_id)
        return member.status in (
            ChatMemberStatus.OWNER,
            ChatMemberStatus.ADMINISTRATOR,
        )
    except Exception:
        LOGGER.exception("Tag command admin check failed in %s", chat_id)
        return False


def register_tagall_handlers(app):
    async def run_tagging(client, message, custom_text):
        chat_id = message.chat.id
        stop_event = asyncio.Event()
        SPAM_CHATS[chat_id] = stop_event
        sent_count = 0
        batch = []

        try:
            async for member in client.get_chat_members(chat_id):
                if stop_event.is_set():
                    break

                user = member.user
                if not user or user.is_bot or user.is_deleted:
                    continue

                name = html.escape(user.first_name or "User")
                batch.append(f'<a href="tg://user?id={user.id}">{name}</a>')

                if len(batch) >= TAG_BATCH_SIZE:
                    if stop_event.is_set():
                        break
                    body = "\n".join(batch)
                    prefix = f"{html.escape(custom_text)}\n\n" if custom_text else ""
                    await client.send_message(
                        chat_id,
                        f"{prefix}{body}",
                        parse_mode="html",
                        disable_web_page_preview=True,
                    )
                    sent_count += len(batch)
                    batch.clear()
                    await asyncio.sleep(TAG_DELAY_SECONDS)

            if batch and not stop_event.is_set():
                prefix = f"{html.escape(custom_text)}\n\n" if custom_text else ""
                body = "\n".join(batch)
                await client.send_message(
                    chat_id,
                    f"{prefix}{body}",
                    parse_mode="html",
                    disable_web_page_preview=True,
                )
                sent_count += len(batch)

            if stop_event.is_set():
                await message.reply_text(
                    f"Tagging stopped. Total tagged: {sent_count}"
                )
            else:
                await message.reply_text(
                    f"Tagging completed. Total tagged: {sent_count}"
                )

        except FloodWait as exc:
            LOGGER.warning(
                "Tagging hit FloodWait in %s: %s seconds",
                chat_id,
                exc.value,
            )
            await message.reply_text(
                f"Telegram rate limit reached. Tagging stopped; "
                f"please try again after {exc.value} seconds."
            )
        except Exception:
            LOGGER.exception("Tagging failed in chat %s", chat_id)
            try:
                await message.reply_text(
                    "Tagging could not be completed. Please check that "
                    "the bot can view group members and send messages."
                )
            except Exception:
                pass
        finally:
            if SPAM_CHATS.get(chat_id) is stop_event:
                SPAM_CHATS.pop(chat_id, None)

    @app.on_message(
        filters.command(
            ["utag", "uall", "tagall", "all", "tagmember"],
            prefixes=["/", "@", "."],
        )
        & filters.group
    )
    async def tag_all_users(client, message):
        chat_id = message.chat.id

        if not _is_group(message):
            return await message.reply_text(
                "This command works in groups only."
            )

        if not message.from_user or not await _is_admin(
            client, chat_id, message.from_user.id
        ):
            return await message.reply_text(
                "Only group admins can use this command."
            )

        if chat_id in SPAM_CHATS:
            return await message.reply_text(
                "A tagging process is already active in this group. "
                "Use /stoputag to stop it."
            )

        parts = (message.text or "").split(maxsplit=1)
        custom_text = parts[1].strip() if len(parts) > 1 else ""

        command = message.command[0].lower() if message.command else ""
        if command in ("utag", "uall") and not custom_text:
            return await message.reply_text(
                "Please add a message to tag with. "
                "Example: /utag Hi everyone!"
            )

        await message.reply_text(
            "Tagging started. Members will be mentioned in batches of 5 "
            "with a 7-second pause. Use /stoputag to stop."
        )
        await run_tagging(client, message, custom_text)

    @app.on_message(
        filters.command(
            [
                "stoputag",
                "stopuall",
                "offutag",
                "offuall",
                "utagoff",
                "ualloff",
                "cancel",
            ],
            prefixes=["/", "@", "."],
        )
        & filters.group
    )
    async def stop_tagging(client, message):
        chat_id = message.chat.id
        if not message.from_user or not await _is_admin(
            client, chat_id, message.from_user.id
        ):
            return await message.reply_text(
                "Only group admins can stop tagging."
            )

        stop_event = SPAM_CHATS.get(chat_id)
        if not stop_event:
            return await message.reply_text(
                "No tagging process is active."
            )

        stop_event.set()
        await message.reply_text(
            "Please wait, stopping the tagging process..."
        )
