import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path

from pyrogram import filters
from pyrogram.enums import ParseMode

LOGGER = logging.getLogger(__name__)
MAX_INPUT_MB = int(os.getenv("AUDIO_CONVERT_MAX_MB", "500"))
MAX_INPUT_BYTES = MAX_INPUT_MB * 1024 * 1024
MAX_OUTPUT_BYTES = 49 * 1024 * 1024


def _media_file(message):
    return (
        getattr(message, "video", None)
        or getattr(message, "animation", None)
        or getattr(message, "audio", None)
        or getattr(message, "voice", None)
        or getattr(message, "video_note", None)
        or getattr(message, "document", None)
    )


async def _convert_to_mp3(message):
    replied = message.reply_to_message
    if not replied:
        await message.reply_text("Reply to a video or audio file with /toaudio.")
        return

    media = _media_file(replied)
    if not media:
        await message.reply_text("Reply to a Telegram video, audio, voice note, or media document.")
        return

    size = getattr(media, "file_size", 0) or 0
    if size > MAX_INPUT_BYTES:
        await message.reply_text(f"File is too large. Maximum input size is {MAX_INPUT_MB} MB.")
        return

    status = await message.reply_text("⏳ Extracting audio and converting to MP3…")
    folder = tempfile.mkdtemp(prefix="v3_toaudio_")
    source = os.path.join(folder, "input_media")
    output = os.path.join(folder, "audio.mp3")

    try:
        downloaded = await replied.download(file_name=source)
        if not downloaded or not os.path.isfile(downloaded):
            raise RuntimeError("Telegram could not download the replied media.")

        process = await asyncio.create_subprocess_exec(
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
            "-y", "-i", downloaded, "-vn", "-map", "0:a:0",
            "-codec:a", "libmp3lame", "-q:a", "2",
            "-id3v2_version", "3", output,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            raise RuntimeError("Conversion timed out after 10 minutes.")

        if process.returncode != 0 or not os.path.isfile(output) or os.path.getsize(output) == 0:
            detail = stderr.decode("utf-8", "ignore")[-700:]
            raise RuntimeError(detail or "No audio stream was found in this file.")

        if os.path.getsize(output) > MAX_OUTPUT_BYTES:
            raise RuntimeError("Converted MP3 is larger than Telegram's 50 MB audio upload limit.")

        original_name = getattr(media, "file_name", None) or "converted_audio"
        title = Path(original_name).stem[:60] or "converted_audio"
        await message.reply_audio(
            audio=output,
            title=title,
            caption="🎵 <b>Audio extracted successfully</b>\n\n๏ V3 MUSIC",
            parse_mode=ParseMode.HTML,
        )
        await status.delete()

    except Exception as exc:
        LOGGER.exception("Video/audio to MP3 conversion failed")
        try:
            await status.edit_text(f"❌ Conversion failed: {str(exc)[:700]}")
        except Exception:
            pass
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def register_media_conversion_handlers(app):
    @app.on_message(filters.command(["toaudio", "extractaudio"]) & (filters.private | filters.group))
    async def to_audio_handler(client, message):
        await _convert_to_mp3(message)
