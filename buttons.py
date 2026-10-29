```python
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def start_buttons(
    owner_id: int,
    support: str,
    channel: str,
    bot_username: str,
):
    rows = []

    # Add bot to a group
    if bot_username:
        rows.append([
            InlineKeyboardButton(
                text="➕ Add Me to Group",
                url=f"https://t.me/{bot_username}?startgroup=true",
            )
        ])

    # Support and channel buttons
    extra = []

    if support and support.startswith("http"):
        extra.append(
            InlineKeyboardButton(
                text="💬 Support",
                url=support,
            )
        )

    if channel and channel.startswith("http"):
        extra.append(
            InlineKeyboardButton(
                text="📢 Channel",
                url=channel,
            )
        )

    if extra:
        rows.append(extra)

    # Help menu
    rows.append([
        InlineKeyboardButton(
            text="🆘 Help",
            callback_data="help_cmd",
        )
    ])

    return InlineKeyboardMarkup(rows)


def help_buttons():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="🏠 Home",
                callback_data="start_home",
            ),
            InlineKeyboardButton(
                text="✖ Close",
                callback_data="ctrl_close",
            ),
        ]
    ])


def stream_buttons(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="▷",
                callback_data=f"ctrl_resume|{chat_id}",
            ),
            InlineKeyboardButton(
                text="Ⅱ",
                callback_data=f"ctrl_pause|{chat_id}",
            ),
            InlineKeyboardButton(
                text="↻",
                callback_data=f"ctrl_replay|{chat_id}",
            ),
            InlineKeyboardButton(
                text="‣‣I",
                callback_data=f"ctrl_skip|{chat_id}",
            ),
            InlineKeyboardButton(
                text="■",
                callback_data=f"ctrl_stop|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="♡ Queue",
                callback_data=f"ctrl_queue|{chat_id}",
            ),
            InlineKeyboardButton(
                text="✖ Close",
                callback_data="ctrl_close",
            ),
        ],
    ])


def queue_buttons(chat_id: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                text="▷ Resume",
                callback_data=f"ctrl_resume|{chat_id}",
            ),
            InlineKeyboardButton(
                text="Ⅱ Pause",
                callback_data=f"ctrl_pause|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="‣‣I Skip",
                callback_data=f"ctrl_skip|{chat_id}",
            ),
            InlineKeyboardButton(
                text="■ Stop",
                callback_data=f"ctrl_stop|{chat_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text="✖ Close",
                callback_data="ctrl_close",
            )
        ],
    ])
```
