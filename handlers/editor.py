import asyncio
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

from pyrogram import filters
from editor.engine import (
    MAX_SECONDS,
    create_timeline,
    edit_photo,
    edit_video,
    number,
    parse_options,
    photo_to_video,
)

LOGGER = logging.getLogger(__name__)
MAX_TIMELINE_CLIPS = 10
MAX_INPUT_BYTES = 100 * 1024 * 1024
MAX_SESSION_BYTES = 300 * 1024 * 1024
SESSION_TTL = 2 * 60 * 60
TIMELINE_SESSIONS = {}

HELP = (
    "🎬 **V3 CAPCUT-STYLE EDITOR**\n\n"
    "**Single photo:** reply with /edit.\n"
    "/edit brightness=1.2 contrast=1.1 saturation=1.3\n"
    "/edit filter=warm (bw / warm / cool / blur / sharpen)\n"
    "/edit crop=square (square / portrait)\n"
    "/edit rotate=90 mirror text=Govind\n\n"
    "**Single video (1–120 seconds):**\n"
    "/edit start=5 end=45 speed=1.5\n"
    "/edit quality=720p brightness=0.1 contrast=1.1\n"
    "/edit mute mirror rotate=90 text=V3_MUSIC\n\n"
    "**Multi-clip timeline (2–10 clips):**\n"
    "1. Send /timeline to start your editing session in this chat.\n"
    "2. Send photos/videos one by one in the order you want them.\n"
    "3. Optional: reply to an audio file with /timeline_music.\n"
    "4. Optional: /timeline_order 3,1,2 to reorder uploaded clips.\n"
    "5. Optional: /timeline_duration 1=5 2=3-12\n"
    "   A=seconds sets a photo duration or trims a video from its start; A=start-end trims a video range.\n"
    "6. Finish with /timeline_done music_volume=0.25 original_audio=keep quality=720p\n"
    "Use original_audio=mute to remove clip sound; background music still plays.\n"
    "Use /timeline_cancel to discard the session. Total output: 1–120 seconds.\n\n"
    "Reply to a photo with /photo2video 15 to make a 15-second video.\n"
    "Quality: 360p / 480p / 720p / 1080p. Use /edithelp for this guide."
)


def media_kind(message):
    if message.photo:
        return "photo"
    if message.video:
        return "video"
    if message.document:
        mime = (message.document.mime_type or "").lower()
        suffix = Path(message.document.file_name or "").suffix.lower()
        if mime.startswith("image/"):
            return "photo"
        if mime.startswith("video/") or suffix in {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}:
            return "video"
    return None


def audio_media(message):
    if message.audio:
        return message.audio
    if message.voice:
        return message.voice
    if message.document:
        mime = (message.document.mime_type or "").lower()
        suffix = Path(message.document.file_name or "").suffix.lower()
        if mime.startswith("audio/") or suffix in {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac", ".wma"}:
            return message.document
    return None


async def download_media(message, path):
    downloaded = await message.download(file_name=path)
    if not downloaded or not os.path.exists(downloaded):
        raise RuntimeError("Could not download the replied media.")
    return downloaded


def cleanup(folder):
    if folder and os.path.isdir(folder):
        shutil.rmtree(folder, ignore_errors=True)


def session_key(message):
    if not message.from_user:
        return None
    return (message.chat.id, message.from_user.id)


def prune_sessions():
    now = time.time()
    for old_key, old_session in list(TIMELINE_SESSIONS.items()):
        if not old_session.get("rendering") and now - old_session["last_activity"] > SESSION_TTL:
            TIMELINE_SESSIONS.pop(old_key, None)
            cleanup(old_session["folder"])


def get_session(message):
    prune_sessions()
    key = session_key(message)
    if key is None:
        return None, None
    session = TIMELINE_SESSIONS.get(key)
    if session and not session.get("rendering") and time.time() - session["last_activity"] > SESSION_TTL:
        TIMELINE_SESSIONS.pop(key, None)
        cleanup(session["folder"])
        return key, None
    return key, session


def file_suffix(message, kind):
    if message.document:
        suffix = Path(message.document.file_name or "").suffix.lower()
    elif message.video:
        suffix = Path(getattr(message.video, "file_name", "") or "").suffix.lower()
    else:
        suffix = ".jpg"
    allowed = {
        "photo": {".jpg", ".jpeg", ".png", ".webp"},
        "video": {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"},
    }
    return suffix if suffix in allowed[kind] else (".jpg" if kind == "photo" else ".mp4")


def parse_order(raw, count):
    values = [part.strip() for part in raw.replace(" ", ",").split(",") if part.strip()]
    try:
        order = [int(value) for value in values]
    except ValueError:
        raise ValueError("Use clip numbers separated by commas, for example /timeline_order 3,1,2.")
    expected = list(range(1, count + 1))
    if sorted(order) != expected:
        raise ValueError("Order must include every uploaded clip exactly once: " + ",".join(map(str, expected)) + ".")
    return order


def parse_duration_specs(raw, count):
    durations = {}
    trims = {}
    for token in raw.split():
        if "=" not in token:
            raise ValueError("Use /timeline_duration 1=5 2=3-12 (clip number=seconds or start-end).")
        key, value = token.split("=", 1)
        try:
            index = int(key)
        except ValueError:
            raise ValueError("Clip numbers in /timeline_duration must be integers.")
        if not 1 <= index <= count:
            raise ValueError("Clip " + str(index) + " does not exist. Current clip count: " + str(count) + ".")
        if "-" in value:
            parts = value.split("-", 1)
            if len(parts) != 2 or not all(parts):
                raise ValueError("Trim format must be start-end, for example 2=3-12.")
            try:
                start, end = float(parts[0]), float(parts[1])
            except ValueError:
                raise ValueError("Trim times must be numeric seconds.")
            if start < 0 or end <= start:
                raise ValueError("Trim end must be greater than its non-negative start.")
            trims[index] = (start, end)
        else:
            try:
                duration = float(value)
            except ValueError:
                raise ValueError("Clip durations must be numeric seconds.")
            if not .5 <= duration <= MAX_SECONDS:
                raise ValueError("Each clip duration must be between 0.5 and 120 seconds.")
            durations[index] = duration
    if not durations and not trims:
        raise ValueError("Add at least one duration, e.g. /timeline_duration 1=5.")
    if set(durations) & set(trims):
        raise ValueError("A clip cannot have both a duration and a start-end trim.")
    return durations, trims


def session_summary(session):
    clips = sorted(session["clips"], key=lambda item: item["message_id"])
    photos = sum(1 for clip in clips if clip["kind"] == "photo")
    videos = len(clips) - photos
    return "📁 **Timeline clips:** " + str(len(clips)) + "/" + str(MAX_TIMELINE_CLIPS) + "\n" + \
        "🖼 Photos: " + str(photos) + " | 🎞 Videos: " + str(videos) + "\n" + \
        "🎵 Background music: " + ("added" if session.get("music") else "not added")


def register_editor_handlers(app):
    # Explicitly enable editor commands in private chats and groups.
    editor_chats = filters.private | filters.group

    @app.on_message(editor_chats & filters.command(["edit", "photoedit", "videoedit"]))
    async def edit_command(client, message):
        if len(message.command) > 1 and message.command[1].lower() in {"help", "guide"}:
            return await message.reply_text(HELP, disable_web_page_preview=True)
        reply = message.reply_to_message
        if not reply:
            return await message.reply_text("Photo/video par reply karke /edit likho.\n\n" + HELP)
        kind = media_kind(reply)
        if not kind:
            return await message.reply_text("Please reply to a photo or video.")
        command = message.command[0].lower()
        if command == "photoedit" and kind != "photo":
            return await message.reply_text("/photoedit ke liye photo par reply karo.")
        if command == "videoedit" and kind != "video":
            return await message.reply_text("/videoedit ke liye video par reply karo.")
        opts = parse_options(" ".join(message.command[1:]))
        status = await message.reply_text("🎬 **V3 Editor: rendering started...**")
        folder = tempfile.mkdtemp(prefix="v3_editor_")
        source = os.path.join(folder, "source.jpg" if kind == "photo" else "source.mp4")
        output = os.path.join(folder, "edited.jpg" if kind == "photo" else "edited.mp4")
        try:
            source = await download_media(reply, source)
            if kind == "photo":
                await asyncio.to_thread(edit_photo, source, output, opts)
                await message.reply_photo(output, caption="✨ **Photo edit complete**\n🎨 V3 Music Editor")
            else:
                await edit_video(source, output, opts)
                await message.reply_video(output, caption="🎬 **Video edit complete**\n⏱ 1–120 seconds\n⚡ V3 Music Editor", supports_streaming=True)
            await status.delete()
        except ValueError as error:
            await status.edit_text("⚠️ " + str(error) + "\n\n" + HELP, disable_web_page_preview=True)
        except Exception as error:
            LOGGER.exception("V3 media editor failed")
            await status.edit_text("❌ **Editing failed.**\n" + str(error)[-700:] + "\n\nCheck Railway logs if this repeats.")
        finally:
            cleanup(folder)

    @app.on_message(editor_chats & filters.command("photo2video"))
    async def photo_to_video_command(client, message):
        reply = message.reply_to_message
        if not reply or media_kind(reply) != "photo":
            return await message.reply_text("Photo par reply karke /photo2video 15 likho (1–120 seconds).")
        seconds = message.command[1] if len(message.command) > 1 else "10"
        opts = parse_options(" ".join(message.command[2:]))
        status = await message.reply_text("🎞️ **Creating video from photo...**")
        folder = tempfile.mkdtemp(prefix="v3_photo_video_")
        source = os.path.join(folder, "source.jpg")
        output = os.path.join(folder, "photo_video.mp4")
        try:
            source = await download_media(reply, source)
            await photo_to_video(source, output, seconds, opts)
            await message.reply_video(output, caption="🎞️ **Photo video ready**\n⏱ Duration: " + str(seconds) + "s\n⚡ V3 Music Editor", supports_streaming=True)
            await status.delete()
        except Exception as error:
            LOGGER.exception("Photo-to-video render failed")
            await status.edit_text("❌ Could not create video: " + str(error)[-600:])
        finally:
            cleanup(folder)

    @app.on_message(editor_chats & filters.command("timeline"))
    async def timeline_start_command(client, message):
        prune_sessions()
        key = session_key(message)
        if key is None:
            return await message.reply_text("Start a timeline from a user account, not an anonymous channel post.")
        old = TIMELINE_SESSIONS.get(key)
        if old and old.get("rendering"):
            return await message.reply_text("Your current timeline is rendering. Wait for it to finish first.")
        if old:
            cleanup(old["folder"])
        opts = parse_options(" ".join(message.command[1:]))
        try:
            photo_duration = number(opts.get("photo_duration", 3), "photo_duration", 1, MAX_SECONDS)
        except ValueError as error:
            return await message.reply_text("⚠️ " + str(error))
        folder = tempfile.mkdtemp(prefix="v3_timeline_")
        TIMELINE_SESSIONS[key] = {
            "folder": folder,
            "clips": [],
            "music": None,
            "input_bytes": 0,
            "order": None,
            "durations": {},
            "trims": {},
            "photo_duration": photo_duration,
            "quality": opts.get("quality", "720p"),
            "original_audio": opts.get("original_audio", "keep").lower(),
            "created_at": time.time(),
            "last_activity": time.time(),
            "rendering": False,
            "lock": asyncio.Lock(),
        }
        if TIMELINE_SESSIONS[key]["original_audio"] not in {"keep", "mute"}:
            cleanup(folder)
            TIMELINE_SESSIONS.pop(key, None)
            return await message.reply_text("original_audio must be keep or mute.")
        await message.reply_text(
            "🎬 **Timeline session started!**\n\n"
            "Now send 2–10 photos/videos one by one in your desired order.\n"
            "Default photo duration: " + str(photo_duration) + "s.\n\n"
            "Optional commands:\n"
            "• Reply to an audio file with /timeline_music\n"
            "• /timeline_order 3,1,2\n"
            "• /timeline_duration 1=5 2=3-12\n"
            "• /timeline_done music_volume=0.25 original_audio=keep quality=720p\n"
            "• /timeline_cancel"
        )

    @app.on_message(editor_chats & filters.incoming & filters.media, group=10)
    async def collect_timeline_clip(client, message):
        key, session = get_session(message)
        if not session:
            return
        kind = media_kind(message)
        if not kind:
            return
        async with session["lock"]:
            if session["rendering"]:
                return
            if any(clip["message_id"] == message.id for clip in session["clips"]):
                return
            if len(session["clips"]) >= MAX_TIMELINE_CLIPS:
                return await message.reply_text("⚠️ Maximum 10 clips allowed. Use /timeline_done or /timeline_cancel.")
            media = message.photo or message.video or message.document
            file_size = getattr(media, "file_size", 0) or 0
            if file_size > MAX_INPUT_BYTES:
                return await message.reply_text("⚠️ Each timeline clip must be 100 MB or smaller.")
            if session["input_bytes"] + file_size > MAX_SESSION_BYTES:
                return await message.reply_text("⚠️ Total timeline uploads are limited to 300 MB per session.")
            position = len(session["clips"]) + 1
            target = os.path.join(session["folder"], "clip_" + str(message.id) + file_suffix(message, kind))
            status = await message.reply_text("⬇️ Downloading timeline clip " + str(position) + "...")
            try:
                path = await download_media(message, target)
                actual_size = os.path.getsize(path)
                if actual_size > MAX_INPUT_BYTES:
                    os.remove(path)
                    raise ValueError("Each timeline clip must be 100 MB or smaller.")
                if session["input_bytes"] + actual_size > MAX_SESSION_BYTES:
                    os.remove(path)
                    raise ValueError("Total timeline uploads are limited to 300 MB per session.")
                session["clips"].append({
                    "message_id": message.id,
                    "kind": kind,
                    "path": path,
                    "size": actual_size,
                })
                session["input_bytes"] += actual_size
                session["last_activity"] = time.time()
                ordered_clips = sorted(session["clips"], key=lambda item: item["message_id"])
                position = next(i for i, item in enumerate(ordered_clips, 1) if item["message_id"] == message.id)
                await status.edit_text("✅ Added " + kind + " clip #" + str(position) + ".\n" + session_summary(session))
            except Exception as error:
                if os.path.exists(target):
                    try:
                        os.remove(target)
                    except OSError:
                        pass
                LOGGER.exception("Timeline clip download failed")
                await status.edit_text("❌ Could not add this clip: " + str(error)[-400:])

    @app.on_message(editor_chats & filters.command("timeline_music"))
    async def timeline_music_command(client, message):
        key, session = get_session(message)
        if not session:
            return await message.reply_text("Start first with /timeline, then reply to an audio file with /timeline_music.")
        reply = message.reply_to_message
        if not reply or not audio_media(reply):
            return await message.reply_text("Reply to an MP3/M4A/OGG/WAV/audio file with /timeline_music.")
        media = audio_media(reply)
        music_size = getattr(media, "file_size", 0) or 0
        if music_size > MAX_INPUT_BYTES:
            return await message.reply_text("Background music must be 100 MB or smaller.")
        async with session["lock"]:
            if session["rendering"]:
                return await message.reply_text("Your timeline is already rendering.")
            suffix = Path(getattr(media, "file_name", "") or "").suffix.lower()
            if suffix not in {".mp3", ".m4a", ".aac", ".wav", ".ogg", ".opus", ".flac", ".wma"}:
                suffix = ".audio"
            target = os.path.join(session["folder"], "background_music_" + str(reply.id) + suffix)
            status = await message.reply_text("🎵 Downloading background music...")
            try:
                path = await download_media(reply, target)
                old_music = session.get("music")
                old_size = os.path.getsize(old_music) if old_music and os.path.exists(old_music) else 0
                new_size = os.path.getsize(path)
                if new_size > MAX_INPUT_BYTES:
                    os.remove(path)
                    raise ValueError("Background music must be 100 MB or smaller.")
                if session["input_bytes"] - old_size + new_size > MAX_SESSION_BYTES:
                    os.remove(path)
                    raise ValueError("Total timeline uploads are limited to 300 MB per session.")
                session["music"] = path
                session["input_bytes"] = session["input_bytes"] - old_size + new_size
                if old_music and old_music != path and os.path.exists(old_music):
                    os.remove(old_music)
                session["last_activity"] = time.time()
                await status.edit_text("✅ Background music added. Volume can be set in /timeline_done music_volume=0.25.")
            except Exception as error:
                if os.path.exists(target):
                    try:
                        os.remove(target)
                    except OSError:
                        pass
                LOGGER.exception("Timeline music download failed")
                await status.edit_text("❌ Could not add music: " + str(error)[-400:])

    @app.on_message(editor_chats & filters.command("timeline_order"))
    async def timeline_order_command(client, message):
        key, session = get_session(message)
        if not session:
            return await message.reply_text("Start a session with /timeline first.")
        if len(message.command) < 2:
            return await message.reply_text("Usage: /timeline_order 3,1,2 — numbers refer to upload order.")
        async with session["lock"]:
            if session["rendering"]:
                return await message.reply_text("Your timeline is already rendering.")
            count = len(session["clips"])
            try:
                session["order"] = parse_order(" ".join(message.command[1:]), count)
                session["last_activity"] = time.time()
            except ValueError as error:
                return await message.reply_text("⚠️ " + str(error))
        await message.reply_text("🔀 Timeline order set: " + ", ".join(map(str, session["order"])))

    @app.on_message(editor_chats & filters.command("timeline_duration"))
    async def timeline_duration_command(client, message):
        key, session = get_session(message)
        if not session:
            return await message.reply_text("Start a session with /timeline first.")
        if len(message.command) < 2:
            return await message.reply_text("Usage: /timeline_duration 1=5 2=3-12\nA=seconds sets duration; A=start-end trims a video.")
        async with session["lock"]:
            if session["rendering"]:
                return await message.reply_text("Your timeline is already rendering.")
            try:
                durations, trims = parse_duration_specs(" ".join(message.command[1:]), len(session["clips"]))
                for index in durations:
                    session["trims"].pop(index, None)
                for index in trims:
                    session["durations"].pop(index, None)
                session["durations"].update(durations)
                session["trims"].update(trims)
                session["last_activity"] = time.time()
            except ValueError as error:
                return await message.reply_text("⚠️ " + str(error))
        await message.reply_text("⏱ Clip timing updated. Clip numbers refer to upload order.")

    @app.on_message(editor_chats & filters.command("timeline_done"))
    async def timeline_done_command(client, message):
        key, session = get_session(message)
        if not session:
            return await message.reply_text("No active timeline. Start with /timeline.")
        opts = parse_options(" ".join(message.command[1:]))
        async with session["lock"]:
            if session["rendering"]:
                return await message.reply_text("Your timeline is already rendering.")
            clips = sorted(session["clips"], key=lambda item: item["message_id"])
            if len(clips) < 2:
                return await message.reply_text("Add at least two photos/videos before /timeline_done.")
            order = session["order"]
            if order is not None and sorted(order) != list(range(1, len(clips) + 1)):
                return await message.reply_text("You added more clips after setting the order. Set /timeline_order again.")
            original_audio = opts.get("original_audio", session["original_audio"]).lower()
            if original_audio not in {"keep", "mute"}:
                return await message.reply_text("Use original_audio=keep or original_audio=mute.")
            try:
                music_volume = number(opts.get("music_volume", .25), "music_volume", 0, 2)
            except ValueError as error:
                return await message.reply_text("⚠️ " + str(error))
            quality = opts.get("quality", session["quality"]).lower()
            session["rendering"] = True
            session["last_activity"] = time.time()
            render_clips = list(clips)
            render_order = list(order) if order else None
            durations = dict(session["durations"])
            trims = dict(session["trims"])
            music = session.get("music")
            photo_duration = session["photo_duration"]
            folder = session["folder"]

        status = None
        output = os.path.join(folder, "v3_timeline_final.mp4")
        succeeded = False
        try:
            status = await message.reply_text("🎬 **Building your timeline...**\n" + session_summary(session))
            result = await create_timeline(
                render_clips,
                output,
                music=music,
                order=render_order,
                durations=durations,
                trims=trims,
                photo_duration=photo_duration,
                original_audio=(original_audio == "keep"),
                music_volume=music_volume,
                quality=quality,
            )
            caption = (
                "🎬 **V3 Timeline Export Complete**\n"
                "🎞 Clips: " + str(result["clips"]) + "\n"
                "⏱ Duration: " + str(round(result["duration"], 1)) + "s\n"
                "🎵 Background music: " + ("yes" if music else "no") + "\n"
                "🔊 Original clip audio: " + original_audio + "\n"
                "⚡ V3 Music Editor"
            )
            await message.reply_video(output, caption=caption, supports_streaming=True)
            succeeded = True
            try:
                await status.delete()
            except Exception:
                pass
        except ValueError as error:
            text = "⚠️ " + str(error) + "\n\nYour clips are still saved. Adjust the timeline and run /timeline_done again."
            if status:
                await status.edit_text(text)
            else:
                await message.reply_text(text)
        except Exception as error:
            LOGGER.exception("V3 timeline render failed")
            text = "❌ **Timeline render failed.**\n" + str(error)[-700:] + "\n\nYour clips are still saved; check Railway logs if this repeats."
            if status:
                await status.edit_text(text)
            else:
                await message.reply_text(text)
        finally:
            if succeeded:
                TIMELINE_SESSIONS.pop(key, None)
                cleanup(folder)
            else:
                session["rendering"] = False
                if os.path.exists(output):
                    try:
                        os.remove(output)
                    except OSError:
                        pass

    @app.on_message(editor_chats & filters.command("timeline_cancel"))
    async def timeline_cancel_command(client, message):
        key, session = get_session(message)
        if not session:
            return await message.reply_text("No active timeline session.")
        async with session["lock"]:
            if session["rendering"]:
                return await message.reply_text("Wait until the current render finishes before cancelling.")
            TIMELINE_SESSIONS.pop(key, None)
            cleanup(session["folder"])
        await message.reply_text("🗑 Timeline session cancelled and temporary files removed.")

    @app.on_message(editor_chats & filters.command("edithelp"))
    async def edit_help_command(client, message):
        await message.reply_text(HELP, disable_web_page_preview=True)
