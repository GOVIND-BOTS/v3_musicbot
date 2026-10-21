from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def stream_buttons(chat_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="▷", callback_data=f"ctrl_resume|{chat_id}"),
            InlineKeyboardButton(text="II", callback_data=f"ctrl_pause|{chat_id}"),
            InlineKeyboardButton(text="↻", callback_data=f"ctrl_replay|{chat_id}"),
            InlineKeyboardButton(text="‣‣I", callback_data=f"ctrl_skip|{chat_id}"),
            InlineKeyboardButton(text="▢", callback_data=f"ctrl_stop|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="♡ Queue", callback_data=f"ctrl_queue|{chat_id}"),
            InlineKeyboardButton(text="♡ Close", callback_data="ctrl_close"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def queue_buttons(chat_id: int) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="▷ Resume", callback_data=f"ctrl_resume|{chat_id}"),
            InlineKeyboardButton(text="II Pause", callback_data=f"ctrl_pause|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="‣‣I Skip", callback_data=f"ctrl_skip|{chat_id}"),
            InlineKeyboardButton(text="▢ Stop", callback_data=f"ctrl_stop|{chat_id}"),
        ],
        [
            InlineKeyboardButton(text="♡ Close", callback_data="ctrl_close"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def start_buttons(owner_id: int, support: str, bot_username: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="➕ Add me to Group",
                url=f"https://t.me/{bot_username}?startgroup=true"
            ),
        ],
        [
            InlineKeyboardButton(text="👤 Owner", user_id=owner_id),
            InlineKeyboardButton(text="💬 Support", url=support),
        ],
        [
            InlineKeyboardButton(text="📢 Channel", url=support),
            InlineKeyboardButton(text="🆘 Help", callback_data="help_cmd"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)


def help_buttons() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="🏠 Home", callback_data="start_home"),
            InlineKeyboardButton(text="♡ Close", callback_data="ctrl_close"),
        ],
    ]
    return InlineKeyboardMarkup(buttons)
