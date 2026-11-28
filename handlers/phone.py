"""Privacy-friendly international phone number validation command.

This command validates number format locally. It does not look up a person's
identity, live location, or carrier, and does not send the number to a third-party API.
"""
import logging
import re

from pyrogram import filters
from pyrogram.enums import ParseMode
import phonenumbers
from phonenumbers import PhoneNumberFormat, PhoneNumberType

LOGGER = logging.getLogger("v3_musicbot.phone")

_NUMBER_CLEAN_RE = re.compile(r"^[+0-9().\-\s]+$")


def _number_type(number):
    kind = phonenumbers.number_type(number)
    labels = {
        PhoneNumberType.MOBILE: "Mobile",
        PhoneNumberType.FIXED_LINE: "Fixed line",
        PhoneNumberType.FIXED_LINE_OR_MOBILE: "Fixed line or mobile",
        PhoneNumberType.TOLL_FREE: "Toll-free",
        PhoneNumberType.PREMIUM_RATE: "Premium-rate",
        PhoneNumberType.SHARED_COST: "Shared-cost",
        PhoneNumberType.VOIP: "VoIP",
        PhoneNumberType.PERSONAL_NUMBER: "Personal number",
        PhoneNumberType.PAGER: "Pager",
        PhoneNumberType.UAN: "UAN",
        PhoneNumberType.VOICEMAIL: "Voicemail",
        PhoneNumberType.UNKNOWN: "Unknown",
    }
    return labels.get(kind, "Unknown")


def register_phone_handlers(app):
    @app.on_message(filters.command("phone", prefixes=[".", "!", "/"]))
    async def phone_command(_, message):
        parts = message.text.split(maxsplit=1) if message.text else []
        if len(parts) < 2 or not parts[1].strip():
            return await message.reply_text(
                "<b>📱 Phone Number Validator</b>\n\n"
                "Send a number in international format, including its country code.\n"
                "Example: <code>/phone +919876543210</code>\n\n"
                "<i>This checks number format only. It cannot identify the owner, "
                "track a phone, or provide a person's live location.</i>",
                parse_mode=ParseMode.HTML,
            )

        raw_number = parts[1].strip()
        if len(raw_number) > 32 or not _NUMBER_CLEAN_RE.fullmatch(raw_number):
            return await message.reply_text(
                "❌ Invalid input. Use digits and an optional leading +.\n"
                "Example: <code>/phone +919876543210</code>",
                parse_mode=ParseMode.HTML,
            )

        if not raw_number.startswith("+"):
            return await message.reply_text(
                "⚠️ Please include the international country code.\n"
                "Example: <code>/phone +919876543210</code>",
                parse_mode=ParseMode.HTML,
            )

        try:
            number = phonenumbers.parse(raw_number, None)
            valid = phonenumbers.is_valid_number(number)
            possible = phonenumbers.is_possible_number(number)
            country = phonenumbers.region_code_for_number(number) or "Unknown"
            country_calling_code = f"+{number.country_code}"
            formatted = phonenumbers.format_number(
                number, PhoneNumberFormat.INTERNATIONAL
            )
            kind = _number_type(number)
        except phonenumbers.NumberParseException:
            return await message.reply_text(
                "❌ Could not parse this number. Check the country code and try again."
            )
        except Exception:
            LOGGER.exception("Phone number validation failed")
            return await message.reply_text(
                "❌ Number validation failed. Please try again later."
            )

        status = "✅ Valid" if valid else ("⚠️ Possible, but not confirmed valid" if possible else "❌ Invalid")
        result = (
            "<b>📱 PHONE NUMBER REPORT</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"<b>Status:</b> {status}\n"
            f"<b>International:</b> <code>{formatted}</code>\n"
            f"<b>Country/Region code:</b> <code>{country}</code>\n"
            f"<b>Calling code:</b> <code>{country_calling_code}</code>\n"
            f"<b>Number type:</b> <code>{kind}</code>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "<i>Offline format validation only. No owner, carrier, or live-location lookup is performed.</i>"
        )
        await message.reply_text(result, parse_mode=ParseMode.HTML)
