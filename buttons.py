
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from player_ui import stylize


def start_buttons(owner_id: int, support: str, channel: str, bot_username: str):
    rows = []

    if bot_username:
        rows.append([
            InlineKeyboardButton(
                stylize("➕ Add Me to Group"),
                url=f"https://t.me/{bot_username}?startgroup=true",
            )
        ])

    extra = []

    if support and support.startswith("http"):
        extra.append(
            InlineKeyboardButton(
                stylize("💬 Support"),
                url=support,
            )
        )

    if channel and channel.startswith("http"):
        extra.append(
            InlineKeyboardButton(
                stylize("📢 Channel"),
                url=channel,
            )
        )

    if extra:
        rows.append(extra)

    rows.append([
        InlineKeyboardButton(
            stylize("🆘 Help"),
            callback_data="help_cmd",
        )
    ])

    return InlineKeyboardMarkup(rows)


def help_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                stylize("🏠 Home"),
                callback_data="start_home",
            ),
            InlineKeyboardButton(
                stylize("✖ Close"),
                callback_data="ctrl_close",
            ),
        ]
    ])


def stream_buttons(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                stylize("▷ RESUME"),
                callback_data=f"ctrl_resume|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize("Ⅱ PAUSE"),
                callback_data=f"ctrl_pause|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize("↻ REPLAY"),
                callback_data=f"ctrl_replay|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                stylize("⏭ SKIP"),
                callback_data=f"ctrl_skip|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize("⏹ STOP"),
                callback_data=f"ctrl_stop|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                stylize("🔁 LOOP"),
                callback_data=f"ctrl_loop|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize("🔀 SHUFFLE"),
                callback_data=f"ctrl_shuffle|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                stylize("🎶 QUEUE"),
                callback_data=f"ctrl_queue|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize("✖ CLOSE"),
                callback_data="ctrl_close",
            ),
        ],
    ])


def queue_buttons(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                stylize("▷ RESUME"),
                callback_data=f"ctrl_resume|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize("Ⅱ PAUSE"),
                callback_data=f"ctrl_pause|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                stylize("⏭ SKIP"),
                callback_data=f"ctrl_skip|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize("⏹ STOP"),
                callback_data=f"ctrl_stop|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                stylize("🔁 LOOP"),
                callback_data=f"ctrl_loop|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize("🔀 SHUFFLE"),
                callback_data=f"ctrl_shuffle|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                stylize("✖ CLOSE"),
                callback_data="ctrl_close",
            )
        ],
    ])
