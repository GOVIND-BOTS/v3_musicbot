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
URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
MAX_FILE_SIZE = int(os.getenv("VIDEO_DOWNLOAD_MAX_MB", "1900")) * 1024 * 1024
DOWNLOAD_SEMAPHORE = asyncio.Semaphore(2)
ACTIVE_DOWNLOADS = set()

# Only accept mainstream platforms with supported yt-dlp extractors.
# This prevents arbitrary URLs (including unsupported invite/profile pages)
# from being sent to yt-dlp's generic extractor.
SUPPORTED_HOSTS = {
    "instagram.com", "www.instagram.com", "instagr.am",
    "youtube.com", "www.youtube.com", "m.youtube.com",
    "music.youtube.com", "youtu.be",
    "tiktok.com", "www.tiktok.com", "vm.tiktok.com", "vt.tiktok.com",
    "facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch",
    "x.com", "www.x.com", "twitter.com", "www.twitter.com",
    "vimeo.com", "www.vimeo.com", "player.vimeo.com",
    "dailymotion.com", "www.dailymotion.com", "dai.ly",
    "reddit.com", "www.reddit.com", "v.redd.it",
    "twitch.tv", "www.twitch.tv", "clips.twitch.tv",
    "soundcloud.com", "www.soundcloud.com",
    "pinterest.com", "www.pinterest.com", "pin.it",
}


def _parsed_url(url: str):
    parsed = urlparse(url.strip().rstrip(".,!?)]}"))
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return parsed


def _safe_url(url: str) -> bool:
    try:
        parsed = _parsed_url(url)
        if not parsed or parsed.username or parsed.password:
            return False

        host = parsed.hostname.lower().rstrip(".")
        if host not in SUPPORTED_HOSTS:
            return False

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
        "format": "best[ext=mp4]/best",
        "outtmpl": template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "restrictfilenames": True,
        "windowsfilenames": True,
        "max_filesize": MAX_FILE_SIZE,
        "socket_timeout": 25,
        "retries": 2,
        "fragment_retries": 2,
        "concurrent_fragment_downloads": 4,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("Video information could not be read from this link.")
        if info.get("_type") == "playlist":
            raise RuntimeError("Playlist downloads are disabled. Please send one video link.")

        files = [
            path for path in Path(folder).glob("*")
            if path.is_file()
            and path.suffix.lower() not in {
                ".part", ".ytdl", ".json", ".jpg", ".webp", ".png"
            }
        ]
        if not files:
            prepared = Path(ydl.prepare_filename(info))
            if prepared.exists():
                files = [prepared]
        if not files:
            raise RuntimeError("The download file could not be created.")

        video = max(files, key=lambda path: path.stat().st_size)
        if video.stat().st_size > MAX_FILE_SIZE:
            raise RuntimeError("The video exceeds the configured Telegram upload size limit.")

        return str(video), info.get("title") or "Downloaded video"


def _friendly_error(exc: Exception) -> str:
    message = str(exc).lower()

    if "login" in message or "cookie" in message or "authentication" in message:
        return "This post may require a signed-in account. Private or login-only posts are not supported."
    if "unsupported url" in message or "no suitable extractor" in message:
        return "This link type is not supported. Send a direct video, Reel, or supported post link."
    if "private" in message or "not available" in message or "unavailable" in message:
        return "This video is private or unavailable."
    if "max-filesize" in message or "file is larger" in message:
        return "The video is larger than the configured upload limit."
    return "Could not download this video. Check that the post is public and the link is supported."


async def _process_link(message: Message, url: str):
    key = (message.chat.id, url)
    if key in ACTIVE_DOWNLOADS:
        return

    ACTIVE_DOWNLOADS.add(key)
    folder = tempfile.mkdtemp(prefix="v3video_")
    status = None

    try:
        async with DOWNLOAD_SEMAPHORE:
            status = await message.reply_text("⏳ Supported video link detected. Downloading…")
            loop = asyncio.get_running_loop()
            task = loop.run_in_executor(None, _download_video, url, folder)
            video_path, title = await task

            await message.reply_video(
                video=video_path,
                caption=f"**{title[:900]}**\n\n๏ Downloaded by V3 MUSIC",
                supports_streaming=True,
            )
            try:
                await status.delete()
            except Exception:
                pass

    except Exception as exc:
        LOGGER.warning("Video download failed (%s): %s", url, exc, exc_info=True)
        friendly = _friendly_error(exc)
        if status:
            try:
                await status.edit_text(f"❌ {friendly}")
            except Exception:
                pass
        else:
            await message.reply_text(f"❌ {friendly}")

    finally:
        ACTIVE_DOWNLOADS.discard(key)
        shutil.rmtree(folder, ignore_errors=True)


def register_video_downloader_handlers(app):
    async def command_handler(client, message: Message):
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            return await message.reply_text(
                "Usage: /vdownload https://www.instagram.com/reel/... "
            )

        match = URL_RE.search(parts[1])
        if not match:
            return await message.reply_text("Please send a valid video link.")

        url = match.group(0).rstrip(".,!?)]}")
        if not _safe_url(url):
            return await message.reply_text(
                "This link is not supported. Use a public video/Reel/post link "
                "from a supported platform."
            )

        await _process_link(message, url)

    async def auto_link_handler(client, message: Message):
        if not message.from_user or message.from_user.is_bot:
            return

        text = message.text or message.caption or ""
        if text.lstrip().startswith("/vdownload"):
            return

        match = URL_RE.search(text)
        if not match:
            return

        url = match.group(0).rstrip(".,!?)]}")
        # Ignore ordinary websites, Telegram invite/channel links, and unknown hosts.
        if _safe_url(url):
            await _process_link(message, url)

    app.on_message(
        filters.command("vdownload") & (filters.private | filters.group),
        group=20,
    )(command_handler)
    app.on_message(
        (filters.private | filters.group) & (filters.text | filters.caption),
        group=30,
    )(auto_link_handler)
