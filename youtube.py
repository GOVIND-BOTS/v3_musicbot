
import asyncio
import logging
import os
import re
from pathlib import Path

import yt_dlp

LOGGER = logging.getLogger(__name__)

YOUTUBE_URL_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?"
    r"(?:youtube\.com|youtu\.be)"
    r"(?::\d+)?(?:[/?#]|$)",
    re.IGNORECASE,
)


def _find_cookies_file():
    """
    Find cookies from:
    1. YOUTUBE_COOKIES environment variable
    2. cookies/cookies.txt in project directory or its parents
    3. cookies.txt in project directory or its parents
    """

    env_path = os.environ.get("YOUTUBE_COOKIES")

    if env_path:
        candidate = Path(env_path).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())

    current_dir = Path(__file__).resolve().parent

    for directory in (current_dir, *current_dir.parents):
        candidates = (
            directory / "cookies" / "cookies.txt",
            directory / "cookies.txt",
        )

        for candidate in candidates:
            if candidate.is_file() and candidate.stat().st_size > 0:
                return str(candidate.resolve())

    return None


COOKIES_PATH = _find_cookies_file()

YDL_BASE_OPTIONS = {
    "quiet": True,
    "no_warnings": True,
    "noplaylist": True,
    "skip_download": True,
    "socket_timeout": 30,
    "retries": 2,
    "fragment_retries": 2,
    "cachedir": False,
}

if COOKIES_PATH:
    YDL_BASE_OPTIONS["cookiefile"] = COOKIES_PATH
    LOGGER.info("YouTube cookies file found and configured.")
else:
    LOGGER.warning(
        "YouTube cookies file not found. "
        "Expected: cookies/cookies.txt"
    )

LOGGER.info(
    "Loaded yt-dlp version: %s",
    yt_dlp.version.__version__,
)


def is_youtube_url(query):
    return bool(YOUTUBE_URL_PATTERN.search(query or ""))


def format_duration(seconds):
    if seconds is None:
        return "LIVE"

    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "LIVE"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


def _get_thumbnail(info):
    if not info:
        return ""

    thumbnail = info.get("thumbnail")

    if thumbnail:
        return thumbnail

    thumbnails = info.get("thumbnails") or []

    for item in reversed(thumbnails):
        if item and item.get("url"):
            return item["url"]

    return ""


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
        "duration_text": format_duration(info.get("duration")),
        "views": info.get("view_count") or 0,
        "channel": (
            info.get("channel")
            or info.get("uploader")
            or info.get("creator")
            or "Unknown"
        ),
        "thumbnail": _get_thumbnail(info),
        "webpage_url": webpage_url,
        "url": info.get("url") or "",
    }


def _make_options(selected_format=None):
    """
    Keep yt-dlp's automatic YouTube client selection.
    When cookies are configured, yt-dlp can select
    the appropriate clients for authenticated requests.
    """

    options = dict(YDL_BASE_OPTIONS)

    if selected_format:
        options["format"] = selected_format

    return options


def _search_youtube(query, limit=5):
    query = (query or "").strip()

    if not query:
        return []

    try:
        limit = max(1, min(int(limit), 10))
    except (TypeError, ValueError):
        limit = 5

    options = _make_options()
    options["extract_flat"] = "in_playlist"

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            data = ydl.extract_info(
                f"ytsearch{limit}:{query}",
                download=False,
            )

    except Exception as exc:
        LOGGER.error("YouTube search failed: %s", exc)
        return []

    results = []

    for entry in (data or {}).get("entries") or []:
        if not entry:
            continue

        normalized = normalize_video(entry)

        if normalized and normalized.get("videoid"):
            results.append(normalized)

    return results


async def search_youtube(query, limit=5):
    return await asyncio.to_thread(
        _search_youtube,
        query,
        limit,
    )


def _get_video_info(url):
    url = (url or "").strip()

    if not is_youtube_url(url):
        raise ValueError("Please send a valid YouTube URL.")

    try:
        with yt_dlp.YoutubeDL(_make_options()) as ydl:
            info = ydl.extract_info(
                url,
                download=False,
            )

        result = normalize_video(info)

        if not result:
            raise RuntimeError("YouTube returned no video information.")

        return result

    except Exception as exc:
        LOGGER.exception("YouTube video information extraction failed.")
        raise RuntimeError(
            f"Could not retrieve YouTube video information: {exc}"
        ) from exc


async def get_video_info(url):
    return await asyncio.to_thread(
        _get_video_info,
        url,
    )


def _get_stream_url(url, media_type="audio"):
    url = (url or "").strip()

    if not is_youtube_url(url):
        raise ValueError("Please send a valid YouTube URL.")

    media_type = (
        "video"
        if str(media_type).lower() == "video"
        else "audio"
    )

    if media_type == "audio":
        format_attempts = (
            "bestaudio/best",
            "best",
            None,
        )
    else:
        format_attempts = (
            "best[height<=480][vcodec!=none]/best[height<=480]/best",
            "best",
            None,
        )

    last_error = None

    for selected_format in format_attempts:
        try:
            options = _make_options(selected_format)

            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(
                    url,
                    download=False,
                )

            if not info:
                raise RuntimeError(
                    "YouTube returned no video information."
                )

            direct_url = info.get("url")
            formats = info.get("formats") or []

            if not direct_url:
                if media_type == "audio":
                    candidates = [
                        item
                        for item in formats
                        if item.get("url")
                        and item.get("acodec")
                        and item.get("acodec") != "none"
                    ]

                    candidates.sort(
                        key=lambda item: (
                            item.get("abr") or 0,
                            item.get("tbr") or 0,
                        ),
                        reverse=True,
                    )

                else:
                    candidates = [
                        item
                        for item in formats
                        if item.get("url")
                        and item.get("vcodec")
                        and item.get("vcodec") != "none"
                        and (item.get("height") or 0) <= 480
                        and item.get("acodec")
                        and item.get("acodec") != "none"
                    ]

                    candidates.sort(
                        key=lambda item: (
                            item.get("height") or 0,
                            item.get("tbr") or 0,
                        ),
                        reverse=True,
                    )

                if candidates:
                    direct_url = candidates[0]["url"]

            if not direct_url:
                raise RuntimeError(
                    "No compatible direct stream URL was found."
                )

            result = normalize_video(info)

            if not result:
                raise RuntimeError(
                    "Could not normalize YouTube information."
                )

            result["url"] = direct_url
            result["media_type"] = media_type

            LOGGER.info(
                "YouTube stream resolved successfully: media=%s",
                media_type,
            )

            return result

        except Exception as exc:
            last_error = exc

            LOGGER.warning(
                "YouTube stream attempt failed "
                "(media=%s, format=%s): %s",
                media_type,
                selected_format or "default",
                exc,
            )

    raise RuntimeError(
        f"Unable to resolve a YouTube {media_type} stream. "
        f"Last error: {last_error}"
    ) from last_error


async def get_stream_url(url, media_type="audio"):
    return await asyncio.to_thread(
        _get_stream_url,
        url,
        media_type,
    )
