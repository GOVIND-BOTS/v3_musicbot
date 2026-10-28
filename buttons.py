from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def start_buttons(owner_id: int, support: str, channel: str, bot_username: str):
    rows = [
        [
            InlineKeyboardButton(
                "➕ Add Me to Group",
                url=f"https://t.me/{bot_username}?startgroup=true"
            )
        ]
    ]

    extra = []

    if support and support.startswith("http"):
        extra.append(InlineKeyboardButton("💬 Support", url=support))

    if channel and channel.startswith("http"):
        extra.append(InlineKeyboardButton("📢 Channel", url=channel))

    if extra:
        rows.append(extra)

    rows.append([
        InlineKeyboardButton("🆘 Help", callback_data="help_cmd")
    ])

    return InlineKeyboardMarkup(rows)


def help_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🏠 Home", callback_data="start_home"),
            InlineKeyboardButton("✖ Close", callback_data="ctrl_close"),
        ]
    ])


def stream_buttons(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▷", callback_data=f"ctrl_resume|{chat_id}"),
            InlineKeyboardButton("Ⅱ", callback_data=f"ctrl_pause|{chat_id}"),
            InlineKeyboardButton("↻", callback_data=f"ctrl_replay|{chat_id}"),
            InlineKeyboardButton("‣‣I", callback_data=f"ctrl_skip|{chat_id}"),
            InlineKeyboardButton("■", callback_data=f"ctrl_stop|{chat_id}"),
        ],
        [
            InlineKeyboardButton("♡ Queue", callback_data=f"ctrl_queue|{chat_id}"),
            InlineKeyboardButton("✖ Close", callback_data="ctrl_close"),
        ],
    ])


def queue_buttons(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▷ Resume", callback_data=f"ctrl_resume|{chat_id}"),
            InlineKeyboardButton("Ⅱ Pause", callback_data=f"ctrl_pause|{chat_id}"),
        ],
        [
            InlineKeyboardButton("‣‣I Skip", callback_data=f"ctrl_skip|{chat_id}"),
            InlineKeyboardButton("■ Stop", callback_data=f"ctrl_stop|{chat_id}"),
        ],
        [
            InlineKeyboardButton("✖ Close", callback_data="ctrl_close")
        ],
    ])
