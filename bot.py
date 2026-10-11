import logging
import yt_dlp
from pyrogram import Client, filters, idle
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality

from config import API_ID, API_HASH, BOT_TOKEN, SESSION_STRING

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

assistant = Client(
    "vc_assistant",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)

calls = PyTgCalls(assistant)


def get_stream(query, video=False):
    search = query if query.startswith("https://") else f"ytsearch1:{query}"

    options = {
        "format": (
            "best[height<=480][vcodec!=none][acodec!=none]/best"
            if video else "bestaudio/best"
        ),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        data = ydl.extract_info(search, download=False)

    if data.get("entries"):
        data = next((x for x in data["entries"] if x), None)

    if not data or not data.get("url"):
        raise ValueError("YouTube par stream nahi mila.")

    return data["url"], data.get("title", "YouTube song")


@bot.on_message(filters.command("start"))
def start(_, message):
    message.reply_text(
        "🎵 YouTube VC Bot\n\n"
        "/play song name - Audio\n"
        "/vplay song name - Video\n"
        "/pause - Pause\n"
        "/resume - Resume\n"
        "/stop - Stop"
    )


@bot.on_message(filters.command(["play", "vplay"]) & filters.group)
def play(_, message):
    video = message.command[0].lower() == "vplay"

    if len(message.command) < 2:
        message.reply_text(
            "Example: /vplay song name"
            if video else "Example: /play song name"
        )
        return

    query = " ".join(message.command[1:])

    try:
        message.reply_text("🔎 YouTube par search ho raha hai...")
        url, title = get_stream(query, video)

        if video:
            stream = MediaStream(
                url,
                AudioQuality.HIGH,
                VideoQuality.HD_720p,
            )
        else:
            stream = MediaStream(
                url,
                AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
            )

        calls.play(message.chat.id, stream)
        message.reply_text(f"🎵 Playback request: {title}")

    except Exception:
        logger.exception("Playback error")
        message.reply_text(
            "❌ Playback nahi chala. VC active hai ya nahi check karo. "
            "Error details Render logs mein dekho."
        )


@bot.on_message(filters.command("pause") & filters.group)
def pause(_, message):
    try:
        calls.pause(message.chat.id)
        message.reply_text("⏸️ Paused")
    except Exception as e:
        message.reply_text(f"Pause error: {e}")


@bot.on_message(filters.command("resume") & filters.group)
def resume(_, message):
    try:
        calls.resume(message.chat.id)
        message.reply_text("▶️ Resumed")
    except Exception as e:
        message.reply_text(f"Resume error: {e}")


@bot.on_message(filters.command("stop") & filters.group)
def stop(_, message):
    try:
        calls.leave_call(message.chat.id)
        message.reply_text("⏹️ Playback stopped")
    except Exception as e:
        message.reply_text(f"Stop error: {e}")


def main():
    try:
        assistant.start()
        bot.start()
        calls.start()
        logger.info("Bot started")
        idle()
    finally:
        try:
            calls.stop()
        except Exception:
            pass
        try:
            bot.stop()
        except Exception:
            pass
        try:
            assistant.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()
