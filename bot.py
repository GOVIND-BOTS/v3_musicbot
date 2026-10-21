import pyrogram.errors

if not hasattr(pyrogram.errors, "GroupcallForbidden"):
    class GroupcallForbidden(Exception):
        pass
    pyrogram.errors.GroupcallForbidden = GroupcallForbidden

import os
import asyncio
import logging
import threading
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
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("V3Music")


# ─────────────── Clients ───────────────
bot = Client("music_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
assistant = Client("vc_assistant", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
calls = PyTgCalls(assistant)


# ─────────────── Data ───────────────
queues = defaultdict(list)
current = {}
linked_channels = {}   # group_id → channel_id


# ─────────────── Helpers ───────────────
def get_stream_url(query: str, video: bool = False):
    search = query if query.startswith("http") else f"ytsearch1:{query}"
    ydl_opts = {
        "format": "best[height<=720][vcodec!=none][acodec!=none]/best" if video else "bestaudio/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search, download=False)

    if "entries" in info:
        info = next((e for e in info["entries"] if e), None)
    if not info or not info.get("url"):
        raise ValueError("Stream nahi mila")

    duration = info.get("duration_string") or (
        f"{info.get('duration', 0)//60:02d}:{info.get('duration', 0)%60:02d}" if info.get("duration") else "00:00"
    )
    views = str(info.get("view_count", "Unknown"))
    if views.isdigit():
        views = f"{int(views):,}"

    return {
        "url": info["url"],
        "title": info.get("title", "Unknown"),
        "videoid": info.get("id", ""),
        "duration": duration,
        "views": views,
        "channel": info.get("uploader") or info.get("channel") or "Unknown",
        "webpage_url": info.get("webpage_url", ""),
    }


async def start_stream(chat_id: int, track: dict, video: bool = False):
    if video:
        stream = MediaStream(track["url"], AudioQuality.HIGH, VideoQuality.HD_720p)
    else:
        stream = MediaStream(track["url"], AudioQuality.HIGH, video_flags=MediaStream.Flags.IGNORE)
    await calls.play(chat_id, stream)
    current[chat_id] = track


async def play_next(chat_id: int):
    if queues[chat_id]:
        track = queues[chat_id].pop(0)
        try:
            await start_stream(chat_id, track, track.get("video", False))
            return track
        except Exception as e:
            logger.exception(e)
            return await play_next(chat_id)
    current.pop(chat_id, None)
    try:
        await calls.leave_call(chat_id)
    except:
        pass
    return None


async def handle_play(message: Message, query: str, video: bool = False, target_chat_id: int = None):
    chat_id = target_chat_id or message.chat.id
    mystic = await message.reply_text("🔎 **Searching...**")

    try:
        data = get_stream_url(query, video)
    except Exception as e:
        logger.exception(e)
        return await mystic.edit_text("❌ Song nahi mil paya.")

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
            f"**Title:** [{data['title']}]({data.get('webpage_url','')})\n"
            f"**Duration:** `{data['duration']}`\n"
            f"**Position:** `{pos}`\n"
            f"**Requested by:** {message.from_user.mention}"
        )
        try:
            await mystic.delete()
            await message.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(chat_id))
        except:
            await mystic.edit_text(caption)
        return

    try:
        await start_stream(chat_id, track, video)
    except Exception as e:
        logger.exception(e)
        return await mystic.edit_text("❌ Playback start nahi hua.\nVoice chat active hai? Assistant admin hai?")

    thumb = await get_thumb(data["videoid"], data["title"], data["duration"], data["views"], data["channel"], BOT_NAME)
    where = "Channel" if target_chat_id else "Group"
    caption = (
        f"**♡ Now Playing** ({where})\n\n"
        f"**Title:** [{data['title']}](https://youtube.com/watch?v={data['videoid']})\n"
        f"**Duration:** `{data['duration']}`\n"
        f"**Views:** `{data['views']}`\n"
        f"**Channel:** `{data['channel']}`\n"
        f"**Requested by:** {message.from_user.mention}"
    )
    try:
        await mystic.delete()
        await message.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(chat_id))
    except:
        await mystic.edit_text(caption, reply_markup=stream_buttons(chat_id))


# ─────────────── Slash Commands ───────────────
@bot.on_message(filters.command("start") & filters.private)
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


@bot.on_message(filters.command(["channel", "channelplay"]) & filters.group)
async def set_channel(_, m: Message):
    if not m.reply_to_message:
        return await m.reply_text("Channel ka message reply karke `/channel` likho.")
    reply = m.reply_to_message
    channel = reply.forward_from_chat or (reply.sender_chat if reply.sender_chat and reply.sender_chat.type.name == "CHANNEL" else None)
    if not channel:
        return await m.reply_text("Sirf channel ka message reply karo.")
    linked_channels[m.chat.id] = channel.id
    await m.reply_text(f"**♡ Channel Linked**\n\n**{channel.title}**\nAb `/cplay song` se isme play hoga.")


@bot.on_message(filters.command(["play", "vplay", "cplay", "cvplay"]) & filters.group)
async def play_cmd(_, m: Message):
    cmd = m.command[0].lower()
    video = cmd in ["vplay", "cvplay"]
    is_channel = cmd in ["cplay", "cvplay"]

    if len(m.command) < 2:
        return await m.reply_text("Example: `/play song name` ya `/cplay song name`")

    query = " ".join(m.command[1:])
    target = None
    if is_channel:
        if m.chat.id not in linked_channels:
            return await m.reply_text("Pehle `/channel` se channel link karo.")
        target = linked_channels[m.chat.id]

    await handle_play(m, query, video, target)


@bot.on_message(filters.command("pause") & filters.group)
async def pause_cmd(_, m: Message):
    try:
        await calls.pause(m.chat.id)
        await m.reply_text("⏸ **Paused**", reply_markup=stream_buttons(m.chat.id))
    except Exception as e:
        await m.reply_text(f"Error: `{e}`")


@bot.on_message(filters.command("resume") & filters.group)
async def resume_cmd(_, m: Message):
    try:
        await calls.resume(m.chat.id)
        await m.reply_text("▶️ **Resumed**", reply_markup=stream_buttons(m.chat.id))
    except Exception as e:
        await m.reply_text(f"Error: `{e}`")


@bot.on_message(filters.command(["skip", "next"]) & filters.group)
async def skip_cmd(_, m: Message):
    track = await play_next(m.chat.id)
    if track:
        thumb = await get_thumb(track["videoid"], track["title"], track["duration"], track["views"], track["channel"], BOT_NAME)
        caption = f"**♡ Skipped → Now Playing**\n\n**{track['title']}**\n`{track['duration']}`\n{track['requester']}"
        await m.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(m.chat.id))
    else:
        await m.reply_text("⏹ Queue empty.")


@bot.on_message(filters.command(["stop", "end"]) & filters.group)
async def stop_cmd(_, m: Message):
    queues[m.chat.id].clear()
    current.pop(m.chat.id, None)
    try:
        await calls.leave_call(m.chat.id)
    except:
        pass
    await m.reply_text("⏹ **Stopped**")


@bot.on_message(filters.command("queue") & filters.group)
async def queue_cmd(_, m: Message):
    q = queues[m.chat.id]
    cur = current.get(m.chat.id)
    text = f"**♡ Queue**\n\n"
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
    cur = current.get(m.chat.id)
    if not cur:
        return await m.reply_text("Kuch play nahi ho raha.")
    thumb = await get_thumb(cur["videoid"], cur["title"], cur["duration"], cur["views"], cur["channel"], BOT_NAME)
    caption = f"**♡ Now Playing**\n\n**{cur['title']}**\n`{cur['duration']}`\n{cur['requester']}"
    await m.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(m.chat.id))


# ─────────────── Bina / + Normal + Babu system ───────────────
@bot.on_message(filters.group & filters.text & ~filters.command([
    "play", "vplay", "cplay", "cvplay", "pause", "resume", "skip", "next",
    "stop", "end", "queue", "now", "np", "start", "channel", "channelplay"
]))
async def text_handler(_, m: Message):
    if not m.text:
        return

    text = m.text.strip()
    lower = text.lower()

    # Trigger (babu ...)
    if lower.startswith(TRIGGER.lower() + " "):
        remaining = text[len(TRIGGER):].strip()
        if not remaining:
            return
        parts = remaining.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
    else:
        # Pure normal (play / skip / pause ...)
        first = lower.split()[0] if lower.split() else ""
        allowed = {
            "play", "p", "vplay", "vp", "video", "cplay", "cp", "cvplay", "cvp",
            "pause", "ruk", "resume", "chal", "continue",
            "skip", "next", "agl", "stop", "end", "band",
            "queue", "q", "list", "now", "np", "playing"
        }
        if first not in allowed:
            return
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

    # Handle commands
    if cmd in ["play", "p"]:
        if not arg:
            return await m.reply_text(f"Example: `play song name`")
        await handle_play(m, arg, False)

    elif cmd in ["vplay", "vp", "video"]:
        if not arg:
            return await m.reply_text("Example: `vplay song name`")
        await handle_play(m, arg, True)

    elif cmd in ["cplay", "cp"]:
        if not arg:
            return await m.reply_text("Example: `cplay song name`")
        if m.chat.id not in linked_channels:
            return await m.reply_text("Pehle `/channel` se channel link karo.")
        await handle_play(m, arg, False, linked_channels[m.chat.id])

    elif cmd in ["cvplay", "cvp"]:
        if not arg:
            return await m.reply_text("Example: `cvplay song name`")
        if m.chat.id not in linked_channels:
            return await m.reply_text("Pehle `/channel` se channel link karo.")
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
            await m.reply_text("⏹ Queue empty.")

    elif cmd in ["stop", "end", "band"]:
        queues[m.chat.id].clear()
        current.pop(m.chat.id, None)
        try:
            await calls.leave_call(m.chat.id)
        except:
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
            return await m.reply_text("Kuch play nahi ho raha.")
        thumb = await get_thumb(cur["videoid"], cur["title"], cur["duration"], cur["views"], cur["channel"], BOT_NAME)
        caption = f"**♡ Now Playing**\n\n**{cur['title']}**\n`{cur['duration']}`\n{cur['requester']}"
        await m.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(m.chat.id))


# ─────────────── Callbacks ───────────────
@bot.on_callback_query(filters.regex(r"^ctrl_"))
async def callbacks(_, q: CallbackQuery):
    data = q.data
    chat_id = q.message.chat.id

    if data == "ctrl_close":
        try:
            await q.message.delete()
        except:
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
                except:
                    pass
                await q.message.reply_photo(thumb, caption=caption, reply_markup=stream_buttons(chat_id))
                await q.answer("⏭ Skipped")
            else:
                await q.message.edit_caption("⏹ Queue empty")
                await q.answer("Empty")
        elif action == "ctrl_replay":
            cur = current.get(chat_id)
            if cur:
                await start_stream(chat_id, cur, cur.get("video", False))
                await q.answer("↻ Replaying")
            else:
                await q.answer("Kuch nahi chal raha", show_alert=True)
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
        logger.exception(e)
        await q.answer(str(e)[:80], show_alert=True)


# ─────────────── Main ───────────────
async def main():
    await assistant.start()
    await bot.start()
    await calls.start()
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
        except:
            pass
