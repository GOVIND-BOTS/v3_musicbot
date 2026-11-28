import asyncio
import logging
import os
import random
import shutil
import uuid
from contextlib import suppress
from pathlib import Path

import aiohttp

from pyrogram import filters
from pyrogram.enums import ChatMemberStatus, ChatType
from pyrogram.errors import RPCError


from config import OWNER_ID, SUDO_USERS

LOGGER = logging.getLogger(__name__)

_ACTIVE = {}
_AUDIO_DIR = Path(__file__).resolve().parent.parent / "Flame" / "Audio"
_CUSTOM_AUDIO_DIR = _AUDIO_DIR / "Custom"


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
    if message.chat and message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
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


async def _get_random_audio():
    """Pick a saved custom track or download one of the original assets."""
    _AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    _CUSTOM_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    custom_tracks = [
        path for path in _CUSTOM_AUDIO_DIR.glob("*.mp3")
        if path.is_file() and path.stat().st_size > 0
    ]
    choices = [("custom", path) for path in custom_tracks]
    choices.extend(("original", index) for index in range(1, 9))
    kind, selected = random.choice(choices)
    if kind == "custom":
        return str(selected)

    index = selected
    destination = _AUDIO_DIR / f"AUDIO{index}"
    if not destination.is_file() or destination.stat().st_size == 0:
        url = (
            "https://raw.githubusercontent.com/GOVIND-BOTS/"
            f"VC-RAID-MUSIC/Xmarty/Flame/Audio/AUDIO{index}"
        )
        temporary = destination.with_name(destination.name + ".part")
        timeout = aiohttp.ClientTimeout(total=90)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    with open(temporary, "wb") as output:
                        async for chunk in response.content.iter_chunked(64 * 1024):
                            output.write(chunk)
            if temporary.stat().st_size == 0:
                raise RuntimeError("Downloaded audio file is empty")
            os.replace(temporary, destination)
        except Exception:
            _remove_file(str(temporary))
            raise
    return str(destination)


def register_vc_raid_handlers(app, stream, assistant):
    async def authorize(client, message):
        if not message.from_user or not _privileged(message.from_user.id):
            await message.reply_text("⛔ Only the bot OWNER or SUDO users can use VC raid controls.")
            return False
        return True

    async def resolve_target(client, message, args):
        chat = await _target_chat(client, message, args)
        if not chat or chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            await message.reply_text("❌ Target group not found. Run the command inside a group or provide a group ID/username.")
            return None
        if not await _bot_is_admin(client, chat.id):
            await message.reply_text("❌ The bot is not an admin in the target group. Promote the bot to admin first.")
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
            await message.reply_text("⚠️ A stream is already active in this group's voice chat. Use /raidend first.")
            return

        local_path = None
        try:
            if use_random:
                try:
                    local_path = await _get_random_audio()
                except Exception as exc:
                    LOGGER.exception("Could not download VC raid audio")
                    await message.reply_text(f"❌ Failed to download VC raid audio: {str(exc)[:180]}")
                    return
                media_type = "audio"
            else:
                replied = message.reply_to_message
                if not replied or not (replied.audio or replied.voice or replied.video or replied.document or replied.video_note or replied.animation):
                    await message.reply_text("❌ Reply to an audio/video/file message and use /vraid [group_id].")
                    return
                local_path = await assistant.download_media(replied)
                if not local_path:
                    await message.reply_text("❌ Failed to download the media.")
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
            if local_path and Path(local_path).parent != _CUSTOM_AUDIO_DIR:
                _remove_file(local_path)
            await message.reply_text(f"❌ VC stream start failed: {str(exc)[:250]}")

    @app.on_message(filters.command("vcadd") & (filters.group | filters.private))
    async def vcadd(client, message):
        if not await authorize(client, message):
            return

        replied = message.reply_to_message
        if not replied or not (
            replied.video
            or replied.video_note
            or (replied.document and (replied.document.mime_type or "").startswith("video/"))
        ):
            await message.reply_text(
                "❌ Reply to a video, video note, or video file with /vcadd to add its audio to the VC raid playlist."
            )
            return

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            await message.reply_text("❌ FFmpeg is not installed on the server. Install FFmpeg and try again.")
            return

        source_path = None
        output_path = None
        status = await message.reply_text("⏳ Downloading the video and converting it to audio...")
        try:
            source_path = await assistant.download_media(replied)
            if not source_path or not os.path.isfile(source_path):
                raise RuntimeError("Video download failed")

            _CUSTOM_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
            output_path = str(_CUSTOM_AUDIO_DIR / f"custom_{uuid.uuid4().hex}.mp3")
            process = await asyncio.create_subprocess_exec(
                ffmpeg, "-y", "-i", source_path,
                "-vn", "-codec:a", "libmp3lame", "-b:a", "192k",
                output_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise RuntimeError("Audio conversion timed out (10 minutes)")
            if process.returncode != 0 or not os.path.isfile(output_path) or os.path.getsize(output_path) == 0:
                detail = (stderr or b"").decode("utf-8", "ignore")[-300:]
                raise RuntimeError(detail or "FFmpeg could not extract audio from this video")

            total = len([
                path for path in _CUSTOM_AUDIO_DIR.glob("*.mp3")
                if path.is_file() and path.stat().st_size > 0
            ])
            await status.edit_text(
                f"✅ Video converted and added to the VC raid playlist!\n"
                f"🎵 Saved tracks: {total}\n"
                "Use /vcraid to play a random track from the playlist."
            )
        except Exception as exc:
            LOGGER.exception("Could not add video audio to VC raid playlist")
            _remove_file(output_path)
            await status.edit_text(f"❌ Could not add this video: {str(exc)[:250]}")
        finally:
            _remove_file(source_path)

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
            await message.reply_text("ℹ️ No active raid stream from this bot in this group's voice chat.")
            return
        try:
            await stream.start()
            if action == "end":
                await stream.calls.leave_call(target.id)
                _ACTIVE.pop(target.id, None)
                active_path = active.get("path")
                if active_path and Path(active_path).parent != _CUSTOM_AUDIO_DIR:
                    _remove_file(active_path)
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
