
import pyrogram.errors

if not hasattr(pyrogram.errors, "GroupcallForbidden"):
    class GroupcallForbidden(Exception):
        pass
    pyrogram.errors.GroupcallForbidden = GroupcallForbidden

import os
import asyncio
import logging
import threading
from pathlib import Path
from http.server import BaseHTTPRequestHandler, HTTPServer
from collections import defaultdict

import yt_dlp
from pyrogram import Client, filters, idle
from pyrogram.types import Message, CallbackQuery
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality

from config import API_ID, API_HASH, BOT_TOKEN, SESSION_STRING, BOT_NAME, TRIGGER
from buttons import stream_buttons, queue_buttons
from thumbnails import get_thumb


# ─────────────── Health Check (Render/Railway) ───────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Music bot is running!")

    def log_message(self, format, *args):
        pass


def run_web_server():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()


threading.Thread(target=run_web_server, daemon=True).start()


# ─────────────── Logging ───────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger("V3Music")


# ─────────────── YouTube Cookies ───────────────
BASE_DIR = Path(__file__).resolve().parent

# Root folder me cookies.txt
YOUTUBE_COOKIE_FILE = BASE_DIR / "cookies.txt"

if YOUTUBE_COOKIE_FILE.is_file():
    logger.info(
        f"🍪 YouTube cookies found: {YOUTUBE_COOKIE_FILE}"
    )
else:
    logger.warning(
        "🍪 cookies.txt not found. YouTube will run without cookies."
    )


# ─────────────── Clients ───────────────
bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ─────────────── Pyrogram Assistant Session ───────────────
SESSION_STRING = SESSION_STRING.strip()

if not SESSION_STRING:
    raise ValueError(
        "SESSION_STRING is empty. Please provide a valid Pyrogram session string."
    )


# Safe diagnostics: complete session kabhi print nahi hoga
print("================================")
print("PYROGRAM SESSION CHECK")
print("SESSION TYPE:", type(SESSION_STRING))
print("SESSION LENGTH:", len(SESSION_STRING))
print("SESSION START:", SESSION_STRING[:10])
print("================================")


assistant = Client(
    "vc_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

calls = PyTgCalls(assistant)


# ─────────────── Data ───────────────
queues = defaultdict(list)
current = {}
linked_channels = {}


# ─────────────── YouTube Stream Helper ───────────────
def get_stream_url(query: str, video: bool = False):
    """
    YouTube se stream URL extract karta hai.

    Agar root folder me cookies.txt available hai,
    yt-dlp usko automatically use karega.
    """

    search = (
        query
        if query.startswith("http")
        else f"ytsearch1:{query}"
    )

    if video:
        stream_format = (
            "best[height<=720][vcodec!=none][acodec!=none]/"
            "best[height<=720]/best"
        )
    else:
        stream_format = (
            "bestaudio[ext=m4a]/"
            "bestaudio/"
            "best"
        )

    ydl_opts = {
        "format": stream_format,

        "quiet": True,
        "no_warnings": True,

        # Sirf requested video/song
        "noplaylist": True,

        # Download nahi karna
        "skip_download": True,

        # YouTube certificate/network compatibility
        "nocheckcertificate": True,

        # Extraction timeout
        "socket_timeout": 30,

        # Keep extractor output normal
        "extract_flat": False,
    }

    # ─────────────── Cookies ───────────────
    if YOUTUBE_COOKIE_FILE.is_file():
        ydl_opts["cookiefile"] = str(YOUTUBE_COOKIE_FILE)

        logger.info(
            "🍪 yt-dlp is using cookies.txt"
        )
    else:
        logger.warning(
            "⚠️ yt-dlp is running without cookies.txt"
        )

    logger.info(
        f"🎵 YouTube extraction started | "
        f"query={query!r} | video={video}"
    )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                search,
                download=False
            )

    except Exception as e:
        logger.exception(
            "❌ yt-dlp extraction failed"
        )
        raise RuntimeError(
            f"YouTube extraction failed: {e}"
        ) from e

    if not info:
        raise ValueError(
            "YouTube se information nahi mili."
        )

    # ytsearch1 result
    if "entries" in info:
        entries = info.get("entries") or []

        info = next(
            (entry for entry in entries if entry),
            None
        )

    if not info:
        raise ValueError(
            "Song nahi mila."
        )

    stream_url = info.get("url")

    if not stream_url:
        raise ValueError(
            "YouTube stream URL nahi mila."
        )

    # ─────────────── Duration ───────────────
    duration_seconds = info.get("duration")

    if duration_seconds:
        duration = info.get("duration_string")

        if not duration:
            duration = (
                f"{int(duration_seconds) // 60:02d}:"
                f"{int(duration_seconds) % 60:02d}"
            )
    else:
        duration = "00:00"

    # ─────────────── Views ───────────────
    views = str(
        info.get("view_count", "Unknown")
    )

    if views.isdigit():
        views = f"{int(views):,}"

    # ─────────────── Basic Info ───────────────
    title = info.get("title") or "Unknown"

    video_id = info.get("id") or ""

    channel = (
        info.get("uploader")
        or info.get("channel")
        or "Unknown"
    )

    webpage_url = (
        info.get("webpage_url")
        or (
            f"https://www.youtube.com/watch?v={video_id}"
            if video_id
            else ""
        )
    )

    logger.info(
        f"✅ YouTube stream extracted | "
        f"title={title!r} | "
        f"id={video_id} | "
        f"duration={duration}"
    )

    return {
        "url": stream_url,
        "title": title,
        "videoid": video_id,
        "duration": duration,
        "views": views,
        "channel": channel,
        "webpage_url": webpage_url,
    }


# ─────────────── Start Stream ───────────────
async def start_stream(
    chat_id: int,
    track: dict,
    video: bool = False
):
    try:
        logger.info(
            f"🎧 Starting stream | "
            f"chat={chat_id} | "
            f"title={track.get('title')} | "
            f"video={video}"
        )

        if video:
            stream = MediaStream(
                track["url"],
                AudioQuality.HIGH,
                VideoQuality.HD_720p
            )
        else:
            stream = MediaStream(
                track["url"],
                AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE
            )

        await calls.play(
            chat_id,
            stream
        )

        current[chat_id] = track

        logger.info(
            f"✅ PyTgCalls stream started | "
            f"chat={chat_id}"
        )

    except Exception:
        logger.exception(
            f"❌ PyTgCalls playback failed | "
            f"chat={chat_id}"
        )
        raise


# ─────────────── Play Next ───────────────
async def play_next(chat_id: int):
    if queues[chat_id]:
        track = queues[chat_id].pop(0)

        try:
            await start_stream(
                chat_id,
                track,
                track.get("video", False)
            )

            return track

        except Exception as e:
            logger.exception(
                f"❌ Queue playback failed: {e}"
            )

            return await play_next(chat_id)

    current.pop(chat_id, None)

    try:
        await calls.leave_call(chat_id)
    except Exception:
        pass

    return None


# ─────────────── Handle Play ───────────────
async def handle_play(
    message: Message,
    query: str,
    video: bool = False,
    target_chat_id: int = None
):
    chat_id = target_chat_id or message.chat.id

    mystic = await message.reply_text(
        "🔎 **Searching...**"
    )

    try:
        data = get_stream_url(
            query,
            video
        )

    except Exception as e:
        logger.exception(
            f"❌ Song extraction failed: {e}"
        )

        return await mystic.edit_text(
            "❌ Song Not found.\n\n"
            "YouTube extraction failed."
        )

    track = {
        "title": data["title"],
        "url": data["url"],
        "videoid": data["videoid"],
        "duration": data["duration"],
        "views": data["views"],
        "channel": data["channel"],
        "video": video,
        "requester": message.from_user.mention,
        "requester_id": message.from_user.id,
    }

    # ─────────────── Queue ───────────────
    if chat_id in current and current[chat_id]:

        queues[chat_id].append(track)

        pos = len(
            queues[chat_id]
        )

        thumb = await get_thumb(
            data["videoid"],
            data["title"],
            data["duration"],
            data["views"],
            data["channel"],
            BOT_NAME
        )

        caption = (
            f"**♡ Added to Queue**\n\n"
            f"**Title:** "
            f"[{data['title']}]"
            f"({data.get('webpage_url', '')})\n"
            f"**Duration:** `{data['duration']}`\n"
            f"**Position:** `{pos}`\n"
            f"**Requested by:** "
            f"{message.from_user.mention}"
        )

        try:
            await mystic.delete()

            await message.reply_photo(
                thumb,
                caption=caption,
                reply_markup=stream_buttons(chat_id)
            )

        except Exception:
            await mystic.edit_text(
                caption
            )

        return

    # ─────────────── Start Playback ───────────────
    try:
        await start_stream(
            chat_id,
            track,
            video
        )

    except Exception as e:
        logger.exception(
            f"❌ Playback start failed: {e}"
        )

        return await mystic.edit_text(
            "❌ Playback start nahi hua.\n\n"
            "Voice chat active hai?\n"
            "Assistant admin hai?"
        )

    thumb = await get_thumb(
        data["videoid"],
        data["title"],
        data["duration"],
        data["views"],
        data["channel"],
        BOT_NAME
    )

    where = (
        "Channel"
        if target_chat_id
        else "Group"
    )

    caption = (
        f"**♡ Now Playing** ({where})\n\n"
        f"**Title:** "
        f"[{data['title']}]"
        f"(https://youtube.com/watch?v={data['videoid']})\n"
        f"**Duration:** `{data['duration']}`\n"
        f"**Views:** `{data['views']}`\n"
        f"**Channel:** `{data['channel']}`\n"
        f"**Requested by:** "
        f"{message.from_user.mention}"
    )

    try:
        await mystic.delete()

        await message.reply_photo(
            thumb,
            caption=caption,
            reply_markup=stream_buttons(chat_id)
        )

    except Exception:
        await mystic.edit_text(
            caption,
            reply_markup=stream_buttons(chat_id)
        )


# ─────────────── Slash Commands ───────────────
@bot.on_message(
    filters.command("start") & filters.private
)
async def start_cmd(_, m: Message):
    await m.reply_text(
        f"**♡ {BOT_NAME}**\n\n"
        "**Slash Commands:**\n"
        "`/play` `/vplay` `/cplay` `/cvplay`\n"
        "`/pause` `/resume` `/skip` `/stop` `/queue` `/now`\n"
        "`/channel` → channel link karo\n\n"
        f"**Bina / ke bhi:**\n"
        f"`play song` | `{TRIGGER} play song` | `cplay song`\n"
        f"`skip` `pause` `resume` `stop` `queue` `now`"
    )


# ─────────────── Channel Link ───────────────
@bot.on_message(
    filters.command(
        ["channel", "channelplay"]
    ) & filters.group
)
async def set_channel(_, m: Message):

    if not m.reply_to_message:
        return await m.reply_text(
            "Channel ka message reply karke `/channel` likho."
        )

    reply = m.reply_to_message

    channel = (
        reply.forward_from_chat
        or (
            reply.sender_chat
            if reply.sender_chat
            and reply.sender_chat.type.name == "CHANNEL"
            else None
        )
    )

    if not channel:
        return await m.reply_text(
            "Sirf channel ka message reply karo."
        )

    linked_channels[m.chat.id] = channel.id

    await m.reply_text(
        f"**♡ Channel Linked**\n\n"
        f"**{channel.title}**\n"
        f"Ab `/cplay song` se isme play hoga."
    )


# ─────────────── Play Commands ───────────────
@bot.on_message(
    filters.command(
        ["play", "vplay", "cplay", "cvplay"]
    ) & filters.group
)
async def play_cmd(_, m: Message):

    cmd = m.command[0].lower()

    video = cmd in [
        "vplay",
        "cvplay"
    ]

    is_channel = cmd in [
        "cplay",
        "cvplay"
    ]

    if len(m.command) < 2:
        return await m.reply_text(
            "Example: `/play song name` ya `/cplay song name`"
        )

    query = " ".join(
        m.command[1:]
    )

    target = None

    if is_channel:

        if m.chat.id not in linked_channels:
            return await m.reply_text(
                "Pehle `/channel` se channel link karo."
            )

        target = linked_channels[
            m.chat.id
        ]

    await handle_play(
        m,
        query,
        video,
        target
    )


# ─────────────── Pause ───────────────
@bot.on_message(
    filters.command("pause") & filters.group
)
async def pause_cmd(_, m: Message):
    try:
        await calls.pause(
            m.chat.id
        )

        await m.reply_text(
            "⏸ **Paused**",
            reply_markup=stream_buttons(
                m.chat.id
            )
        )

    except Exception as e:
        await m.reply_text(
            f"Error: `{e}`"
        )


# ─────────────── Resume ───────────────
@bot.on_message(
    filters.command("resume") & filters.group
)
async def resume_cmd(_, m: Message):
    try:
        await calls.resume(
            m.chat.id
        )

        await m.reply_text(
            "▶️ **Resumed**",
            reply_markup=stream_buttons(
                m.chat.id
            )
        )

    except Exception as e:
        await m.reply_text(
            f"Error: `{e}`"
        )


# ─────────────── Skip ───────────────
@bot.on_message(
    filters.command(
        ["skip", "next"]
    ) & filters.group
)
async def skip_cmd(_, m: Message):

    track = await play_next(
        m.chat.id
    )

    if track:

        thumb = await get_thumb(
            track["videoid"],
            track["title"],
            track["duration"],
            track["views"],
            track["channel"],
            BOT_NAME
        )

        caption = (
            f"**♡ Skipped → Now Playing**\n\n"
            f"**{track['title']}**\n"
            f"`{track['duration']}`\n"
            f"{track['requester']}"
        )

        await m.reply_photo(
            thumb,
            caption=caption,
            reply_markup=stream_buttons(
                m.chat.id
            )
        )

    else:
        await m.reply_text(
            "⏹ Queue empty."
        )


# ─────────────── Stop ───────────────
@bot.on_message(
    filters.command(
        ["stop", "end"]
    ) & filters.group
)
async def stop_cmd(_, m: Message):

    queues[m.chat.id].clear()

    current.pop(
        m.chat.id,
        None
    )

    try:
        await calls.leave_call(
            m.chat.id
        )
    except Exception:
        pass

    await m.reply_text(
        "⏹ **Stopped**"
    )


# ─────────────── Queue ───────────────
@bot.on_message(
    filters.command("queue") & filters.group
)
async def queue_cmd(_, m: Message):

    q = queues[m.chat.id]

    cur = current.get(
        m.chat.id
    )

    text = "**♡ Queue**\n\n"

    if cur:
        text += (
            f"**▶ Now:** "
            f"{cur['title']} "
            f"(`{cur['duration']}`)\n\n"
        )

    if not q:
        text += "_Empty_"

    else:
        for i, t in enumerate(
            q[:15],
            1
        ):
            text += (
                f"`{i}.` "
                f"{t['title'][:40]} "
                f"(`{t['duration']}`)\n"
            )

    await m.reply_text(
        text,
        reply_markup=queue_buttons(
            m.chat.id
        )
    )


# ─────────────── Now Playing ───────────────
@bot.on_message(
    filters.command(
        ["now", "np"]
    ) & filters.group
)
async def now_cmd(_, m: Message):

    cur = current.get(
        m.chat.id
    )

    if not cur:
        return await m.reply_text(
            "Kuch play nahi ho raha."
        )

    thumb = await get_thumb(
        cur["videoid"],
        cur["title"],
        cur["duration"],
        cur["views"],
        cur["channel"],
        BOT_NAME
    )

    caption = (
        f"**♡ Now Playing**\n\n"
        f"**{cur['title']}**\n"
        f"`{cur['duration']}`\n"
        f"{cur['requester']}"
    )

    await m.reply_photo(
        thumb,
        caption=caption,
        reply_markup=stream_buttons(
            m.chat.id
        )
    )


# ─────────────── Bina / + Normal + Babu system ───────────────
@bot.on_message(
    filters.group
    & filters.text
    & ~filters.command([
        "play",
        "vplay",
        "cplay",
        "cvplay",
        "pause",
        "resume",
        "skip",
        "next",
        "stop",
        "end",
        "queue",
        "now",
        "np",
        "start",
        "channel",
        "channelplay"
    ])
)
async def text_handler(_, m: Message):

    if not m.text:
        return

    text = m.text.strip()

    lower = text.lower()

    # Trigger: babu ...
    if lower.startswith(
        TRIGGER.lower() + " "
    ):

        remaining = text[
            len(TRIGGER):
        ].strip()

        if not remaining:
            return

        parts = remaining.split(
            None,
            1
        )

        cmd = parts[0].lower()

        arg = (
            parts[1]
            if len(parts) > 1
            else ""
        )

    else:

        first = (
            lower.split()[0]
            if lower.split()
            else ""
        )

        allowed = {
            "play",
            "p",
            "vplay",
            "vp",
            "video",
            "cplay",
            "cp",
            "cvplay",
            "cvp",
            "pause",
            "ruk",
            "resume",
            "chal",
            "continue",
            "skip",
            "next",
            "agl",
            "stop",
            "end",
            "band",
            "queue",
            "q",
            "list",
            "now",
            "np",
            "playing"
        }

        if first not in allowed:
            return

        parts = text.split(
            None,
            1
        )

        cmd = parts[0].lower()

        arg = (
            parts[1]
            if len(parts) > 1
            else ""
        )

    # ─────────────── Commands ───────────────

    if cmd in ["play", "p"]:

        if not arg:
            return await m.reply_text(
                "Example: `play song name`"
            )

        await handle_play(
            m,
            arg,
            False
        )

    elif cmd in [
        "vplay",
        "vp",
        "video"
    ]:

        if not arg:
            return await m.reply_text(
                "Example: `vplay song name`"
            )

        await handle_play(
            m,
            arg,
            True
        )

    elif cmd in [
        "cplay",
        "cp"
    ]:

        if not arg:
            return await m.reply_text(
                "Example: `cplay song name`"
            )

        if m.chat.id not in linked_channels:
            return await m.reply_text(
                "Pehle `/channel` se channel link karo."
            )

        await handle_play(
            m,
            arg,
            False,
            linked_channels[
                m.chat.id
            ]
        )

    elif cmd in [
        "cvplay",
        "cvp"
    ]:

        if not arg:
            return await m.reply_text(
                "Example: `cvplay song name`"
            )

        if m.chat.id not in linked_channels:
            return await m.reply_text(
                "Pehle `/channel` se channel link karo."
            )

        await handle_play(
            m,
            arg,
            True,
            linked_channels[
                m.chat.id
            ]
        )

    elif cmd in [
        "pause",
        "ruk"
    ]:

        try:
            await calls.pause(
                m.chat.id
            )

            await m.reply_text(
                "⏸ **Paused**",
                reply_markup=stream_buttons(
                    m.chat.id
                )
            )

        except Exception as e:
            await m.reply_text(
                f"Error: `{e}`"
            )

    elif cmd in [
        "resume",
        "chal",
        "continue"
    ]:

        try:
            await calls.resume(
                m.chat.id
            )

            await m.reply_text(
                "▶️ **Resumed**",
                reply_markup=stream_buttons(
                    m.chat.id
                )
            )

        except Exception as e:
            await m.reply_text(
                f"Error: `{e}`"
            )

    elif cmd in [
        "skip",
        "next",
        "agl"
    ]:

        track = await play_next(
            m.chat.id
        )

        if track:

            thumb = await get_thumb(
                track["videoid"],
                track["title"],
                track["duration"],
                track["views"],
                track["channel"],
                BOT_NAME
            )

            caption = (
                f"**♡ Skipped → Now Playing**\n\n"
                f"**{track['title']}**\n"
                f"`{track['duration']}`\n"
                f"{track['requester']}"
            )

            await m.reply_photo(
                thumb,
                caption=caption,
                reply_markup=stream_buttons(
                    m.chat.id
                )
            )

        else:
            await m.reply_text(
                "⏹ Queue empty."
            )

    elif cmd in [
        "stop",
        "end",
        "band"
    ]:

        queues[m.chat.id].clear()

        current.pop(
            m.chat.id,
            None
        )

        try:
            await calls.leave_call(
                m.chat.id
            )
        except Exception:
            pass

        await m.reply_text(
            "⏹ **Stopped**"
        )

    elif cmd in [
        "queue",
        "q",
        "list"
    ]:

        q = queues[m.chat.id]

        cur = current.get(
            m.chat.id
        )

        text = "**♡ Queue**\n\n"

        if cur:
            text += (
                f"**▶ Now:** "
                f"{cur['title']} "
                f"(`{cur['duration']}`)\n\n"
            )

        if not q:
            text += "_Empty_"

        else:
            for i, t in enumerate(
                q[:15],
                1
            ):
                text += (
                    f"`{i}.` "
                    f"{t['title'][:40]} "
                    f"(`{t['duration']}`)\n"
                )

        await m.reply_text(
            text,
            reply_markup=queue_buttons(
                m.chat.id
            )
        )

    elif cmd in [
        "now",
        "np",
        "playing"
    ]:

        cur = current.get(
            m.chat.id
        )

        if not cur:
            return await m.reply_text(
                "Kuch play nahi ho raha."
            )

        thumb = await get_thumb(
            cur["videoid"],
            cur["title"],
            cur["duration"],
            cur["views"],
            cur["channel"],
            BOT_NAME
        )

        caption = (
            f"**♡ Now Playing**\n\n"
            f"**{cur['title']}**\n"
            f"`{cur['duration']}`\n"
            f"{cur['requester']}"
        )

        await m.reply_photo(
            thumb,
            caption=caption,
            reply_markup=stream_buttons(
                m.chat.id
            )
        )


# ─────────────── Callbacks ───────────────
@bot.on_callback_query(
    filters.regex(r"^ctrl_")
)
async def callbacks(_, q: CallbackQuery):

    data = q.data

    chat_id = q.message.chat.id

    if data == "ctrl_close":

        try:
            await q.message.delete()

        except Exception:
            await q.message.edit_reply_markup(
                None
            )

        return await q.answer()

    action = data.split("|")[0]

    try:

        if action == "ctrl_pause":

            await calls.pause(
                chat_id
            )

            await q.answer(
                "⏸ Paused"
            )

        elif action == "ctrl_resume":

            await calls.resume(
                chat_id
            )

            await q.answer(
                "▶️ Resumed"
            )

        elif action == "ctrl_stop":

            queues[chat_id].clear()

            current.pop(
                chat_id,
                None
            )

            await calls.leave_call(
                chat_id
            )

            await q.message.edit_caption(
                "⏹ **Stopped**"
            )

            await q.answer(
                "Stopped"
            )

        elif action == "ctrl_skip":

            track = await play_next(
                chat_id
            )

            if track:

                thumb = await get_thumb(
                    track["videoid"],
                    track["title"],
                    track["duration"],
                    track["views"],
                    track["channel"],
                    BOT_NAME
                )

                caption = (
                    f"**♡ Now Playing**\n\n"
                    f"**{track['title']}**\n"
                    f"`{track['duration']}`\n"
                    f"{track['requester']}"
                )

                try:
                    await q.message.delete()

                except Exception:
                    pass

                await q.message.reply_photo(
                    thumb,
                    caption=caption,
                    reply_markup=stream_buttons(
                        chat_id
                    )
                )

                await q.answer(
                    "⏭ Skipped"
                )

            else:

                await q.message.edit_caption(
                    "⏹ Queue empty"
                )

                await q.answer(
                    "Empty"
                )

        elif action == "ctrl_replay":

            cur = current.get(
                chat_id
            )

            if cur:

                await start_stream(
                    chat_id,
                    cur,
                    cur.get("video", False)
                )

                await q.answer(
                    "↻ Replaying"
                )

            else:

                await q.answer(
                    "Kuch nahi chal raha",
                    show_alert=True
                )

        elif action == "ctrl_queue":

            qlist = queues[
                chat_id
            ]

            cur = current.get(
                chat_id
            )

            text = "**♡ Queue**\n\n"

            if cur:
                text += (
                    f"**▶** "
                    f"{cur['title']}\n\n"
                )

            if not qlist:

                text += "_Empty_"

            else:

                for i, t in enumerate(
                    qlist[:10],
                    1
                ):
                    text += (
                        f"`{i}.` "
                        f"{t['title'][:35]}\n"
                    )

            await q.answer()

            await q.message.reply_text(
                text,
                reply_markup=queue_buttons(
                    chat_id
                )
            )

    except Exception as e:

        logger.exception(
            "❌ Callback error"
        )

        await q.answer(
            str(e)[:80],
            show_alert=True
        )


# ─────────────── Main ───────────────
async def main():

    print("================================")
    print("STARTING V3 MUSIC BOT")
    print(
        "ASSISTANT SESSION LENGTH:",
        len(SESSION_STRING)
    )
    print(
        "YOUTUBE COOKIES:",
        "FOUND"
        if YOUTUBE_COOKIE_FILE.is_file()
        else "NOT FOUND"
    )
    print("================================")

    await assistant.start()

    print(
        "ASSISTANT STARTED SUCCESSFULLY"
    )

    await bot.start()

    print(
        "BOT STARTED SUCCESSFULLY"
    )

    await calls.start()

    print(
        "PYTG_CALLS STARTED SUCCESSFULLY"
    )

    logger.info(
        f"{BOT_NAME} started ♡"
    )

    await idle()


if __name__ == "__main__":

    try:
        asyncio.get_event_loop().run_until_complete(
            main()
        )

    except KeyboardInterrupt:
        pass

    finally:

        try:
            calls.stop()

        except Exception:
            pass

