import asyncio
from html import escape

from pyrogram import filters
from pyrogram.enums import ParseMode

from config import SUDO_USERS
from .status_cards import get_status_image


def _run_speedtest():
    import speedtest

    test = speedtest.Speedtest()
    test.get_best_server()
    download = test.download()
    upload = test.upload()
    result = test.results.dict()
    return {
        "download": download / 1_000_000,
        "upload": upload / 1_000_000,
        "ping": result.get("ping", 0),
        "server": result.get("server", {}).get("name", "Unknown"),
        "country": result.get("server", {}).get("country", "Unknown"),
        "isp": result.get("client", {}).get("isp", "Unknown"),
    }


def register_speedtest_handlers(app):
    sudo_filter = filters.user(list(SUDO_USERS))

    @app.on_message(filters.command(["speedtest", "spt"]) & sudo_filter)
    async def speedtest_command(client, message):
        progress = await message.reply_text(
            "⚡ <b>V3 MUSIC SPEEDTEST</b>\n\nFinding the best server...",
            parse_mode=ParseMode.HTML,
        )

        try:
            result = await asyncio.to_thread(_run_speedtest)
            caption = (
                "⚡ <b>V3 MUSIC — SPEEDTEST RESULT</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"⬇️ <b>Download:</b> <code>{result['download']:.2f} Mbps</code>\n"
                f"⬆️ <b>Upload:</b> <code>{result['upload']:.2f} Mbps</code>\n"
                f"📡 <b>Ping:</b> <code>{result['ping']:.2f} ms</code>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"🌐 <b>ISP:</b> {escape(str(result['isp']))}\n"
                f"📍 <b>Server:</b> {escape(str(result['server']))}, {escape(str(result['country']))}"
            )
            try:
                await message.reply_photo(
                    photo=get_status_image("speedtest"),
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                )
                await progress.delete()
            except Exception:
                await progress.edit_text(caption, parse_mode=ParseMode.HTML)
        except Exception as exc:
            await progress.edit_text(
                "❌ <b>Speedtest failed.</b>\n"
                f"<code>{type(exc).__name__}: {escape(str(exc)[:500])}</code>\n\n"
                "Check whether the hosting provider allows outbound speed-test connections.",
                parse_mode=ParseMode.HTML,
            )
