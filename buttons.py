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
