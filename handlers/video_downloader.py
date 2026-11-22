import asyncio
import ipaddress
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from pyrogram import filters
from pyrogram.types import Message
import yt_dlp

LOGGER = logging.getLogger(__name__)
URL_RE = re.compile(r"https?://[^\\s<>]+", re.IGNORECASE)
MAX_FILE_SIZE = int(os.getenv("VIDEO_DOWNLOAD_MAX_MB", "1900")) * 1024 * 1024
DOWNLOAD_TIMEOUT = int(os.getenv("VIDEO_DOWNLOAD_TIMEOUT", "900"))
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)
ACTIVE_DOWNLOADS = set()

def _safe_url(url: str) -> bool:
    try:
        parsed = urlparse(url.strip().rstrip(".,!?)]}"))
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        host = parsed.hostname.lower()
        if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        return True
    except Exception:
        return False

def _download_video(url: str, folder: str):
    template = os.path.join(folder, "%(title).120B [%(id)s].%(ext)s")
    options = {
        "format": "best[ext=mp4]/best", "outtmpl": template,
        "merge_output_format": "mp4", "noplaylist": True,
        "quiet": True, "no_warnings": True, "restrictfilenames": True,
        "windowsfilenames": True, "max_filesize": MAX_FILE_SIZE,
        "socket_timeout": 25, "retries": 2, "fragment_retries": 2,
        "concurrent_fragment_downloads": 4,
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("Is link se video information nahi mili.")
        if info.get("_type") == "playlist":
            raise RuntimeError("Playlist download disabled hai. Ek video ka link bhejein.")
        files = [p for p in Path(folder).glob("*") if p.is_file() and p.suffix.lower() not in {".part", ".ytdl", ".json", ".jpg", ".webp", ".png"}]
        if not files:
            prepared = Path(ydl.prepare_filename(info))
            if prepared.exists():
                files = [prepared]
        if not files:
            raise RuntimeError("Download file create nahi hui.")
        video = max(files, key=lambda p: p.stat().st_size)
        if video.stat().st_size > MAX_FILE_SIZE:
            raise RuntimeError("Video configured Telegram upload size limit se badi hai.")
        return str(video), info.get("title") or "Downloaded video"

async def _process_link(message: Message, url: str):
    key = (message.chat.id, url)
    if key in ACTIVE_DOWNLOADS:
        return
    ACTIVE_DOWNLOADS.add(key)
    folder = tempfile.mkdtemp(prefix="v3video_")
    status = None
    try:
        async with DOWNLOAD_SEMAPHORE:
            status = await message.reply_text("⏳ Video link detected! Downloading…")
            loop = asyncio.get_running_loop()
            task = loop.run_in_executor(None, _download_video, url, folder)
            try:
                video_path, title = await asyncio.wait_for(task, timeout=DOWNLOAD_TIMEOUT)
            except asyncio.TimeoutError:
                raise RuntimeError("Download time limit exceed ho gaya. Chhota video try karein.")
            await message.reply_video(video=video_path, caption=f"**{title[:900]}**\n\n๏ Downloaded by V3 MUSIC", supports_streaming=True)
            try:
                await status.delete()
            except Exception:
                pass
    except Exception as exc:
        LOGGER.exception("Video download failed for %s", url)
        error = str(exc).strip() or "Unknown error"
        if status:
            try:
                await status.edit_text(f"❌ Video download failed\n{error[:900]}")
            except Exception:
                pass
        else:
            await message.reply_text(f"❌ Video download failed\n{error[:900]}")
    finally:
        ACTIVE_DOWNLOADS.discard(key)
        shutil.rmtree(folder, ignore_errors=True)

def register_video_downloader_handlers(app):
    async def command_handler(client, message: Message):
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text("Usage: /vdownload https://website.com/video")
        match = URL_RE.search(parts[1])
        if not match or not _safe_url(match.group(0)):
            return await message.reply_text("Valid public http/https video link bhejein.")
        await _process_link(message, match.group(0).rstrip(".,!?)]}"))

    async def auto_link_handler(client, message: Message):
        if not message.from_user or message.from_user.is_bot:
            return
        text = message.text or message.caption or ""
        match = URL_RE.search(text)
        if not match:
            return
        url = match.group(0).rstrip(".,!?)]}")
        if _safe_url(url):
            await _process_link(message, url)

    app.on_message(filters.command("vdownload") & (filters.private | filters.group), group=20)(command_handler)
    app.on_message((filters.private | filters.group) & (filters.text | filters.caption), group=30)(auto_link_handler)
