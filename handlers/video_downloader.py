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

SUPPORTED_DOMAINS = {
    "instagram.com", "instagr.am",
    "youtube.com", "youtu.be", "youtube-nocookie.com",
    "tiktok.com",
    "facebook.com", "fb.watch",
    "x.com", "twitter.com",
    "vimeo.com",
    "dailymotion.com", "dai.ly",
    "reddit.com", "redd.it",
    "twitch.tv",
    "pinterest.com", "pin.it",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".3gp"
}


def _parsed_url(url: str):
    parsed = urlparse(url.strip().rstrip(".,!?)]}"))
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    return parsed


def _safe_url(url: str) -> bool:
    """Accept known video-platform domains; reject local/private IP addresses."""
    try:
        parsed = _parsed_url(url)
        if not parsed or parsed.username or parsed.password:
            return False

        host = parsed.hostname.lower().rstrip(".")
        if not any(
            host == domain or host.endswith("." + domain)
            for domain in SUPPORTED_DOMAINS
        ):
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
        "extractor_retries": 2,
        "concurrent_fragment_downloads": 4,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        if not info:
            raise RuntimeError("Video information could not be read from this link.")
        if info.get("_type") == "playlist" or info.get("entries"):
            raise RuntimeError("Playlist downloads are disabled. Please send one video link.")

        files = [
            path for path in Path(folder).iterdir()
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
        ]
        if not files:
            prepared = Path(ydl.prepare_filename(info))
            if prepared.exists() and prepared.suffix.lower() in VIDEO_EXTENSIONS:
                files = [prepared]
        if not files:
            raise RuntimeError("No video file was produced. This link may contain audio only.")

        video = max(files, key=lambda path: path.stat().st_size)
        if video.stat().st_size > MAX_FILE_SIZE:
            raise RuntimeError("The video exceeds the configured Telegram upload size limit.")

        return str(video), info.get("title") or "Downloaded video"


def _friendly_error(exc: Exception) -> str:
    message = str(exc).lower()

    if any(term in message for term in (
        "sign in to confirm", "not a bot", "login", "cookie",
        "authentication", "redirected to the login page",
    )):
        return (
            "This platform is requiring sign-in or verification. "
            "Only public videos accessible without login are supported."
        )
    if any(term in message for term in (
        "rate-limit", "rate limit", "too many requests", "http error 429",
    )):
        return (
            "The platform is temporarily limiting requests from this server. "
            "Please try again later; platform limits are not bypassed."
        )
    if "unsupported url" in message or "no suitable extractor" in message:
        return "This link format is not supported. Send a direct video or public post link from a supported platform."
    if "private" in message or "not available" in message or "unavailable" in message:
        return "This video is private or unavailable."
    if "max-filesize" in message or "file is larger" in message:
        return "The video is larger than the configured Telegram upload size limit."
    if "no video file was produced" in message:
        return "This link did not provide a video. Audio-only links are not supported here."
    return "Could not download this video. Check that the link is public and supported, then try again."


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
                "Usage: /vdownload https://www.instagram.com/reel/..."
            )

        match = URL_RE.search(parts[1])
        if not match:
            return await message.reply_text("Please send a valid video link.")

        url = match.group(0).rstrip(".,!?)]}")
        if not _safe_url(url):
            return await message.reply_text(
                "This link is not supported. Send a public video/post link "
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
