import asyncio
import logging

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    Update,
)
from pytgcalls.types.stream import StreamEnded

from music import music_queue


LOGGER = logging.getLogger(__name__)


class MusicStream:

    def __init__(self, assistant: Client):
        self.assistant = assistant
        self.calls = PyTgCalls(assistant)

        self.locks = {}
        self.player_messages = {}

        self.started = False
        self._start_lock = asyncio.Lock()

        self._register_handlers()

    # -----------------------------------------
    # EVENT HANDLER
    # -----------------------------------------

    def _register_handlers(self):

        @self.calls.on_update()
        async def stream_update(_, update: Update):

            if isinstance(update, StreamEnded):
                chat_id = update.chat_id

                LOGGER.info(
                    "Stream ended in chat %s",
                    chat_id,
                )

                await self.play_next(chat_id)

    # -----------------------------------------
    # CHAT LOCK
    # -----------------------------------------

    def lock_for(self, chat_id):

        if chat_id not in self.locks:
            self.locks[chat_id] = asyncio.Lock()

        return self.locks[chat_id]

    # -----------------------------------------
    # START PYTGCALLS
    # -----------------------------------------

    async def start(self):

        async with self._start_lock:

            if self.started:
                return

            await self.calls.start()

            self.started = True

            LOGGER.info(
                "PyTgCalls started successfully."
            )

    # -----------------------------------------
    # MEDIA STREAM
    # -----------------------------------------

    def make_media(self, track):

        if not isinstance(track, dict):
            raise TypeError(
                "Track must be a dictionary."
            )

        url = (
            track.get("url")
            or track.get("webpage_url")
        )

        if not url:
            raise ValueError(
                "Track has no playable URL."
            )

        media_type = str(
            track.get("media_type", "audio")
        ).lower()

        if media_type == "video":

            return MediaStream(
                url,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
            )

        return MediaStream(
            url,
            audio_parameters=AudioQuality.HIGH,
        )

    # -----------------------------------------
    # PLAY NEXT TRACK
    # -----------------------------------------

    async def play_next(
        self,
        chat_id: int,
        skip_current=False,
    ):

        await self.start()

        async with self.lock_for(chat_id):

            attempts = (
                await music_queue.queue_length(chat_id)
            ) + 2

            while attempts > 0:

                attempts -= 1

                track = await music_queue.get_next(
                    chat_id,
                    skip_current=skip_current,
                )

                skip_current = False

                if not track:

                    LOGGER.info(
                        "Queue finished in chat %s",
                        chat_id,
                    )

                    try:
                        await self.calls.leave_call(
                            chat_id
                        )

                    except Exception:
                        LOGGER.debug(
                            "Voice chat already stopped: %s",
                            chat_id,
                        )

                    await music_queue.clear(chat_id)

                    self.player_messages.pop(
                        chat_id,
                        None,
                    )

                    return None

                try:

                    await self.calls.play(
                        chat_id,
                        self.make_media(track),
                    )

                    await music_queue.set_current(
                        chat_id,
                        track,
                    )

                    LOGGER.info(
                        "Now playing in %s: %s",
                        chat_id,
                        track.get("title", "Unknown"),
                    )

                    return track

                except Exception:

                    LOGGER.exception(
                        "Track playback failed in chat %s",
                        chat_id,
                    )

                    await music_queue.set_current(
                        chat_id,
                        None,
                    )

            try:
                await self.calls.leave_call(chat_id)

            except Exception:
                pass

            await music_queue.clear(chat_id)

            self.player_messages.pop(
                chat_id,
                None,
            )

            return None

    # -----------------------------------------
    # PLAY TRACK
    # -----------------------------------------

    async def play(
        self,
        chat_id,
        track,
        media_type="audio",
    ):

        await self.start()

        if not isinstance(track, dict):
            raise TypeError(
                "Track must be a dictionary."
            )

        item = dict(track)

        item["media_type"] = (
            "video"
            if str(media_type).lower() == "video"
            else "audio"
        )

        if not (
            item.get("url")
            or item.get("webpage_url")
        ):
            raise ValueError(
                "Track has no playable URL."
            )

        async with self.lock_for(chat_id):

            current = await music_queue.get_current(
                chat_id
            )

            if current:

                position = await music_queue.add(
                    chat_id,
                    item,
                )

                LOGGER.info(
                    "Track added to queue: %s",
                    position,
                )

                return "queued"

            await self.calls.play(
                chat_id,
                self.make_media(item),
            )

            await music_queue.set_current(
                chat_id,
                item,
            )

        LOGGER.info(
            "%s playback started in %s",
            item["media_type"].upper(),
            chat_id,
        )

        return "playing"

    # -----------------------------------------
    # PAUSE
    # -----------------------------------------

    async def pause(self, chat_id):

        await self.start()

        async with self.lock_for(chat_id):

            current = await music_queue.get_current(
                chat_id
            )

            if not current:
                return False

            await self.calls.pause(chat_id)

            await music_queue.set_paused(
                chat_id,
                True,
            )

            return True

    # -----------------------------------------
    # RESUME
    # -----------------------------------------

    async def resume(self, chat_id):

        await self.start()

        async with self.lock_for(chat_id):

            current = await music_queue.get_current(
                chat_id
            )

            if not current:
                return False

            await self.calls.resume(chat_id)

            await music_queue.set_paused(
                chat_id,
                False,
            )

            return True

    # -----------------------------------------
    # SKIP
    # -----------------------------------------

    async def skip(self, chat_id):

        return await self.play_next(
            chat_id,
            skip_current=True,
        )

    # -----------------------------------------
    # STOP
    # -----------------------------------------

    async def stop(self, chat_id):

        await self.start()

        async with self.lock_for(chat_id):

            try:
                await self.calls.leave_call(
                    chat_id
                )

            except Exception:
                LOGGER.debug(
                    "Could not leave voice chat: %s",
                    chat_id,
                )

            await music_queue.clear(chat_id)

            self.player_messages.pop(
                chat_id,
                None,
            )

            return True

    # -----------------------------------------
    # REPLAY
    # -----------------------------------------

    async def replay(self, chat_id):

        await self.start()

        async with self.lock_for(chat_id):

            track = await music_queue.get_current(
                chat_id
            )

            if not track:
                return None

            await self.calls.play(
                chat_id,
                self.make_media(track),
            )

            return track

    # -----------------------------------------
    # SHUTDOWN
    # -----------------------------------------

    async def shutdown(self):

        if not self.started:
            return

        LOGGER.info(
            "Stopping PyTgCalls..."
        )

        try:
            await self.calls.stop()

        except Exception:
            LOGGER.exception(
                "PyTgCalls shutdown failed."
            )

        self.started = False


# ---------------------------------------------
# STREAM SETUP
# ---------------------------------------------

def setup_stream(assistant: Client):

    return MusicStream(assistant)
