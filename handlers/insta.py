"""Consent-based Instagram export analyzer."""
import io
import json
import logging
import zipfile

from pyrogram import filters

LOGGER = logging.getLogger(__name__)
_WAITING_FOR_EXPORT = set()
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024


def _find_json_member(archive, suffix):
    for name in archive.namelist():
        if name.lower().endswith(suffix.lower()) and not name.startswith("__MACOSX/"):
            return name
    return None


def _extract_usernames(payload, following=False):
    if isinstance(payload, dict):
        entries = payload.get("relationships_following", []) if following else payload.get("relationships_followers", payload)
    else:
        entries = payload

    usernames = set()
    if not isinstance(entries, list):
        return usernames
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for item in entry.get("string_list_data") or []:
            if isinstance(item, dict):
                value = item.get("value")
                if isinstance(value, str) and value.strip():
                    usernames.add(value.strip().lstrip("@").lower())
    return usernames


def _read_export(file_bytes):
    if len(file_bytes) > _MAX_UPLOAD_BYTES:
        raise ValueError("ZIP file 20 MB se chhoti honi chahiye.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(file_bytes))
    except zipfile.BadZipFile:
        raise ValueError("Valid Instagram data-export ZIP file bhejo.")

    with archive:
        if sum(item.file_size for item in archive.infolist()) > _MAX_UNCOMPRESSED_BYTES:
            raise ValueError("Export ZIP ka uncompressed size allowed limit se zyada hai.")
        followers_name = _find_json_member(archive, "followers_1.json")
        following_name = _find_json_member(archive, "following.json")
        if not followers_name or not following_name:
            raise ValueError("followers_1.json ya following.json nahi mili. Instagram export JSON format mein ZIP karo.")
        try:
            followers_payload = json.loads(archive.read(followers_name).decode("utf-8"))
            following_payload = json.loads(archive.read(following_name).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError):
            raise ValueError("Instagram export JSON read nahi ho paayi.")

    return _extract_usernames(followers_payload), _extract_usernames(following_payload, following=True)


def register_insta_handlers(app):
    @app.on_message(filters.command("insta"))
    async def insta_command(_, message):
        user_id = message.from_user.id if message.from_user else None
        if not user_id:
            return
        _WAITING_FOR_EXPORT.add(user_id)
        await message.reply_text(
            "📊 **V3MUSIC Instagram Export Analyzer**\n\n"
            "Account owner apni Instagram information ka JSON format export ZIP download karke yahan upload karein.\n\n"
            "⚠️ Sirf account owner ki permission se export use karein. Bot Instagram password nahi maangta aur username se private data nahi nikalta.\n"
            "Gender Instagram export mein verified form mein nahi hota, isliye male/female counts guess karke nahi dikhaye jayenge.\n\n"
            "Ab apni export ZIP file isi chat mein bhejein."
        )

    @app.on_message(filters.document)
    async def insta_export_document(_, message):
        user_id = message.from_user.id if message.from_user else None
        if not user_id or user_id not in _WAITING_FOR_EXPORT:
            return
        document = message.document
        if not document.file_name or not document.file_name.lower().endswith(".zip"):
            await message.reply_text("Instagram export ki ZIP file bhejo.")
            return
        if document.file_size and document.file_size > _MAX_UPLOAD_BYTES:
            await message.reply_text("ZIP 20 MB se chhoti honi chahiye.")
            return

        status = await message.reply_text("⏳ Export check ho rahi hai...")
        try:
            downloaded = await message.download(in_memory=True)
            file_bytes = downloaded.getvalue() if hasattr(downloaded, "getvalue") else downloaded.read()
            followers, following = _read_export(file_bytes)
            _WAITING_FOR_EXPORT.discard(user_id)
            mutuals = followers & following
            not_following_back = following - followers
            followers_not_followed = followers - following
            await status.edit_text(
                "📊 **V3MUSIC INSTAGRAM REPORT**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👥 Total Followers: **{len(followers):,}**\n"
                f"➡️ Total Following: **{len(following):,}**\n"
                f"🤝 Mutual Follow: **{len(mutuals):,}**\n"
                f"↗️ You follow, they don't follow back: **{len(not_following_back):,}**\n"
                f"↙️ They follow, you don't follow back: **{len(followers_not_followed):,}**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "ℹ️ Gender Instagram export mein verified nahi hota; gender-wise counts report nahi kiye gaye.\n"
                "_Report sirf uploaded export ke data par based hai._"
            )
        except ValueError as exc:
            await status.edit_text(f"❌ {exc}")
        except Exception:
            LOGGER.exception("Instagram export analysis failed")
            await status.edit_text("❌ Export process nahi ho paayi. Fresh JSON ZIP export karke try karo.")
