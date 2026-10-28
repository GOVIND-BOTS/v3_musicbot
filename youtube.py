import asyncio
import logging
import os
import re

import yt_dlp


LOGGER = logging.getLogger(__name__)


YOUTUBE_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:youtube\.com|youtu\.be)",
    re.IGNORECASE
)


COOKIES_PATH = os.path.join("cookies", "cookies.txt")


YDL_BASE_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "skip_download": True,
    "extract_flat": False,

    # Network
    "socket_timeout": 20,
    "retries": 3,
    "fragment_retries": 3,
    "continuedl": True,

    # Avoid unnecessary files
    "cachedir": False,

    # YouTube client compatibility
    "extractor_args": {
        "youtube": {
            "player_client": [
                "android",
                "web"
            ]
        }
    },
}

# Cookies add karo agar file exist karti hai
if os.path.exists(COOKIES_PATH):
    YDL_BASE_OPTIONS["cookiefile"] = COOKIES_PATH
    LOGGER.info("YouTube cookies loaded from %s", COOKIES_PATH)
else:
    LOGGER.warning("Cookies file not found at %s — YouTube may block requests", COOKIES_PATH)


def is_youtube_url(query: str) -> bool:
    return bool(
        YOUTUBE_URL_PATTERN.search(query or "")
    )


def format_duration(seconds):
    if seconds is None:
        return "LIVE"

    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "LIVE"

    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)

    if h:
        return f"{h}:{m:02d}:{s:02d}"

    return f"{m}:{s:02d}"


def normalize_video(info):
    if not info:
        return None

    video_id = info.get("id") or ""

    webpage_url = (
        info.get("webpage_url")
        or info.get("original_url")
        or (
            f"https://www.youtube.com/watch?v={video_id}"
            if video_id
            else ""
        )
    )

    return {
        "title": info.get("title") or "Unknown title",

        "videoid": video_id,

        "duration": info.get("duration"),

        "duration_text": format_duration(
            info.get("duration")
        ),

        "views": info.get("view_count") or 0,

        "channel": (
            info.get("channel")
            or info.get("uploader")
            or info.get("creator")
            or "Unknown"
        ),

        "thumbnail": (
            info.get("thumbnail")
            or ""
        ),

        "webpage_url": webpage_url,

        # This is intentionally preserved.
        # get_stream_url() replaces it with the
        # direct playable media URL.
        "url": info.get("url") or "",
    }


def _search_youtube(query, limit=5):
    query = (query or "").strip()

    if not query:
        return []

    try:
        limit = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        limit = 5

    options = dict(YDL_BASE_OPTIONS)

    options["extract_flat"] = False

    search_query = f"ytsearch{limit}:{query}"

    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(
            search_query,
            download=False
        )

    entries = (
        (data or {}).get("entries")
        or []
    )

    results = []

    for entry in entries:
        if not entry:
            continue

        normalized = normalize_video(entry)

        if normalized:
            results.append(normalized)

    return results


async def search_youtube(query, limit=5):
    return await asyncio.to_thread(
        _search_youtube,
        query,
        limit
    )


def _get_video_info(url):
    url = (url or "").strip()

    if not is_youtube_url(url):
        raise ValueError(
            "Please send a valid YouTube URL."
        )

    options = dict(YDL_BASE_OPTIONS)

    options["extract_flat"] = False

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=False
        )

    result = normalize_video(info)

    if not result:
        raise RuntimeError(
            "Could not extract YouTube video information."
        )

    return result


async def get_video_info(url):
    return await asyncio.to_thread(
        _get_video_info,
        url
    )


def _get_stream_url(url, media_type="audio"):
    url = (url or "").strip()

    if not is_youtube_url(url):
        raise ValueError(
            "Please send a valid YouTube URL."
        )

    media_type = (
        "video"
        if str(media_type).lower() == "video"
        else "audio"
    )

    options = dict(YDL_BASE_OPTIONS)

    # We need the actual media URL, not only
    # metadata.
    options["extract_flat"] = False

    if media_type == "audio":
        options["format"] = (
            "bestaudio/best"
        )

    else:
        options["format"] = (
            "bestvideo[height<=480]+bestaudio/"
            "best[height<=480]/"
            "best"
        )

        options["merge_output_format"] = "mp4"

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            url,
            download=False
        )

    if not info:
        raise RuntimeError(
            "YouTube returned no video information."
        )

    direct_url = info.get("url")

    # Some yt-dlp extraction results contain
    # multiple formats instead of a top-level URL.
    if not direct_url:
        formats = info.get("formats") or []

        if media_type == "audio":
            audio_formats = [
                item for item in formats
                if item.get("url")
                and (
                    item.get("acodec")
                    and item.get("acodec") != "none"
                )
            ]

            if audio_formats:
                audio_formats.sort(
                    key=lambda item: (
                        item.get("abr") or 0
                    ),
                    reverse=True
                )

                direct_url = (
                    audio_formats[0].get("url")
                )

        else:
            video_formats = [
                item for item in formats
                if item.get("url")
                and (
                    item.get("vcodec")
                    and item.get("vcodec") != "none"
                )
            ]

            if video_formats:
                video_formats.sort(
                    key=lambda item: (
                        item.get("height") or 0,
                        item.get("tbr") or 0
                    ),
                    reverse=True
                )

                direct_url = (
                    video_formats[0].get("url")
                )

    if not direct_url:
        raise RuntimeError(
            "Could not get a playable stream URL "
            "from YouTube."
        )

    result = normalize_video(info)

    if not result:
        raise RuntimeError(
            "Could not normalize YouTube information."
        )

    result["url"] = direct_url
    result["media_type"] = media_type

    return result


async def get_stream_url(url, media_type="audio"):
    return await asyncio.to_thread(
        _get_stream_url,
        url,
        media_type
    )
