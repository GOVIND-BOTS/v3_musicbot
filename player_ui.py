
from html import escape


def format_duration(seconds):
    """Convert seconds to MM:SS or HH:MM:SS."""
    try:
        seconds = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        return "Unknown"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:02}:{minutes:02}:{secs:02}"
    return f"{minutes:02}:{secs:02}"


def add_requester(track, user):
    """Preserve the requesting user's details with the queued track."""
    item = dict(track or {})

    if user:
        item["requested_by_id"] = user.id
        item["requested_by_name"] = (
            user.first_name or "Telegram User"
        )
        item["requested_by_username"] = user.username or ""
    else:
        item.setdefault("requested_by_id", 0)
        item.setdefault("requested_by_name", "Group member")
        item.setdefault("requested_by_username", "")

    return item


def requester_html(track):
    """Return a clickable Telegram user name when an ID is available."""
    track = track or {}

    name = escape(
        str(track.get("requested_by_name") or "Group member")
    )
    user_id = track.get("requested_by_id") or 0

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        user_id = 0

    if user_id > 0:
        return f'<a href="tg://user?id={user_id}">{name}</a>'

    username = str(track.get("requested_by_username") or "").strip()
    if username:
        return "@" + escape(username.lstrip("@"))

    return name


def now_playing_caption(track, elapsed=0):
    """Build the branded Now Playing message."""
    track = track or {}

    title = escape(str(track.get("title") or "Unknown title"))

    duration_seconds = track.get("duration") or 0
    try:
        duration_seconds = int(duration_seconds)
    except (TypeError, ValueError):
        duration_seconds = 0

    duration_text = escape(
        str(track.get("duration_text") or
            format_duration(duration_seconds))
    )

    try:
        elapsed = max(0, int(elapsed or 0))
    except (TypeError, ValueError):
        elapsed = 0

    # A text progress bar; live updates require a separate updater.
    if duration_seconds > 0:
        elapsed = min(elapsed, duration_seconds)
        filled = min(
            12,
            int(12 * elapsed / duration_seconds)
        )
        progress = "━" * filled + "●" + "─" * (12 - filled)
        time_text = (
            f"{format_duration(elapsed)} "
            f"{progress} {format_duration(duration_seconds)}"
        )
    else:
        time_text = "Progress unavailable"

    return (
        "🎶 <b>GOVIND MUSIC</b>\n\n"
        "➤ <b>STARTED STREAMING</b>\n\n"
        f"✨ <b>TITLE:</b> {title}\n"
        f"⏱ <b>DURATION:</b> {duration_text}\n"
        f"👤 <b>REQUESTED BY:</b> {requester_html(track)}\n\n"
        f"<code>{escape(time_text)}</code>"
    )
