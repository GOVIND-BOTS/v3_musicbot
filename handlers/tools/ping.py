import time

import psutil
from pyrogram import filters
from pyrogram.enums import ParseMode

from player_ui import stylize

STARTED_AT = time.monotonic()


def readable_uptime(seconds):
    seconds = max(0, int(seconds))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def register_ping_handlers(app):
    @app.on_message(filters.command(["ping", "alive"]))
    async def ping_command(client, message):
        started = time.perf_counter()
        reply = await message.reply_text("📡 Checking V3 Music...")
        latency = (time.perf_counter() - started) * 1000

        try:
            cpu = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            ram_used = memory.used / (1024 ** 3)
            ram_total = memory.total / (1024 ** 3)
            uptime = readable_uptime(time.monotonic() - STARTED_AT)

            text = (
                "🍃 <b>V3 MUSIC SYSTEM STATUS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"⚡ <b>Ping:</b> <code>{latency:.2f} ms</code>\n"
                f"🧠 <b>CPU:</b> <code>{cpu:.1f}%</code>\n"
                f"💾 <b>RAM:</b> <code>{ram_used:.2f}/{ram_total:.2f} GB</code>\n"
                f"⏱ <b>Uptime:</b> <code>{uptime}</code>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🎧 <b>Service:</b> {stylize('Online')}"
            )
            await reply.edit_text(text, parse_mode=ParseMode.HTML)
        except Exception:
            await reply.edit_text(
                f"✅ <b>V3 Music is online</b>\n⚡ Ping: <code>{latency:.2f} ms</code>",
                parse_mode=ParseMode.HTML,
            )
