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

# StreamEnded import (version-safe)
try:
    from pytgcalls.types import StreamEnded
except ImportError:
    try:
        from pytgcalls.types.stream import StreamEnded
    except ImportError:
        StreamEnded = None

from config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    SESSION_STRING,
    BOT_NAME,
    TRIGGER,
    OWNER_ID,
    SUPPORT_CHAT,
)
from buttons import stream_buttons, queue_buttons, start_buttons, help_buttons
from thumbnails import get_thumb


# ─────────────── Health Check ───────────────
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
YOUTUBE_COOKIE_FILE = BASE_DIR / "cookies" / "cookies.txt"

if YOUTUBE_COOKIE_FILE.is_file():
    logger.info(f"🍪 YouTube cookies found: {YOUTUBE_COOKIE_FILE}")
else:
    logger.warning("🍪 cookies.txt not found. YouTube will run without cookies.")


# ─────────────── Clients ───────────────
bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

SESSION_STRING = SESSION_STRING.strip()
if not SESSION_STRING:
    raise ValueError("SESSION_STRING is empty. Please provide a valid Pyrogram session string.")

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
ASSISTANT_ID = None


# ─────────────── YouTube Stream Helper ───────────────
def get_stream_url(query: str, video: bool = False):
    """
    Extract YouTube metadata.
    IMPORTANT: We return the webpage_url (watch?v=...) instead of the
    direct googlevideo stream URL, because direct URLs expire very fast.
    PyTgCalls will re-extract a fresh stream when playing.
    """
    search = query if query.startswith("http") else f"ytsearch1:{query}"

    if video:
        stream_format = "best[height<=720]/best"
    else:
        stream_format = "bestaudio/best"

    ydl_opts = {
        "format": stream_format,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "skip_download": True,
        "nocheckcertificate": True,
        "socket_timeout": 30,
        "force_ipv4": True,
        "prefer_free_formats": True,
        "extractor_args": {
            "youtube": {
                # android often works best on VPS / datacenter IPs
                "player_client": ["android", "ios", "web"],
            }
        },
    }

    if YOUTUBE_COOKIE_FILE.is_file():
        ydl_opts["cookiefile"] = str(YOUTUBE_COOKIE_FILE)
        logger.info("🍪 yt-dlp is using cookies.txt")
    else:
        logger.warning("⚠️ yt-dlp is running without cookies.txt")

    logger.info(f"🎵 YouTube extraction started | query={query!r} | video={video}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search, download=False)
    except Exception as e:
        logger.exception("❌ yt-dlp extraction failed")
        raise RuntimeError(f"YouTube extraction failed: {e}") from e

    if not info:
        raise ValueError("Could not get information from YouTube.")

    if "entries" in info:
        entries = info.get("entries") or []
        info = next((entry for entry in entries if entry), None)

    if not info:
        raise ValueError("Song not found.")

    video_id = info.get("id") or ""
    webpage_url = info.get("webpage_url") or (
        f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
    )

    if not webpage_url:
        raise ValueError("Could not get YouTube URL.")

    duration_seconds = info.get("duration")
    if duration_seconds:
        duration = info.get("duration_string")
        if not duration:
            duration = f"{int(duration_seconds) // 60:02d}:{int(duration_seconds) % 60:02d}"
    else:
        duration = "00:00"

    views = str(info.get("view_count", "Unknown"))
    if views.isdigit():
        views = f"{int(views):,}"

    title = info.get("title") or "Unknown"
    channel = info.get("uploader") or info.get("channel") or "Unknown"

    logger.info(f"✅ YouTube info extracted | title={title!r} | id={video_id} | duration={duration}")

    return {
        # CRITICAL FIX: use webpage_url, NOT the direct stream url
        "url": webpage_url,
        "title": title,
        "videoid": video_id,
        "duration": duration,
        "views": views,
        "channel": channel,
        "webpage_url": webpage_url,
    }


# ─────────────── Ensure Assistant ───────────────
async def ensure_assistant(chat_id: int, message: Message = None):
    global ASSISTANT_ID

    if ASSISTANT_ID is None:
        try:
            me = await assistant.get_me()
            ASSISTANT_ID = me.id
        except Exception as e:
            logger.error(f"Could not get assistant ID: {e}")
            return False

    try:
        member = await bot.get_chat_member(chat_id, ASSISTANT_ID)
        if member.status in ("member", "administrator", "creator", "owner"):
            return True
    except Exception:
        pass

    try:
        await bot.add_chat_members(chat_id, ASSISTANT_ID)
        logger.info(f"✅ Assistant added to chat {chat_id}")
        if message:
            try:
                await message.reply_text("👤 **Assistant** has been added to the group.\nStarting playback...")
            except Exception:
                pass
        await asyncio.sleep(1)
        return True
    except Exception as e:
        err = str(e).lower()
        logger.warning(f"Could not auto-add assistant: {e}")
        if message:
            try:
                if "banned" in err or "user_banned" in err:
                    await message.reply_text(
                        f"🚫 **Assistant is banned** in this group.\n\n"
                        f"Please unban the assistant and try again.\n`Assistant ID: {ASSISTANT_ID}`"
                    )
                else:
                    await message.reply_text(
                        f"❌ **Assistant is not in this group.**\n\n"
                        f"Please add the assistant manually and make it admin.\n`Assistant ID: {ASSISTANT_ID}`"
                    )
            except Exception:
                pass
        return False


# ─────────────── Start Stream ───────────────
async def start_stream(chat_id: int, track: dict, video: bool = False):
    try:
        logger.info(f"🎧 Starting stream | chat={chat_id} | title={track.get('title')} | video={video}")

        # Use YouTube page URL — PyTgCalls will fetch a fresh stream via yt-dlp
        media_url = track["url"]

        if video:
            stream = MediaStream(
                media_url,
                AudioQuality.HIGH,
                VideoQuality.HD_720p,
            )
        else:
            stream = MediaStream(
                media_url,
                AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
            )

        await calls.play(chat_id, stream)
        current[chat_id] = track
        logger.info(f"✅ PyTgCalls stream started | chat={chat_id}")
    except Exception:
        logger.exception(f"❌ PyTgCalls playback failed | chat={chat_id}")
        raise


# ─────────────── Play Next ───────────────
async def play_next(chat_id: int):
    if queues[chat_id]:
        track = queues[chat_id].pop(0)
        try:
            await start_stream(chat_id, track, track.get("video", False))
            return track
        except Exception as e:
            logger.exception(f"❌ Queue playback failed: {e}")
            return await play_next(chat_id)

    current.pop(chat_id, None)
    try:
        await calls.leave_call(chat_id)
    except Exception:
        pass
    return None


# ─────────────── Handle Play ───────────────
async def handle_play(message: Message, query: str, video: bool = False, target_chat_id: int = None):
    chat_id = target_chat_id or message.chat.id
    mystic = await message.reply_text("🔎 **Searching on YouTube...**")

    try:
        data = get_stream_url(query, video)
    except Exception as e:
        logger.exception(f"❌ Song extraction failed: {e}")
        return await mystic.edit_text(
            "❌ **Song not found.**\n\nUnable to extract from YouTube.\nPlease try another song or check cookies."
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

    if chat_id in current and current[chat_id]:
        queues[chat_id].append(track)
        pos = len(queues[chat_id])
        thumb = await get_thumb(data["videoid"], data["title"], data["duration"], data["views"], data["channel"], BOT_NAME)
        caption = (
            f"**♡ Added to Queue**\n\n"
            f"**Title:** [{data['title']}]({data.get('webpage_url', '')})\n"
            f"**Duration:** `{data['duration']}`\n"
            f"**Position:** `{pos}`\n"
            f"**Requested by:** {message.from_user.mention}"
        )
        try:
            await mystic.delete()
            await message.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(chat_id))
        except Exception:
            await mystic.edit_text(caption)
        return

    ready = await ensure_assistant(chat_id, message)
    if not ready:
        return await mystic.edit_text("❌ **Assistant is missing.**\n\nPlease add the assistant to this group and try again.")

    try:
        await start_stream(chat_id, track, video)
    except Exception as e:
        logger.exception(f"❌ Playback start failed: {e}")
        return await mystic.edit_text(
            "❌ **Playback failed.**\n\n"
            "• Is the **Voice Chat** active?\n"
            "• Is the **Assistant** an admin?\n"
            f"• Error: `{str(e)[:120]}`"
        )

    thumb = await get_thumb(data["videoid"], data["title"], data["duration"], data["views"], data["channel"], BOT_NAME)
    where = "Channel" if target_chat_id else "Group"
    caption = (
        f"**♡ Now Playing** ‹ {where} ›\n\n"
        f"**Title:** [{data['title']}](https://youtube.com/watch?v={data['videoid']})\n"
        f"**Duration:** `{data['duration']}`\n"
        f"**Views:** `{data['views']}`\n"
        f"**Channel:** `{data['channel']}`\n"
        f"**Requested by:** {message.from_user.mention}"
    )
    try:
        await mystic.delete()
        await message.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(chat_id))
    except Exception:
        await mystic.edit_text(caption, reply_markup=stream_buttons(chat_id))


# ─────────────── Helper ───────────────
async def delete_cmd(m: Message):
    try:
        await m.delete()
    except Exception:
        pass


# ─────────────── Start Command (Group + Private) ───────────────
@bot.on_message(filters.command("start"))
async def start_cmd(_, m: Message):
    me = await bot.get_me()
    bot_username = me.username or "musicbot"

    caption = (
        f"**♡ Welcome to {BOT_NAME}**\n\n"
        f"Hey {m.from_user.mention},\n"
        f"I'm a high-quality **Telegram Music Bot**.\n"
        f"I can play songs & videos in voice chats.\n\n"
        f"**Commands**\n"
        f"`/play` `/vplay` `/pause` `/resume` `/skip` `/stop`\n"
        f"`/queue` `/now` `/channel`\n\n"
        f"**Without Slash**\n"
        f"`play song name`\n"
        f"`{TRIGGER} play song name`\n\n"
        f"Add me to your group and enjoy!"
    )

    start_img = BASE_DIR / "assets" / "start.jpg"
    if not start_img.is_file():
        start_img = BASE_DIR / "assets" / "start.png"

    markup = start_buttons(OWNER_ID, SUPPORT_CHAT, bot_username)

    try:
        if start_img.is_file():
            await m.reply_photo(str(start_img), caption=caption, reply_markup=markup)
        else:
            await m.reply_text(caption, reply_markup=markup)
    except Exception:
        await m.reply_text(caption, reply_markup=markup)


# ─────────────── Channel Link ───────────────
@bot.on_message(filters.command(["channel", "channelplay"]) & filters.group)
async def set_channel(_, m: Message):
    await delete_cmd(m)
    if not m.reply_to_message:
        return await m.reply_text("Reply to a **channel message** with `/channel`.")

    reply = m.reply_to_message
    channel = (
        reply.forward_from_chat
        or (reply.sender_chat if reply.sender_chat and reply.sender_chat.type.name == "CHANNEL" else None)
    )
    if not channel:
        return await m.reply_text("Please reply to a message from a **channel** only.")

    linked_channels[m.chat.id] = channel.id
    await m.reply_text(f"**♡ Channel Linked**\n\n**{channel.title}**\nNow use `/cplay song` to play in this channel.")


# ─────────────── Play Commands ───────────────
@bot.on_message(filters.command(["play", "vplay", "cplay", "cvplay"]) & filters.group)
async def play_cmd(_, m: Message):
    await delete_cmd(m)
    cmd = m.command[0].lower()
    video = cmd in ["vplay", "cvplay"]
    is_channel = cmd in ["cplay", "cvplay"]

    if len(m.command) < 2:
        return await m.reply_text("Example: `/play song name`")

    query = " ".join(m.command[1:])
    target = None
    if is_channel:
        if m.chat.id not in linked_channels:
            return await m.reply_text("Please link a channel first using `/channel`.")
        target = linked_channels[m.chat.id]

    await handle_play(m, query, video, target)


@bot.on_message(filters.command("pause") & filters.group)
async def pause_cmd(_, m: Message):
    await delete_cmd(m)
    try:
        await calls.pause(m.chat.id)
        await m.reply_text("⏸ **Paused**", reply_markup=stream_buttons(m.chat.id))
    except Exception as e:
        await m.reply_text(f"Error: `{e}`")


@bot.on_message(filters.command("resume") & filters.group)
async def resume_cmd(_, m: Message):
    await delete_cmd(m)
    try:
        await calls.resume(m.chat.id)
        await m.reply_text("▶️ **Resumed**", reply_markup=stream_buttons(m.chat.id))
    except Exception as e:
        await m.reply_text(f"Error: `{e}`")


@bot.on_message(filters.command(["skip", "next"]) & filters.group)
async def skip_cmd(_, m: Message):
    await delete_cmd(m)
    track = await play_next(m.chat.id)
    if track:
        thumb = await get_thumb(track["videoid"], track["title"], track["duration"], track["views"], track["channel"], BOT_NAME)
        caption = f"**♡ Skipped → Now Playing**\n\n**{track['title']}**\n`{track['duration']}`\n{track['requester']}"
        await m.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(m.chat.id))
    else:
        await m.reply_text("⏹ Queue is empty.")


@bot.on_message(filters.command(["stop", "end"]) & filters.group)
async def stop_cmd(_, m: Message):
    await delete_cmd(m)
    queues[m.chat.id].clear()
    current.pop(m.chat.id, None)
    try:
        await calls.leave_call(m.chat.id)
    except Exception:
        pass
    await m.reply_text("⏹ **Stopped**")


@bot.on_message(filters.command("queue") & filters.group)
async def queue_cmd(_, m: Message):
    await delete_cmd(m)
    q = queues[m.chat.id]
    cur = current.get(m.chat.id)
    text = "**♡ Queue**\n\n"
    if cur:
        text += f"**▶ Now:** {cur['title']} (`{cur['duration']}`)\n\n"
    if not q:
        text += "_Empty_"
    else:
        for i, t in enumerate(q[:15], 1):
            text += f"`{i}.` {t['title'][:40]} (`{t['duration']}`)\n"
    await m.reply_text(text, reply_markup=queue_buttons(m.chat.id))


@bot.on_message(filters.command(["now", "np"]) & filters.group)
async def now_cmd(_, m: Message):
    await delete_cmd(m)
    cur = current.get(m.chat.id)
    if not cur:
        return await m.reply_text("Nothing is playing right now.")
    thumb = await get_thumb(cur["videoid"], cur["title"], cur["duration"], cur["views"], cur["channel"], BOT_NAME)
    caption = f"**♡ Now Playing**\n\n**{cur['title']}**\n`{cur['duration']}`\n{cur['requester']}"
    await m.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(m.chat.id))


# ─────────────── Text Commands ───────────────
@bot.on_message(
    filters.group & filters.text & ~filters.command([
        "play", "vplay", "cplay", "cvplay", "pause", "resume",
        "skip", "next", "stop", "end", "queue", "now", "np",
        "start", "channel", "channelplay"
    ])
)
async def text_handler(_, m: Message):
    if not m.text:
        return

    text = m.text.strip()
    lower = text.lower()

    if lower.startswith(TRIGGER.lower() + " "):
        remaining = text[len(TRIGGER):].strip()
        if not remaining:
            return
        parts = remaining.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
    else:
        first = lower.split()[0] if lower.split() else ""
        allowed = {
            "play", "p", "vplay", "vp", "video", "cplay", "cp", "cvplay", "cvp",
            "pause", "ruk", "resume", "chal", "continue", "skip", "next", "agl",
            "stop", "end", "band", "queue", "q", "list", "now", "np", "playing"
        }
        if first not in allowed:
            return
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

    await delete_cmd(m)

    if cmd in ["play", "p"]:
        if not arg:
            return await m.reply_text("Example: `play song name`")
        await handle_play(m, arg, False)
    elif cmd in ["vplay", "vp", "video"]:
        if not arg:
            return await m.reply_text("Example: `vplay song name`")
        await handle_play(m, arg, True)
    elif cmd in ["cplay", "cp"]:
        if not arg:
            return await m.reply_text("Example: `cplay song name`")
        if m.chat.id not in linked_channels:
            return await m.reply_text("Please link a channel first using `/channel`.")
        await handle_play(m, arg, False, linked_channels[m.chat.id])
    elif cmd in ["cvplay", "cvp"]:
        if not arg:
            return await m.reply_text("Example: `cvplay song name`")
        if m.chat.id not in linked_channels:
            return await m.reply_text("Please link a channel first using `/channel`.")
        await handle_play(m, arg, True, linked_channels[m.chat.id])
    elif cmd in ["pause", "ruk"]:
        try:
            await calls.pause(m.chat.id)
            await m.reply_text("⏸ **Paused**", reply_markup=stream_buttons(m.chat.id))
        except Exception as e:
            await m.reply_text(f"Error: `{e}`")
    elif cmd in ["resume", "chal", "continue"]:
        try:
            await calls.resume(m.chat.id)
            await m.reply_text("▶️ **Resumed**", reply_markup=stream_buttons(m.chat.id))
        except Exception as e:
            await m.reply_text(f"Error: `{e}`")
    elif cmd in ["skip", "next", "agl"]:
        track = await play_next(m.chat.id)
        if track:
            thumb = await get_thumb(track["videoid"], track["title"], track["duration"], track["views"], track["channel"], BOT_NAME)
            caption = f"**♡ Skipped → Now Playing**\n\n**{track['title']}**\n`{track['duration']}`\n{track['requester']}"
            await m.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(m.chat.id))
        else:
            await m.reply_text("⏹ Queue is empty.")
    elif cmd in ["stop", "end", "band"]:
        queues[m.chat.id].clear()
        current.pop(m.chat.id, None)
        try:
            await calls.leave_call(m.chat.id)
        except Exception:
            pass
        await m.reply_text("⏹ **Stopped**")
    elif cmd in ["queue", "q", "list"]:
        q = queues[m.chat.id]
        cur = current.get(m.chat.id)
        text = "**♡ Queue**\n\n"
        if cur:
            text += f"**▶ Now:** {cur['title']} (`{cur['duration']}`)\n\n"
        if not q:
            text += "_Empty_"
        else:
            for i, t in enumerate(q[:15], 1):
                text += f"`{i}.` {t['title'][:40]} (`{t['duration']}`)\n"
        await m.reply_text(text, reply_markup=queue_buttons(m.chat.id))
    elif cmd in ["now", "np", "playing"]:
        cur = current.get(m.chat.id)
        if not cur:
            return await m.reply_text("Nothing is playing right now.")
        thumb = await get_thumb(cur["videoid"], cur["title"], cur["duration"], cur["views"], cur["channel"], BOT_NAME)
        caption = f"**♡ Now Playing**\n\n**{cur['title']}**\n`{cur['duration']}`\n{cur['requester']}"
        await m.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(m.chat.id))


# ─────────────── Callbacks ───────────────
@bot.on_callback_query(filters.regex(r"^(help_cmd|start_home)$"))
async def help_home_cb(_, q: CallbackQuery):
    data = q.data
    if data == "help_cmd":
        text = (
            f"**♡ {BOT_NAME} — Help**\n\n"
            f"**Play Commands**\n"
            f"`/play` or `play` — Play audio\n"
            f"`/vplay` or `vplay` — Play video\n"
            f"`/cplay` — Play in linked channel\n"
            f"`/cvplay` — Video in linked channel\n\n"
            f"**Controls**\n"
            f"`/pause` · `/resume` · `/skip` · `/stop`\n"
            f"`/queue` · `/now`\n\n"
            f"**Other**\n"
            f"`/channel` — Link a channel\n"
            f"`{TRIGGER} play song` — Trigger play"
        )
        await q.message.edit_text(text, reply_markup=help_buttons())
        return await q.answer()

    if data == "start_home":
        me = await bot.get_me()
        bot_username = me.username or "musicbot"
        caption = (
            f"**♡ Welcome to {BOT_NAME}**\n\n"
            f"Hey {q.from_user.mention},\n"
            f"I'm a high-quality **Telegram Music Bot**.\n"
            f"I can play songs & videos in voice chats.\n\n"
            f"Add me to your group and enjoy!"
        )
        await q.message.edit_text(caption, reply_markup=start_buttons(OWNER_ID, SUPPORT_CHAT, bot_username))
        return await q.answer()


@bot.on_callback_query(filters.regex(r"^ctrl_"))
async def callbacks(_, q: CallbackQuery):
    data = q.data
    chat_id = q.message.chat.id

    if data == "ctrl_close":
        try:
            await q.message.delete()
        except Exception:
            await q.message.edit_reply_markup(None)
        return await q.answer()

    action = data.split("|")[0]
    try:
        if action == "ctrl_pause":
            await calls.pause(chat_id)
            await q.answer("⏸ Paused")
        elif action == "ctrl_resume":
            await calls.resume(chat_id)
            await q.answer("▶️ Resumed")
        elif action == "ctrl_stop":
            queues[chat_id].clear()
            current.pop(chat_id, None)
            await calls.leave_call(chat_id)
            await q.message.edit_caption("⏹ **Stopped**")
            await q.answer("Stopped")
        elif action == "ctrl_skip":
            track = await play_next(chat_id)
            if track:
                thumb = await get_thumb(track["videoid"], track["title"], track["duration"], track["views"], track["channel"], BOT_NAME)
                caption = f"**♡ Now Playing**\n\n**{track['title']}**\n`{track['duration']}`\n{track['requester']}"
                try:
                    await q.message.delete()
                except Exception:
                    pass
                await q.message.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(chat_id))
                await q.answer("⏭ Skipped")
            else:
                await q.message.edit_caption("⏹ Queue is empty")
                await q.answer("Empty")
        elif action == "ctrl_replay":
            cur = current.get(chat_id)
            if cur:
                await start_stream(chat_id, cur, cur.get("video", False))
                await q.answer("↻ Replaying")
            else:
                await q.answer("Nothing is playing", show_alert=True)
        elif action == "ctrl_queue":
            qlist = queues[chat_id]
            cur = current.get(chat_id)
            text = "**♡ Queue**\n\n"
            if cur:
                text += f"**▶** {cur['title']}\n\n"
            if not qlist:
                text += "_Empty_"
            else:
                for i, t in enumerate(qlist[:10], 1):
                    text += f"`{i}.` {t['title'][:35]}\n"
            await q.answer()
            await q.message.reply_text(text, reply_markup=queue_buttons(chat_id))
    except Exception as e:
        logger.exception("❌ Callback error")
        await q.answer(str(e)[:80], show_alert=True)


# ─────────────── Stream End Handler (auto next) ───────────────
@calls.on_update()
async def on_stream_end(_, update):
    """When a track finishes, automatically play the next one in queue."""
    try:
        if StreamEnded is not None and isinstance(update, StreamEnded):
            chat_id = update.chat_id
            logger.info(f"⏹ Stream ended | chat={chat_id} → playing next")
            track = await play_next(chat_id)
            if track:
                logger.info(f"▶ Auto-playing next: {track.get('title')}")
            else:
                logger.info(f"Queue empty for chat {chat_id}")
    except Exception:
        logger.exception("❌ Error in stream end handler")


# ─────────────── Main ───────────────
async def main():
    print("================================")
    print("STARTING V3 MUSIC BOT")
    print("ASSISTANT SESSION LENGTH:", len(SESSION_STRING))
    print("YOUTUBE COOKIES:", "FOUND" if YOUTUBE_COOKIE_FILE.is_file() else "NOT FOUND")
    print("================================")

    await assistant.start()
    global ASSISTANT_ID
    try:
        me = await assistant.get_me()
        ASSISTANT_ID = me.id
        print(f"ASSISTANT ID: {ASSISTANT_ID}")
        print(f"ASSISTANT USERNAME: @{me.username}" if me.username else "ASSISTANT USERNAME: None")
    except Exception as e:
        print(f"Could not get assistant info: {e}")

    print("ASSISTANT STARTED SUCCESSFULLY")
    await bot.start()
    print("BOT STARTED SUCCESSFULLY")
    await calls.start()
    print("PYTG_CALLS STARTED SUCCESSFULLY")
    logger.info(f"{BOT_NAME} started ♡")
    await idle()


if __name__ == "__main__":
    try:
        asyncio.get_event_loop().run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            calls.stop()
        except Exception:
            pass
