
from html import escape

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from player_ui import stylize, format_duration, progress_button_text
from config import MAIN_OWNER_ID


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


def help_buttons(page=0):
    """Return the central, paginated command-help keyboard."""
    return command_help_keyboard(page)


def stream_buttons(
    chat_id: int,
    elapsed=0,
    duration=0,
    loop_mode="off",
    shuffle=False,
    owner_url=None,
    more_open=False,
):
    loop_label = "ON" if str(loop_mode).lower() not in ("off", "none", "false", "0") else "OFF"
    shuffle_label = "ON" if shuffle else "OFF"
    progress_text = progress_button_text(elapsed, duration)

    rows = [
        [
            InlineKeyboardButton(
                progress_text,
                callback_data=f"ctrl_progress|{chat_id}",
            ),
        ],
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
    ]

    if more_open:
        rows.extend([
            [
                InlineKeyboardButton(
                    stylize(f"🔁 LOOP: {loop_label}"),
                    callback_data=f"ctrl_loop|{chat_id}",
                ),
                InlineKeyboardButton(
                    stylize(f"🔀 SHUFFLE: {shuffle_label}"),
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
            [
                InlineKeyboardButton(
                    stylize("🖼 CHANGE THUMBNAIL"),
                    callback_data=f"thumb_change|{chat_id}",
                ),
                InlineKeyboardButton(
                    stylize("👑 OWNER"),
                    url=owner_url or f"tg://user?id={MAIN_OWNER_ID}",
                ),
            ],
            [
                InlineKeyboardButton(
                    stylize("➖ LESS"),
                    callback_data=f"ctrl_more|{chat_id}|0",
                ),
            ],
        ])
    else:
        rows.append([
            InlineKeyboardButton(
                stylize("➕ MORE"),
                callback_data=f"ctrl_more|{chat_id}|1",
            ),
        ])

    return InlineKeyboardMarkup(rows)


def queue_buttons(
    chat_id: int,
    loop_mode="off",
    shuffle=False,
):
    loop_label = "ON" if str(loop_mode).lower() not in ("off", "none", "false", "0") else "OFF"
    shuffle_label = "ON" if shuffle else "OFF"

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
                stylize(f"🔁 LOOP: {loop_label}"),
                callback_data=f"ctrl_loop|{chat_id}",
            ),
            InlineKeyboardButton(
                stylize(f"🔀 SHUFFLE: {shuffle_label}"),
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



HELP_COMMANDS = {
    "genstring": ("🔐 String Session Generator", "Owner Tools", "/genstring", "Generate Pyrogram or Telegram (Telethon) user/bot string sessions in a private guided login flow. OTP and 2FA messages are deleted after processing; generated sessions are secret.", "Available to all users in private chat. Use only accounts/bots you own; the session is sent only to your own chat and must never be shared.", "/genstring"),
    "start": ("🚀 Start", "General", "/start", "Open the bot welcome panel and main navigation.", "Private chat or group.", "/start"),
    "help": ("🆘 Help", "General", "/help", "Open the interactive command directory. Every command has its own help button.", "Anyone.", "/help"),
    "play": ("🎵 Play", "Music", "/play <song name or link>", "Search and stream audio in the group's voice chat.", "Group; bot and assistant must have voice-chat access.", "/play Arijit Singh"),
    "vplay": ("🎬 Video Play", "Music", "/vplay <song name or link>", "Search and stream video in the voice chat.", "Group; video streaming support and permissions required.", "/vplay Kesariya"),
    "joinuserbot": ("👤 Join Assistant", "Music", "/joinuserbot", "Ask the assistant account to join the current group/call when supported.", "Group admin may need to add the assistant.", "/joinuserbot"),
    "pause": ("⏸ Pause", "Music", "/pause", "Pause the current voice-chat stream.", "Group admin or authorized user.", "/pause"),
    "resume": ("▶️ Resume", "Music", "/resume", "Resume a paused voice-chat stream.", "Group admin or authorized user.", "/resume"),
    "skip": ("⏭ Skip", "Music", "skip (or adisha skip / baby skip)", "Skip the currently playing track and continue the queue. This handler uses a text trigger, not /skip.", "Group admin.", "skip"),
    "stop": ("⏹ Stop", "Music", "/stop", "Stop playback and clear the active queue.", "Group admin or authorized user.", "/stop"),
    "queue": ("📜 Queue", "Music", "/queue", "Show tracks waiting in the current group queue.", "Group.", "/queue"),
    "now": ("🎧 Now Playing", "Music", "/now", "Show the currently playing track and its details.", "Group.", "/now"),
    "loop": ("🔁 Loop", "Music", "/loop [count]", "Toggle or set repeat mode for the current track/queue.", "Group admin or authorized user.", "/loop 3"),
    "shuffle": ("🔀 Shuffle", "Music", "/shuffle", "Shuffle the pending tracks in the queue.", "Group admin or authorized user.", "/shuffle"),
    "remove": ("➖ Remove Track", "Music", "/remove <queue number>", "Remove a selected track from the queue.", "Group admin or authorized user.", "/remove 2"),
    "clearqueue": ("🧹 Clear Queue", "Music", "/clearqueue", "Remove all pending tracks from the queue.", "Group admin or authorized user.", "/clearqueue"),
    "settings": ("⚙️ Settings", "Music", "/settings", "Open group playback and music settings.", "Group admin.", "/settings"),
    "authadd": ("➕ Add Auth User", "Music", "/authadd <user id>", "Allow a trusted user to use restricted music controls.", "Group admin.", "/authadd 123456789"),
    "authremove": ("➖ Remove Auth", "Music", "/authremove <user id>", "Remove a user from the authorized music-user list.", "Group admin.", "/authremove 123456789"),
    "authlist": ("👥 Auth List", "Music", "/authlist", "Show users currently authorized in this group.", "Group admin.", "/authlist"),
    "clone": ("🧬 Clone Bot", "Clone", "/clone <bot token>", "Connect a Telegram bot token as a personal clone.", "Private chat; use only a bot token you own.", "/clone YOUR_BOT_TOKEN"),
    "clones": ("📋 My Clones", "Clone", "/clones", "List clone bots connected to your account.", "Private chat.", "/clones"),
    "removeclone": ("🗑 Remove Clone", "Clone", "/removeclone <bot username>", "Disconnect one of your connected clone bots.", "Private chat.", "/removeclone @your_bot"),
    "cancel": ("✖ Cancel", "General", "/cancel", "Cancel a supported ongoing clone/tagging operation.", "Where the operation is active.", "/cancel"),
    "tagall": ("📣 Tag All", "Group Tools", "/tagall [message]", "Mention group members in batches. Aliases: /all and /tagmember.", "Group; follow Telegram rate limits.", "/tagall Meeting starts now"),
    "all": ("📣 All", "Group Tools", "/all [message]", "Alias of /tagall.", "Group.", "/all Hello everyone"),
    "tagmember": ("👥 Tag Members", "Group Tools", "/tagmember [message]", "Alias of /tagall.", "Group.", "/tagmember Hello"),
    "tr": ("🌐 Translate", "Utilities", "/tr <text>", "Translate the supplied text using the configured translation service.", "Private chat or group.", "/tr Hello, how are you?"),
    "adisa": ("💬 Adisa", "Chatbot", "adisa <message>", "Use the Adisa conversational trigger. Aliases: disa and disha.", "Send as a normal message; prefix may be optional.", "adisa kaise ho"),
    "disa": ("💬 Disa", "Chatbot", "disa <message>", "Alias of the Adisa conversational trigger.", "Normal message.", "disa hello"),
    "disha": ("💬 Disha", "Chatbot", "disha <message>", "Alias of the Adisa conversational trigger.", "Normal message.", "disha hello"),
    "chatbot": ("🤖 Chatbot Toggle", "Chatbot", "/chatbot on|off", "Enable or disable the Vick-style group chatbot.", "Group admin; MongoDB chatbot collections must be configured.", "/chatbot on"),
    "antigali": ("🛡 Anti-Abuse", "Protection", "/antigali", "Open abusive-word protection settings for this group.", "Group admin.", "/antigali"),
    "galiadd": ("➕ Add Blocked Word", "Protection", "/galiadd <word>", "Add a word or phrase to the group's blocked-word list.", "Group admin.", "/galiadd example"),
    "galidel": ("➖ Delete Blocked Word", "Protection", "/galidel <word>", "Remove a word or phrase from the blocked-word list.", "Group admin.", "/galidel example"),
    "galiwords": ("📃 Blocked Words", "Protection", "/galiwords", "List blocked words configured for the group.", "Group admin.", "/galiwords"),
    "resetwarn": ("♻️ Reset Abuse Warns", "Protection", "/resetwarn <user reply or id>", "Reset anti-abuse warning count for a member.", "Group admin.", "/resetwarn 123456789"),
    "rules": ("📜 Group Rules", "Protection", "/rules", "Show the group's student-protection rules and warning policy.", "Group.", "/rules"),
    "warns": ("⚠️ My Warnings", "Protection", "/warns", "Show your current moderation warning count.", "Group.", "/warns"),
    "resetwarns": ("♻️ Reset Warnings", "Protection", "/resetwarns <user reply or id>", "Reset moderation warnings for a member.", "Group admin.", "/resetwarns 123456789"),
    "checkbio": ("🔎 Check Bio", "Protection", "/checkbio [reply to user]", "Check the target member's bio for group/channel promotion links when Telegram exposes that bio.", "Group; assistant session and required permissions.", "/checkbio"),
    "vdownload": ("⬇️ Video Download", "Downloader", "/vdownload <video URL>", "Download a public video link supported by yt-dlp. Supported links may also auto-download when posted.", "Private chat or group; public, non-DRM content only.", "/vdownload https://example.com/video"),
    "edit": ("🎞 Edit Media", "Editor", "/edit (reply to photo/video)", "Open the media editor for a replied-to photo or video. Aliases: /photoedit and /videoedit.", "Reply to supported media.", "/edit"),
    "photoedit": ("🖼 Photo Edit", "Editor", "/photoedit (reply to photo)", "Open the editor for a replied-to photo.", "Reply to a photo.", "/photoedit"),
    "videoedit": ("🎬 Video Edit", "Editor", "/videoedit (reply to video)", "Open the editor for a replied-to video.", "Reply to a video.", "/videoedit"),
    "photo2video": ("🪄 Photo to Video", "Editor", "/photo2video", "Start creating a video from uploaded photos.", "Follow the prompts in chat.", "/photo2video"),
    "timeline": ("🎬 Timeline", "Editor", "/timeline", "Start a multi-photo/video timeline editing session.", "Upload media and follow the prompts.", "/timeline"),
    "timeline_music": ("🎵 Timeline Music", "Editor", "/timeline_music <audio or URL>", "Add background music to the active timeline project.", "An active timeline project.", "/timeline_music"),
    "timeline_order": ("🔢 Timeline Order", "Editor", "/timeline_order 3,1,2", "Set the order of uploaded timeline clips.", "An active timeline project.", "/timeline_order 2,1,3"),
    "timeline_duration": ("⏱ Clip Duration", "Editor", "/timeline_duration 1=5", "Set clip duration or trim ranges in the timeline.", "An active timeline project.", "/timeline_duration 1=5 2=3-12"),
    "timeline_done": ("✅ Finish Timeline", "Editor", "/timeline_done", "Render the active timeline project.", "An active timeline project.", "/timeline_done"),
    "timeline_cancel": ("✖ Cancel Timeline", "Editor", "/timeline_cancel", "Cancel and clear the active timeline project.", "An active timeline project.", "/timeline_cancel"),
    "edithelp": ("❔ Editor Help", "Editor", "/edithelp", "Show supported editor operations, quality options and workflow.", "Anyone.", "/edithelp"),
    "logo": ("✨ Logo Maker", "Creative", "/logo [style] <text>", "Generate a logo. Use /logo list to view styles; supported styles include neon, gold and gaming.", "Private chat or group.", "/logo neon Govind"),
    "owner": ("👑 Public Owner", "Owner", "/owner", "Show the profile linked by the owner button on the playing panel.", "Anyone.", "/owner"),
    "setowner": ("⚙️ Set Public Owner", "Owner", "/setowner @username|user_id|default", "Change the public owner button target or restore the secure main owner.", "Immutable MAIN_OWNER_ID only; SUDO users cannot change it.", "/setowner @username"),
    "eval": ("🧪 Safe Eval", "Owner", "/eval <python expression>", "Run the restricted safe test evaluator. Alias: /test.", "Bot owner only; this is not unrestricted Python execution.", "/eval print('Hello')"),
    "test": ("🧪 Test", "Owner", "/test <expression>", "Alias of the restricted safe evaluator.", "Bot owner only.", "/test 2 + 2"),
    "whisper": ("🔒 Whisper", "Inline", "@botusername username message", "Send a private whisper using Telegram inline mode. Supports one-time whisper.", "Enable inline mode with @BotFather; use the bot in any chat.", "@botusername @username Secret message"),
    "welcome": ("👋 Welcome", "Group Tools", "Automatic on member join", "Send a welcome image and owner/support buttons when a new member joins.", "Automatic; bot needs permission to send photos/messages.", "Add a member to the group"),
}


def command_help_text(command):
    item = HELP_COMMANDS.get(command)
    if not item:
        return "Help details are not available for this command."
    title, category, usage, description, permission, example = item
    return (
        f"<b>{title}</b>\n"
        f"<i>Category: {category}</i>\n\n"
        f"<b>Usage</b>\n<code>{escape(usage)}</code>\n\n"
        f"<b>What it does</b>\n{description}\n\n"
        f"<b>Permissions / Notes</b>\n{permission}\n\n"
        f"<b>Example</b>\n<code>{escape(example)}</code>"
    )


def command_help_keyboard(page=0):
    from math import ceil

    keys = list(HELP_COMMANDS)
    page_size = 10
    pages = max(1, ceil(len(keys) / page_size))
    page = max(0, min(int(page), pages - 1))
    selected = keys[page * page_size:(page + 1) * page_size]

    rows = []
    for index in range(0, len(selected), 2):
        row = []
        for key in selected[index:index + 2]:
            row.append(InlineKeyboardButton(
                stylize(HELP_COMMANDS[key][0]),
                callback_data=f"help_item_{key}",
            ))
        rows.append(row)

    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(
            "⬅️ Previous", callback_data=f"help_page_{page - 1}"
        ))
    navigation.append(InlineKeyboardButton(
        f"📖 {page + 1}/{pages}", callback_data="help_page_info"
    ))
    if page < pages - 1:
        navigation.append(InlineKeyboardButton(
            "Next ➡️", callback_data=f"help_page_{page + 1}"
        ))
    rows.append(navigation)
    rows.append([
        InlineKeyboardButton("🏠 Home", callback_data="start_home"),
        InlineKeyboardButton("✖ Close", callback_data="ctrl_close"),
    ])
    return InlineKeyboardMarkup(rows)
