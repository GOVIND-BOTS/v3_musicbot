import asyncio
import re
import yt_dlp

YOUTUBE_URL_PATTERN = re.compile(r"(youtube\.com|youtu\.be)", re.I)
YDL_BASE_OPTIONS = {
    "quiet": True, "no_warnings": True, "noplaylist": True,
    "skip_download": True, "extract_flat": False,
    "socket_timeout": 15, "retries": 2,
}

def is_youtube_url(query: str) -> bool:
    return bool(YOUTUBE_URL_PATTERN.search(query or ""))

def format_duration(seconds):
    if seconds is None:
        return "LIVE"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def normalize_video(info):
    if not info:
        return None
    return {
        "title": info.get("title") or "Unknown title",
        "videoid": info.get("id") or "",
        "duration": info.get("duration"),
        "duration_text": format_duration(info.get("duration")),
        "views": info.get("view_count") or 0,
        "channel": info.get("channel") or info.get("uploader") or "Unknown",
        "thumbnail": info.get("thumbnail") or "",
        "webpage_url": info.get("webpage_url") or (f"https://www.youtube.com/watch?v={info.get('id')}" if info.get("id") else ""),
        "url": info.get("url") or "",
    }

def _search_youtube(query, limit=5):
    opts = dict(YDL_BASE_OPTIONS)
    opts["extract_flat"] = False
    with yt_dlp.YoutubeDL(opts) as ydl:
        data = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    return [normalize_video(x) for x in (data or {}).get("entries", []) if x]

async def search_youtube(query, limit=5):
    return await asyncio.to_thread(_search_youtube, query, limit)

def _get_video_info(url):
    with yt_dlp.YoutubeDL(dict(YDL_BASE_OPTIONS)) as ydl:
        return normalize_video(ydl.extract_info(url, download=False))

async def get_video_info(url):
    if not is_youtube_url(url):
        raise ValueError("Please send a valid YouTube URL.")
    return await asyncio.to_thread(_get_video_info, url)

def _get_stream_url(url, media_type="audio"):
    opts = dict(YDL_BASE_OPTIONS)
    opts["format"] = "bestaudio/best" if media_type == "audio" else "best[height<=480][ext=mp4]/best[height<=480]"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    result = normalize_video(info)
    result["url"] = info.get("url")
    result["media_type"] = media_type
    if not result["url"]:
        raise RuntimeError("Could not get a playable stream URL.")
    return result

async def get_stream_url(url, media_type="audio"):
    return await asyncio.to_thread(_get_stream_url, url, media_type)
