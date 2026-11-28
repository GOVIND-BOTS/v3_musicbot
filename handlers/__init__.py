from .start import register_start_handlers
from .play import register_play_handlers
from .callbacks import register_callback_handlers
from .queue import register_queue_handlers
from .settings import register_settings_handlers
from .admin import register_admin_handlers
from .welcome import register_welcome_handlers
from .chatbot import register_chatbot_handlers
from .adisa import register_adisa_handlers
from .tagall import register_tagall_handlers
from .translate import register_translate_handlers
from .whisper import register_whisper_handlers
from .student_protection import register_handlers as register_student_protection
from .clone import register_clone_handlers
from .logo import register_logo_handlers
from .anti_abuse import register_anti_abuse_handlers
from .eval import register_eval
from .bio_guard import register_bio_guard_handlers
from .editor import register_editor_handlers
from .video_downloader import register_video_downloader_handlers
from .media_conversion import register_media_conversion_handlers
from .owner_control import register_owner_control_handlers
from .profile_dp import register_profile_dp_handlers
from .bin_lookup import register_bin_handlers
from .couples import register_couples_handlers
from .string_session import register_string_session_handlers
from .loveraid import register_loveraid_handlers
from .insta import register_insta_handlers
from .phone import register_phone_handlers

from .tools.ping import register_ping_handlers
from .tools.reload import register_reload_handlers
from .tools.speedtest import register_speedtest_handlers
from .tools.active import register_active_handlers
from .tools.status import register_status_handlers


def register_handlers(app, stream, assistant, include_clone=True):
    register_start_handlers(app)
    register_string_session_handlers(app)
    register_owner_control_handlers(app)
    register_profile_dp_handlers(app)
    register_phone_handlers(app)

    register_ping_handlers(app)
    register_reload_handlers(app)
    register_speedtest_handlers(app)
    register_active_handlers(app)
    register_status_handlers(app)

    register_play_handlers(app, stream, assistant)
    register_callback_handlers(app, stream)
    register_queue_handlers(app, stream)
    register_settings_handlers(app)

    register_admin_handlers(app, stream)
    register_welcome_handlers(app)
    register_chatbot_handlers(app)
    register_adisa_handlers(app)
    register_tagall_handlers(app)
    register_translate_handlers(app)
    register_whisper_handlers(app)
    register_bin_handlers(app)
    register_couples_handlers(app)
    register_loveraid_handlers(app)
    register_insta_handlers(app)

    register_student_protection(app)
    register_bio_guard_handlers(app, assistant)

    if include_clone:
        register_clone_handlers(app)

    register_logo_handlers(app)
    register_anti_abuse_handlers(app)
    register_eval(app)
    register_editor_handlers(app)
    register_video_downloader_handlers(app)
    register_media_conversion_handlers(app)
