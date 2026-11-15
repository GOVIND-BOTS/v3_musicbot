import asyncio
import logging
import os
import tempfile
from pathlib import Path

from pyrogram import filters
from editor.engine import edit_photo, edit_video, parse_options, photo_to_video

LOGGER = logging.getLogger(__name__)
HELP = (
    "🎬 **V3 CAPCUT-STYLE EDITOR**\n\n"
    "Reply to a photo/video with /edit.\n\n"
    "**Photo:**\n"
    "/edit brightness=1.2 contrast=1.1 saturation=1.3\n"
    "/edit filter=warm (bw / warm / cool / blur / sharpen)\n"
    "/edit crop=square (square / portrait)\n"
    "/edit rotate=90 mirror text=Govind\n\n"
    "**Video (1–120 seconds):**\n"
    "/edit start=5 end=45 speed=1.5\n"
    "/edit quality=720p brightness=0.1 contrast=1.1\n"
    "/edit mute mirror rotate=90 text=V3_MUSIC\n\n"
    "Reply to a photo with /photo2video 15 to create a 15-second video.\n"
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
        if mime.startswith("video/") or suffix in {".mp4", ".mov", ".mkv", ".webm", ".m4v"}:
            return "video"
    return None

async def download_media(message, path):
    downloaded = await message.download(file_name=path)
    if not downloaded or not os.path.exists(downloaded):
        raise RuntimeError("Could not download the replied media.")
    return downloaded

def cleanup(folder):
    for name in os.listdir(folder):
        try:
            os.remove(os.path.join(folder, name))
        except OSError:
            pass
    try:
        os.rmdir(folder)
    except OSError:
        pass

def register_editor_handlers(app):
    @app.on_message(filters.command(["edit", "photoedit", "videoedit"]))
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

    @app.on_message(filters.command("photo2video"))
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

    @app.on_message(filters.command("edithelp"))
    async def edit_help_command(client, message):
        await message.reply_text(HELP, disable_web_page_preview=True)
