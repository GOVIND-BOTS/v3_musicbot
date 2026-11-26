import platform
import sys
import time

import psutil
from pyrogram import filters
from pyrogram.enums import ParseMode

from config import BOT_NAME, SUDO_USERS, START_IMAGE
from database.mongodb import get_chats, get_users
from music import music_queue
from .ping import STARTED_AT, readable_uptime


def register_status_handlers(app):
    @app.on_message(filters.command(["status", "stats"]))
    async def status_command(client, message):
        reply = await message.reply_text("📊 Collecting V3 Music statistics...")

        try:
            me = await client.get_me()
            chats = await get_chats()
            users = await get_users()
            active = await music_queue.get_active_chat_ids()

            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            cpu = psutil.cpu_percent(interval=None)

            caption = (
                f"🍃 <b>{BOT_NAME} — SYSTEM STATUS</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🤖 <b>Bot:</b> @{me.username or me.id}\n"
                "🟢 <b>Status:</b> Online\n"
                f"⏱ <b>Uptime:</b> <code>{readable_uptime(time.monotonic() - STARTED_AT)}</code>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👥 <b>Registered users:</b> <code>{len(users)}</code>\n"
                f"👥 <b>Registered groups:</b> <code>{len(chats)}</code>\n"
                f"🎧 <b>Active voice chats:</b> <code>{len(active)}</code>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🧠 <b>CPU:</b> <code>{cpu:.1f}%</code>\n"
                f"💾 <b>RAM:</b> <code>{memory.percent:.1f}%</code> "
                f"({memory.used / (1024 ** 3):.2f}/{memory.total / (1024 ** 3):.2f} GB)\n"
                f"💿 <b>Disk:</b> <code>{disk.percent:.1f}%</code>\n"
                f"🐍 <b>Python:</b> <code>{sys.version.split()[0]}</code>\n"
                f"🖥 <b>Platform:</b> <code>{platform.system()}</code>"
            )

            if message.from_user and message.from_user.id in SUDO_USERS:
                caption += f"\n🔐 <b>Sudo users:</b> <code>{len(SUDO_USERS)}</code>"

            try:
                await message.reply_photo(
                    photo=START_IMAGE,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
                await reply.delete()
            except Exception:
                await reply.edit_text(
                    caption,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
        except Exception as exc:
            await reply.edit_text(
                f"❌ Could not collect status: <code>{type(exc).__name__}</code>",
                parse_mode=ParseMode.HTML,
            )
