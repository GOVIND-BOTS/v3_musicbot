"""Consent-based Instagram export analyzer with paginated username buttons.

Instagram does not provide a supported way to list arbitrary users' followers.
This handler therefore uses only the account owner's downloaded Instagram export.
"""
import io
import json
import logging
import re
import zipfile

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

LOGGER = logging.getLogger(__name__)
_WAITING_FOR_EXPORT = set()
_REPORTS = {}
_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_MAX_UNCOMPRESSED_BYTES = 80 * 1024 * 1024
_USERNAME_RE = re.compile(r"^[a-z0-9._]{1,30}$")


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
                if isinstance(value, str):
                    username = value.strip().lstrip("@").lower()
                    if _USERNAME_RE.fullmatch(username):
                        usernames.add(username)
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

        follower_files = [
            name for name in archive.namelist()
            if re.search(r"(?:^|/)followers_\d+\.json$", name, re.IGNORECASE)
            and not name.startswith("__MACOSX/")
        ]
        following_name = _find_json_member(archive, "following.json")
        if not follower_files or not following_name:
            raise ValueError("followers_1.json ya following.json nahi mili. Instagram export JSON format mein ZIP karo.")

        try:
            followers = set()
            for name in follower_files:
                payload = json.loads(archive.read(name).decode("utf-8"))
                followers.update(_extract_usernames(payload))
            following_payload = json.loads(archive.read(following_name).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, RuntimeError):
            raise ValueError("Instagram export JSON read nahi ho paayi.")

    return followers, _extract_usernames(following_payload, following=True)


def _report_keyboard(counts):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"👥 Followers ({counts['followers']})", callback_data="insta:list:followers:0"),
            InlineKeyboardButton(f"➡️ Following ({counts['following']})", callback_data="insta:list:following:0"),
        ],
        [
            InlineKeyboardButton(f"🤝 Mutual ({counts['mutual']})", callback_data="insta:list:mutual:0"),
            InlineKeyboardButton(f"↗️ Not following back ({counts['not_back']})", callback_data="insta:list:not_back:0"),
        ],
        [
            InlineKeyboardButton(f"↙️ Fans not followed ({counts['fans']})", callback_data="insta:list:fans:0"),
        ],
    ])


def _list_keyboard(usernames, page, category):
    start = page * 9
    current = usernames[start:start + 9]
    rows = []
    for offset in range(0, len(current), 3):
        rows.append([
            InlineKeyboardButton(
                "@" + username,
                url="https://www.instagram.com/" + username + "/",
            )
            for username in current[offset:offset + 3]
        ])

    total_pages = max(1, (len(usernames) + 8) // 9)
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton("⬅️ Back", callback_data=f"insta:list:{category}:{page - 1}"))
    navigation.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="insta:noop"))
    if page + 1 < total_pages:
        navigation.append(InlineKeyboardButton("Next ➡️", callback_data=f"insta:list:{category}:{page + 1}"))
    rows.append(navigation)
    rows.append([InlineKeyboardButton("↩️ Report", callback_data="insta:report")])
    return InlineKeyboardMarkup(rows)


def register_insta_handlers(app):
    @app.on_message(filters.command("insta"))
    async def insta_command(_, message):
        user_id = message.from_user.id if message.from_user else None
        if not user_id:
            return

        args = message.command[1:] if len(message.command) > 1 else []
        requested_username = args[0].strip().lstrip("@") if args else None
        if requested_username and not _USERNAME_RE.fullmatch(requested_username.lower()):
            await message.reply_text("❌ Valid Instagram username likho. Example: /insta instagram")
            return

        _WAITING_FOR_EXPORT.add((message.chat.id, user_id))
        target_line = (
            f"\nRequested username: **@{requested_username}**\n"
            if requested_username else ""
        )
        await message.reply_text(
            "📊 **V3MUSIC Instagram Analyzer**\n"
            f"{target_line}\n"
            "Username se kisi bhi account ki complete followers/following list officially fetch nahi hoti. "
            "Isliye bot fake/live numbers nahi dikhayega.\n\n"
            "List aur 9-per-page username buttons ke liye account owner ka Instagram JSON export ZIP upload karo. "
            "Export mein jitne followers/following honge, wahi report mein dikhaye jayenge.\n\n"
            "⚠️ Sirf apna export ya account owner ki permission wala export bhejo. "
            "Bot Instagram password nahi maangta. Gender Instagram export mein verified nahi hota, "
            "isliye girls/boys counts guess nahi kiye jayenge.\n\n"
            "ZIP file isi chat mein Telegram document ke roop mein bhejo."
        )

    @app.on_message(filters.document)
    async def insta_export_document(_, message):
        user_id = message.from_user.id if message.from_user else None
        key = (message.chat.id, user_id) if user_id else None
        if not key or key not in _WAITING_FOR_EXPORT:
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
            _WAITING_FOR_EXPORT.discard(key)

            mutuals = followers & following
            not_following_back = following - followers
            followers_not_followed = followers - following
            report = {
                "followers": sorted(followers),
                "following": sorted(following),
                "mutual": sorted(mutuals),
                "not_back": sorted(not_following_back),
                "fans": sorted(followers_not_followed),
            }
            _REPORTS[key] = report
            counts = {name: len(values) for name, values in report.items()}

            await status.edit_text(
                "📊 **V3MUSIC INSTAGRAM REPORT**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👥 Total Followers: **{counts['followers']:,}**\n"
                f"➡️ Total Following: **{counts['following']:,}**\n"
                f"🤝 Mutual Follow: **{counts['mutual']:,}**\n"
                f"↗️ You follow, they don't follow back: **{counts['not_back']:,}**\n"
                f"↙️ They follow, you don't follow back: **{counts['fans']:,}**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "👇 Kisi list ko kholne ke liye button dabao. Har page par maximum 9 usernames hain.\n"
                "ℹ️ Instagram export gender verify nahi karta; girls/boys counts available nahi hain.\n"
                "_Report uploaded export ke data par based hai._",
                reply_markup=_report_keyboard(counts),
            )
        except ValueError as exc:
            await status.edit_text(f"❌ {exc}")
        except Exception:
            LOGGER.exception("Instagram export analysis failed")
            await status.edit_text("❌ Export process nahi ho paayi. Fresh JSON ZIP export karke try karo.")

    @app.on_callback_query(filters.regex(r"^insta:"))
    async def insta_pagination(_, query):
        user_id = query.from_user.id
        key = (query.message.chat.id, user_id) if query.message else None
        if not key or key not in _REPORTS:
            await query.answer("Ye report aapke liye available nahi hai. /insta se dobara shuru karein.", show_alert=True)
            return

        data = query.data
        if data == "insta:noop":
            await query.answer()
            return

        report = _REPORTS[key]
        if data == "insta:report":
            counts = {name: len(values) for name, values in report.items()}
            await query.message.edit_text(
                "📊 **V3MUSIC INSTAGRAM REPORT**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👥 Total Followers: **{counts['followers']:,}**\n"
                f"➡️ Total Following: **{counts['following']:,}**\n"
                f"🤝 Mutual Follow: **{counts['mutual']:,}**\n"
                f"↗️ You follow, they don't follow back: **{counts['not_back']:,}**\n"
                f"↙️ They follow, you don't follow back: **{counts['fans']:,}**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                "👇 Kisi list ko kholne ke liye button dabao. Har page par maximum 9 usernames hain.\n"
                "ℹ️ Gender-wise counts available nahi hain.",
                reply_markup=_report_keyboard(counts),
            )
            await query.answer()
            return

        try:
            _, _, category, page_text = data.split(":")
            page = int(page_text)
            usernames = report[category]
            total_pages = max(1, (len(usernames) + 8) // 9)
            if page < 0 or page >= total_pages:
                raise ValueError("Invalid page")
        except (ValueError, KeyError):
            await query.answer("Invalid page.", show_alert=True)
            return

        labels = {
            "followers": "Followers",
            "following": "Following",
            "mutual": "Mutual followers",
            "not_back": "You follow, they don't follow back",
            "fans": "They follow, you don't follow back",
        }
        await query.message.edit_text(
            f"📋 **{labels[category]}**\n"
            f"Total: **{len(usernames):,}** · Page **{page + 1}/{total_pages}**\n\n"
            "Username button dabane par Instagram profile khulega.",
            reply_markup=_list_keyboard(usernames, page, category),
        )
        await query.answer()
