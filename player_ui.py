
from html import escape


def format_duration(seconds):
    """Convert seconds into MM:SS or HH:MM:SS."""

    try:
        seconds = max(0, int(float(seconds or 0)))
    except (TypeError, ValueError, OverflowError):
        return "Unknown"

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def add_requester(track, user):
    """Add requester information without modifying the original track."""

    item = dict(track or {})

    if user:
        item["requested_by_id"] = getattr(user, "id", 0) or 0
        item["requested_by_name"] = (
            getattr(user, "first_name", None)
            or "Telegram User"
        )
        item["requested_by_username"] = (
            getattr(user, "username", None) or ""
        )
    else:
        item.setdefault("requested_by_id", 0)
        item.setdefault("requested_by_name", "Group member")
        item.setdefault("requested_by_username", "")

    return item


def requester_html(track):
    """Create a safe clickable requester name."""

    track = track or {}

    name = escape(
        str(track.get("requested_by_name") or "Group member")
    )

    try:
        user_id = int(track.get("requested_by_id") or 0)
    except (TypeError, ValueError):
        user_id = 0

    if user_id > 0:
        return (
            f'<a href="tg://user?id={user_id}">'
            f"{name}</a>"
        )

    username = str(
        track.get("requested_by_username") or ""
    ).strip().lstrip("@")

    if username:
        return f"@{escape(username)}"

    return name


def progress_bar(elapsed, duration, length=12):
    """Generate a text-based playback progress bar."""

    try:
        duration = int(float(duration or 0))
        elapsed = int(float(elapsed or 0))
    except (TypeError, ValueError, OverflowError):
        return "Progress unavailable"

    if duration <= 0:
        return "Progress unavailable"

    elapsed = max(0, min(elapsed, duration))
    filled = int(length * elapsed / duration)

    return (
        "━" * filled
        + "●"
        + "─" * (length - filled)
    )


def now_playing_caption(
    track,
    elapsed=0,
    loop_mode="off",
    shuffle=False,
):
    """Build the GOVIND MUSIC Now Playing caption."""

    track = track or {}

    title = escape(
        str(track.get("title") or "Unknown title")
    )

    duration = track.get("duration") or 0

    try:
        duration = int(float(duration))
    except (TypeError, ValueError, OverflowError):
        duration = 0

    duration_text = (
        str(track.get("duration_text") or "").strip()
        or format_duration(duration)
    )

    duration_text = escape(duration_text)

    media_type = str(
        track.get("media_type") or "audio"
    ).lower()

    media_label = (
        "🎬 VIDEO"
        if media_type == "video"
        else "🎧 AUDIO"
    )

    progress = progress_bar(
        elapsed,
        duration,
    )

    try:
        elapsed = max(0, int(float(elapsed or 0)))
    except (TypeError, ValueError, OverflowError):
        elapsed = 0

    if duration > 0:
        elapsed = min(elapsed, duration)

        time_line = (
            f"{format_duration(elapsed)} "
            f"{progress} "
            f"{format_duration(duration)}"
        )
    else:
        time_line = "Progress unavailable"

    loop_labels = {
        "off": "OFF",
        "track": "TRACK",
        "queue": "QUEUE",
    }

    loop_mode = str(loop_mode or "off").lower()
    loop_text = loop_labels.get(loop_mode, "OFF")

    shuffle_text = (
        "ON"
        if shuffle
        else "OFF"
    )

    requester = requester_html(track)

    return (
        "🎶 <b>GOVIND MUSIC</b>\n\n"
        "▶️ <b>NOW PLAYING</b>\n\n"
        f"🎵 <b>Title:</b> {title}\n"
        f"⏱ <b>Duration:</b> {duration_text}\n"
        f"📡 <b>Stream:</b> {media_label}\n"
        f"👤 <b>Requested by:</b> {requester}\n\n"
        f"<code>{escape(time_line)}</code>\n\n"
        f"🔁 <b>Loop:</b> {loop_text}\n"
        f"🔀 <b>Shuffle:</b> {shuffle_text}\n\n"
        "<i>Powered by GOVIND BOTS</i>"
    )


def queue_track_caption(track, position=None):
    """Create a formatted queue entry."""

    track = track or {}

    title = escape(
        str(track.get("title") or "Unknown title")
    )

    duration = escape(
        str(
            track.get("duration_text")
            or format_duration(track.get("duration"))
        )
    )

    requester = requester_html(track)

    position_text = (
        f"<b>{int(position)}.</b> "
        if position is not None
        else ""
    )

    return (
        f"{position_text}🎵 <b>{title}</b>\n"
        f"   ⏱ {duration} | 👤 {requester}"
    )
