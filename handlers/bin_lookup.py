import html
import logging
import re

from pyrogram import filters
from pyrogram.enums import ParseMode

from SafoneAPI import SafoneAPI

LOGGER = logging.getLogger("v3_musicbot.bin")
api = SafoneAPI()


def _field(response, name, default="N/A"):
    value = getattr(response, name, None)
    if value is None or str(value).strip() == "":
        return default
    return html.escape(str(value))


def register_bin_handlers(app):
    @app.on_message(
        filters.command(
            ["bin", "ccbin", "bininfo"],
            prefixes=[".", "!", "/"],
        )
    )
    async def check_ccbin(client, message):
        parts = message.text.split(maxsplit=1) if message.text else []
        if len(parts) < 2 or not parts[1].strip():
            return await message.reply_text(
                "<b>BIN number bhejein.</b>\n"
                "Example: <code>/bin 457173</code>\n"
                "<i>Sirf starting 6–8 digits; full card details nahi.</i>",
                parse_mode=ParseMode.HTML,
            )

        bin_value = parts[1].strip()
        # Accept BIN/IIN prefixes only. Never accept or process full card numbers.
        if not re.fullmatch(r"\d{6,8}", bin_value):
            return await message.reply_text(
                "<b>❌ Invalid BIN</b>\n"
                "Sirf 6 se 8 digits bhejein. Full card number, CVV ya expiry date mat bhejein.",
                parse_mode=ParseMode.HTML,
            )

        try:
            status = await message.reply_text(
                "<b>🔎 BIN details check ho rahi hain...</b>",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            LOGGER.exception("Could not send BIN lookup status")
            return

        try:
            response = await api.bininfo(bin_value)
            details = (
                "<b>💳 BIN INFORMATION</b>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"<b>🏦 BANK:</b> <code>{_field(response, 'bank')}</code>\n"
                f"<b>🔢 BIN:</b> <code>{_field(response, 'bin', bin_value)}</code>\n"
                f"<b>🌍 COUNTRY:</b> <code>{_field(response, 'country')}</code>\n"
                f"<b>🏳️ FLAG:</b> <code>{_field(response, 'flag')}</code>\n"
                f"<b>🧭 ISO:</b> <code>{_field(response, 'iso')}</code>\n"
                f"<b>🏷 LEVEL:</b> <code>{_field(response, 'level')}</code>\n"
                f"<b>💰 PREPAID:</b> <code>{_field(response, 'prepaid')}</code>\n"
                f"<b>💳 TYPE:</b> <code>{_field(response, 'type')}</code>\n"
                f"<b>🏢 NETWORK:</b> <code>{_field(response, 'vendor')}</code>\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "<i>BIN data is informational and does not verify a card or its balance.</i>"
            )
            await status.edit_text(details, parse_mode=ParseMode.HTML)
        except Exception as exc:
            LOGGER.warning("BIN lookup failed (%s): %s", type(exc).__name__, exc)
            await status.edit_text(
                "🚫 <b>BIN details nahi mil payi.</b>\n"
                "BIN dobara check karein ya kuch der baad try karein.",
                parse_mode=ParseMode.HTML,
            )
