
import html


# ----------------------------------
# FONT STYLING
# ----------------------------------

UPPER = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
LOWER = "abcdefghijklmnopqrstuvwxyz"
DIGITS = "0123456789"

STYLED_UPPER = "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁"
STYLED_LOWER = "𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛"
STYLED_DIGITS = "𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗"

FONT_MAP = str.maketrans(
    UPPER + LOWER + DIGITS,
    STYLED_UPPER + STYLED_LOWER + STYLED_DIGITS,
)


def stylize(text):
    """Convert English text and digits into Adisha Music font."""
    return str(text).translate(FONT_MAP)


# ----------------------------------
# DURATION
# ----------------------------------

def format_duration(seconds):
    try:
        seconds = int(float(seconds or 0))
    except (TypeError, ValueError):
        return "00:00"

    seconds = max(0, seconds)

    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:02}:{minutes:02}:{seconds:02}"

    return f"{minutes:02}:{seconds:02}"


# ----------------------------------
# PROGRESS
# ----------------------------------

def progress_bar(elapsed, duration, length=10):
    try:
        elapsed = max(0, float(elapsed or 0))
        duration = max(0, float(duration or 0))
    except (TypeError, ValueError):
        elapsed = 0
        duration = 0

    if duration <= 0:
        return "──────────"

    progress = min(elapsed / duration, 1)
    filled = min(length, int(progress * length))

    return "━" * filled + "─" * (length - filled)


def progress_button_text(elapsed, duration):
    elapsed_text = format_duration(elapsed)
    duration_text = format_duration(duration)
    bar = progress_bar(elapsed, duration, length=8)

    return f"{elapsed_text} {bar} {duration_text}"


# ----------------------------------
# REQUESTER
# ----------------------------------

def add_requester(track, user):
    item = dict(track)

    if not user:
        return item

    item["requested_by"] = user.id

    first_name = user.first_name or "Group member"

    if user.last_name:
        first_name += f" {user.last_name}"

    item["requested_by_name"] = first_name
    item["requested_by_username"] = user.username

    return item


def requester_html(track):
    name = html.escape(
        str(track.get("requested_by_name", "Group member"))
    )

    user_id = track.get("requested_by")
    username = track.get("requested_by_username")

    if user_id:
        if username:
            url = f"https://t.me/{username}"
        else:
            url = f"tg://user?id={user_id}"

        return f'<a href="{url}">{name}</a>'

    return name


# ----------------------------------
# NOW PLAYING CAPTION
# ----------------------------------

def now_playing_caption(
    track,
    elapsed=0,
    loop_mode="off",
    shuffle=False,
):
    if not isinstance(track, dict):
        track = {}

    title = html.escape(
        str(track.get("title", "Unknown Track"))
    )

    duration = track.get("duration_text") or format_duration(
        track.get("duration", 0)
    )

    channel = html.escape(
        str(track.get("channel", "YouTube"))
    )

    requester = requester_html(track)

    url = track.get("webpage_url") or track.get("url") or ""
    safe_url = html.escape(str(url), quote=True)

    if safe_url.startswith(("https://", "http://")):
        title_text = f'<a href="{safe_url}">{title}</a>'
    else:
        title_text = title

    return (
        f"<b>🎧 {stylize('ADISHA MUSIC')}</b>\n"
        f"<i>{stylize('NOW PLAYING')}</i>\n\n"
        f"🎵 <b>{title_text}</b>\n\n"
        f"⏱ <b>{stylize('Duration')}:</b> {html.escape(str(duration))}\n"
        f"📡 <b>{stylize('Source')}:</b> {channel}\n"
        f"👤 <b>{stylize('Requested By')}:</b> {requester}"
    )


# ----------------------------------
# QUEUE TRACK CAPTION
# ----------------------------------

def queue_track_caption(track, position=None):
    if not isinstance(track, dict):
        track = {}

    title = html.escape(
        str(track.get("title", "Unknown Track"))
    )

    duration = track.get("duration_text") or format_duration(
        track.get("duration", 0)
    )

    requester = requester_html(track)

    text = (
        f"🎵 <b>{stylize('QUEUED TRACK')}</b>\n\n"
        f"<b>{title}</b>\n"
        f"⏱ {stylize('Duration')}: {html.escape(str(duration))}\n"
        f"👤 {stylize('Requested By')}: {requester}"
    )

    if position is not None:
        text += f"\n🔢 {stylize('Position')}: {position}"

    return text
