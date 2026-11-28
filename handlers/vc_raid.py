import logging
import os
import random
import tempfile
from contextlib import suppress
from pathlib import Path

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import RPCError
from pytgcalls.types import AudioQuality, VideoQuality, MediaStream

from config import OWNER_ID, SUDO_USERS

LOGGER = logging.getLogger(__name__)

# One active raid stream per target chat. Files are kept until /raidend.
_ACTIVE = {}
_AUDIO_DIR = Path(__file__).resolve().parent.parent / "Flame" / "Audio"


def _privileged(user_id):
    try:
        allowed = {int(OWNER_ID)}
        allowed.update(int(item) for item in SUDO_USERS)
        return int(user_id) in allowed
    except (TypeError, ValueError):
        return False


async def _target_chat(client, message, args):
    if args:
        value = args[0]
        try:
            chat = await client.get_chat(int(value) if value.lstrip("-").isdigit() else value)
        except (RPCError, ValueError):
            return None
        return chat
    if message.chat and message.chat.type in ("group", "supergroup"):
        return message.chat
    return None


async def _bot_is_admin(client, chat_id):
    try:
        me = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
        return member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
    except Exception:
        return False


def _remove_file(path):
    if path:
        with suppress(OSError):
            os.remove(path)


def register_vc_raid_handlers(app, stream, assistant):
    async def authorize(client, message):
        if not message.from_user or not _privileged(message.from_user.id):
            await message.reply_text("⛔ Only the bot OWNER or SUDO users can use VC raid controls.")
            return False
        return True

    async def resolve_target(client, message, args):
        chat = await _target_chat(client, message, args)
        if not chat or chat.type not in ("group", "supergroup"):
            await message.reply_text("❌ Target group nahi mila. Group ke andar command chalao ya group ID/username do.")
            return None
        if not await _bot_is_admin(client, chat.id):
            await message.reply_text("❌ Bot target group mein admin nahi hai. Pehle bot ko admin banao.")
            return None
        return chat

    async def start_stream(client, message, use_random=False):
        if not await authorize(client, message):
            return
        parts = (message.text or "").split()
        args = parts[1:]
        target = await resolve_target(client, message, args)
        if not target:
            return

        if target.id in _ACTIVE:
            await message.reply_text("⚠️ Is group ke VC mein stream pehle se active hai. /raidend use karo.")
            return

        local_path = None
        try:
            if use_random:
                candidates = [
                    _AUDIO_DIR / f"AUDIO{i}.{ext}"
                    for i in range(1, 9)
                    for ext in ("mp3", "ogg", "m4a", "wav")
                    if (_AUDIO_DIR / f"AUDIO{i}.{ext}").is_file()
                ]
                if not candidates:
                    await message.reply_text("❌ Audio files nahi mile. Flame/Audio/ mein AUDIO1–AUDIO8 files add karo, ya media par reply karke /vraid use karo.")
                    return
                local_path = str(random.choice(candidates))
                media_type = "audio"
            else:
                replied = message.reply_to_message
                if not replied or not (replied.audio or replied.voice or replied.video or replied.document or replied.video_note or replied.animation):
                    await message.reply_text("❌ Kisi audio/video/file message par reply karke /vraid [group_id] likho.")
                    return
                local_path = await assistant.download_media(replied)
                if not local_path:
                    await message.reply_text("❌ Media download nahi ho paya.")
                    return
                media_type = "video" if (replied.video or replied.video_note or replied.animation) else "audio"

            track = {"url": local_path, "media_type": media_type}
            media = stream.make_media(track)
            await stream.start()
            await stream.calls.play(target.id, media)
            _ACTIVE[target.id] = {"path": local_path, "source_chat": message.chat.id}
            await message.reply_text(f"🔊 VC stream started in {target.title} ({target.id}). Use /raidpause, /raidresume or /raidend.")
        except Exception as exc:
            LOGGER.exception("VC stream start failed for %s", getattr(target, "id", None))
            _remove_file(local_path)
            await message.reply_text(f"❌ VC stream start failed: {str(exc)[:250]}")

    @app.on_message(filters.command("vcraid") & (filters.group | filters.private))
    async def vcraid(client, message):
        await start_stream(client, message, use_random=True)

    @app.on_message(filters.command("vraid") & (filters.group | filters.private))
    async def vraid(client, message):
        await start_stream(client, message, use_random=False)

    async def control(client, message, action):
        if not await authorize(client, message):
            return
        parts = (message.text or "").split()
        target = await resolve_target(client, message, parts[1:])
        if not target:
            return
        active = _ACTIVE.get(target.id)
        if not active:
            await message.reply_text("ℹ️ Is group ke VC mein bot ka raid stream active nahi hai.")
            return
        try:
            await stream.start()
            if action == "end":
                await stream.calls.leave_call(target.id)
                _ACTIVE.pop(target.id, None)
                _remove_file(active.get("path"))
                reply = "⏹️ VC stream ended."
            elif action == "pause":
                await stream.calls.pause(target.id)
                reply = "⏸️ VC stream paused."
            else:
                await stream.calls.resume(target.id)
                reply = "▶️ VC stream resumed."
            await message.reply_text(f"{reply} ({target.title})")
        except Exception as exc:
            LOGGER.exception("VC stream %s failed for %s", action, target.id)
            await message.reply_text(f"❌ {action.title()} failed: {str(exc)[:200]}")

    @app.on_message(filters.command("raidend") & (filters.group | filters.private))
    async def raidend(client, message):
        await control(client, message, "end")

    @app.on_message(filters.command("raidpause") & (filters.group | filters.private))
    async def raidpause(client, message):
        await control(client, message, "pause")

    @app.on_message(filters.command("raidresume") & (filters.group | filters.private))
    async def raidresume(client, message):
        await control(client, message, "resume")

    LOGGER.info("OWNER/SUDO VC raid handlers registered")
