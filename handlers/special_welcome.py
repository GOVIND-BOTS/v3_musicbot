
import logging
from html import escape

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus

from config import (
    OWNER_ID,
    WELCOME_IMAGE,
    OWNER_WELCOME_IMAGE,
    START_IMAGE,
)

LOGGER = logging.getLogger(__name__)


def is_new_member(member):
    """Check whether a user has newly joined the group."""
    old_member = member.old_chat_member
    new_member = member.new_chat_member

    if not new_member or not new_member.user:
        return False

    if new_member.user.is_bot:
        return False

    old_status = old_member.status if old_member else None
    new_status = new_member.status

    active_statuses = {
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    }

    # Restricted users can also be present in a group.
    if new_status == ChatMemberStatus.RESTRICTED:
        if new_member.is_member:
            return old_status not in active_statuses and (
                old_status != ChatMemberStatus.RESTRICTED
                or not old_member.is_member
            )

    if new_status not in active_statuses:
        return False

    return old_status not in active_statuses and (
        old_status != ChatMemberStatus.RESTRICTED
        or not old_member.is_member
    )


def get_welcome_text(user, chat, is_owner=False):
    name = escape(user.first_name or "User")
    mention = f'<a href="tg://user?id={user.id}">{name}</a>'
    group = escape(chat.title or "this group")

    if is_owner:
        return (
            "👑 <b>OWNER HAS ARRIVED!</b>\n\n"
            f"Welcome our Owner {mention}!\n"
            f"✨ The creator has joined <b>{group}</b>.\n\n"
            "❤️ <b>Special Owner Welcome!</b>"
        )

    return (
        "🎉 <b>NEW MEMBER JOINED!</b>\n\n"
        f"Welcome {mention} to <b>{group}</b>!\n\n"
        "💖 Enjoy your stay and have fun with everyone!"
    )


def get_image_url(is_owner):
    if is_owner:
        return OWNER_WELCOME_IMAGE or WELCOME_IMAGE or START_IMAGE

    return WELCOME_IMAGE or START_IMAGE


def register_welcome_handlers(app):

    @app.on_chat_member_updated(filters.group)
    async def welcome_new_member(client, member):
        try:
            if not is_new_member(member):
                return

            user = member.new_chat_member.user
            chat = member.chat
            is_owner = user.id == OWNER_ID

            text = get_welcome_text(user, chat, is_owner)
            image_url = get_image_url(is_owner)

            if image_url:
                try:
                    await client.send_photo(
                        chat_id=chat.id,
                        photo=image_url,
                        caption=text,
                    )
                    LOGGER.info(
                        "Welcome image sent for user %s in chat %s",
                        user.id,
                        chat.id,
                    )
                    return

                except Exception as image_error:
                    LOGGER.warning(
                        "Welcome image failed, sending text instead: %s",
                        image_error,
                    )

            await client.send_message(
                chat_id=chat.id,
                text=text,
            )

            LOGGER.info(
                "Welcome message sent for user %s in chat %s",
                user.id,
                chat.id,
            )

        except Exception:
            LOGGER.exception("Welcome handler error")
