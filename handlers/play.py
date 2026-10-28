import logging
import time
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from buttons import stream_buttons
from config import BOT_NAME
from thumbnails import get_thumb
from youtube import is_youtube_url, search_youtube, get_video_info, get_stream_url

LOGGER = logging.getLogger(__name__)
PENDING_TRACKS = {}
PENDING_TTL = 900

def _clean_pending():
    now = time.time()
    for key, value in list(PENDING_TRACKS.items()):
        if now - value["time"] > PENDING_TTL:
            PENDING_TRACKS.pop(key, None)

def register_play_handlers(app, stream):
    async def handle_play(client, message, force_video=False):
        if len(message.command) < 2:
            await message.reply_text("Usage: `/play song name` or `/play YouTube link`")
            return
        query_text = " ".join(message.command[1:]).strip()
        status = await message.reply_text("🔎 Searching YouTube...")
        try:
            if is_youtube_url(query_text):
                results = [await get_video_info(query_text)]
            else:
                results = await search_youtube(query_text, limit=5)
            results = [x for x in results if x and x.get("webpage_url")]
            if not results:
                await status.edit_text("No results found. Try another title.")
                return
            _clean_pending()
            key = f"{message.chat.id}:{message.from_user.id if message.from_user else 0}:{int(time.time()*1000)}"
            PENDING_TRACKS[key] = {"items": results, "chat_id": message.chat.id, "time": time.time(), "force_video": force_video}
            if len(results) == 1:
                track = results[0]
                await status.edit_text(
                    f"**{track['title']}**\nDuration: {track.get('duration_text','?')}\nChoose playback type:",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("🎧 Audio", callback_data=f"choose_media|audio|{key}"),
                        InlineKeyboardButton("🎬 Video", callback_data=f"choose_media|video|{key}"),
                    ]])
                )
            else:
                rows = []
                for i, item in enumerate(results):
                    label = f"{i+1}. {item['title'][:45]}"
                    rows.append([InlineKeyboardButton(label, callback_data=f"select_track|{key}|{i}")])
                rows.append([InlineKeyboardButton("✖ Close", callback_data="ctrl_close")])
                await status.edit_text("**Choose a track:**", reply_markup=InlineKeyboardMarkup(rows))
        except Exception as exc:
            LOGGER.exception("YouTube search failed")
            await status.edit_text(f"Could not search/play this track: `{type(exc).__name__}`")

    @app.on_message(filters.command("play") & filters.group)
    async def play_command(client, message):
        await handle_play(client, message, False)

    @app.on_message(filters.command("vplay") & filters.group)
    async def vplay_command(client, message):
        await handle_play(client, message, True)

    @app.on_callback_query(filters.regex(r"^select_track\|"))
    async def select_track(client, query):
        await query.answer()
        try:
            _, key, index = query.data.split("|", 2)
            pending = PENDING_TRACKS[key]
            track = pending["items"][int(index)]
            PENDING_TRACKS[key]["selected"] = track
            await query.message.edit_text(
                f"**{track['title']}**\nDuration: {track.get('duration_text','?')}\nChoose playback type:",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎧 Audio", callback_data=f"choose_media|audio|{key}|{index}"),
                    InlineKeyboardButton("🎬 Video", callback_data=f"choose_media|video|{key}|{index}"),
                ]])
            )
        except Exception:
            await query.message.edit_text("This selection expired. Run `/play` again.")

    @app.on_callback_query(filters.regex(r"^choose_media\|"))
    async def choose_media(client, query):
        await query.answer("Preparing stream...")
        try:
            parts = query.data.split("|")
            media_type, key = parts[1], parts[2]
            pending = PENDING_TRACKS[key]
            track = pending.get("selected")
            if len(parts) > 3:
                track = pending["items"][int(parts[3])]
            if not track:
                track = pending["items"][0]
            if pending.get("force_video"):
                media_type = "video"
            playable = await get_stream_url(track["webpage_url"], media_type)
            result = await stream.play(pending["chat_id"], playable, media_type)
            PENDING_TRACKS.pop(key, None)
            if result == "queued":
                await query.message.edit_text(f"➕ Added to queue: **{playable['title']}**")
                return
            thumb = await get_thumb(playable.get("videoid"), playable.get("title"), playable.get("duration_text"), playable.get("views"), playable.get("channel"), BOT_NAME)
            await query.message.delete()
            await client.send_photo(
                pending["chat_id"], thumb,
                caption=f"🎶 **Now Playing**\n**{playable['title']}**\nDuration: {playable.get('duration_text','?')}",
                reply_markup=stream_buttons(pending["chat_id"]),
            )
        except Exception as exc:
            LOGGER.exception("Unable to start stream")
            try: await query.message.edit_text(f"Unable to start playback: `{type(exc).__name__}`")
            except Exception: pass
