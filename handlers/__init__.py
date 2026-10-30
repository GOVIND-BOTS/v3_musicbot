from .start import register_start_handlers
from .play import register_play_handlers
from .callbacks import register_callback_handlers
from .queue import register_queue_handlers
from .admin import register_admin_handlers


def register_handlers(app, stream, assistant):
    register_start_handlers(app)
    register_play_handlers(app, stream, assistant)
    register_callback_handlers(app, stream)
    register_queue_handlers(app, stream)
    register_admin_handlers(app, stream)
