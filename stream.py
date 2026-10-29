
import asyncio
import logging

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality

from music import music_queue


LOGGER = logging.getLogger(__name__)


class MusicStream:
    def __init__(self, assistant: Client):
        self.assistant = assistant
        self.calls = PyTgCalls(assistant)

        self.locks = {}
        self.started = False
        self._start_lock = asyncio.Lock()
        self._shutdown_lock = asyncio.Lock()

    def lock_for(self, chat_id):
        if chat_id not in self.locks:
            self.locks[chat_id] = asyncio.Lock()

        return self.locks[chat_id]

    async def start(self):
        async with self._start_lock:
            if self.started:
                return

            await self.calls.start()
            self.started = True
            LOGGER.info("PyTgCalls started successfully.")

    def make_media(self, track):
        url = track.get("url")

        if not url:
            raise ValueError("Track has no playable stream URL.")

        if track.get("media_type", "audio") == "video":
            return MediaStream(
                url,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
            )

        return MediaStream(
            url,
            audio_parameters=AudioQuality.HIGH,
        )

    async def play(self, chat_id, track, media_type="audio"):
        await self.start()

        item = dict(track)
        item["media_type"] = media_type

        if not item.get("url"):
            raise ValueError("Track has no playable stream URL.")

        async with self.lock_for(chat_id):
            current = await music_queue.get_current(chat_id)

            if current:
                await music_queue.add(chat_id, item)
                LOGGER.info("Track queued in chat %s", chat_id)
                return "queued"

            await self.calls.play(
                chat_id,
                self.make_media(item),
            )

            await music_queue.set_current(chat_id, item)

        LOGGER.info("Playback started in chat %s", chat_id)
        return "playing"

    async def pause(self, chat_id):
        await self.start()

        async with self.lock_for(chat_id):
            await self.calls.pause(chat_id)
            await music_queue.set_paused(chat_id, True)

        LOGGER.info("Playback paused in chat %s", chat_id)

    async def resume(self, chat_id):
        await self.start()

        async with self.lock_for(chat_id):
            await self.calls.resume(chat_id)
            await music_queue.set_paused(chat_id, False)

        LOGGER.info("Playback resumed in chat %s", chat_id)

    async def skip(self, chat_id):
        await self.start()

        async with self.lock_for(chat_id):
            track = await music_queue.get_next(chat_id)

            if not track:
                try:
                    await self.calls.leave_call(chat_id)
                except Exception:
                    LOGGER.info(
                        "No active call to leave in chat %s",
                        chat_id,
                    )

                await music_queue.clear(chat_id)
                return None

            try:
                await self.calls.play(
                    chat_id,
                    self.make_media(track),
                )
            except Exception:
                LOGGER.exception(
                    "Failed to play next track in chat %s",
                    chat_id,
                )
                raise

            await music_queue.set_current(chat_id, track)

            LOGGER.info("Skipped to next track in chat %s", chat_id)
            return track

    async def stop(self, chat_id):
        await self.start()

        async with self.lock_for(chat_id):
            try:
                await self.calls.leave_call(chat_id)
            except Exception:
                LOGGER.info(
                    "No active call to leave in chat %s",
                    chat_id,
                )

            await music_queue.clear(chat_id)

        LOGGER.info("Playback stopped in chat %s", chat_id)

    async def replay(self, chat_id):
        await self.start()

        async with self.lock_for(chat_id):
            track = await music_queue.get_current(chat_id)

            if not track:
                return None

            await self.calls.play(
                chat_id,
                self.make_media(track),
            )

            return track

    async def shutdown(self):
        """
        Graceful shutdown without calling the unsupported
        PyTgCalls.stop() method.
        """
        async with self._shutdown_lock:
            if not self.started:
                return

            LOGGER.info("Shutting down music stream...")

            # Leave active voice chats if possible.
            # PyTgCalls 2.2.11 does not expose .stop().
            try:
                if hasattr(self.calls, "leave_call"):
                    # Active chat IDs are not tracked here.
                    # Individual chats should be stopped by stop(chat_id).
                    pass
            except Exception:
                LOGGER.exception("Error while leaving voice chats")

            self.started = False
            LOGGER.info("Music stream shutdown handler completed.")


def setup_stream(assistant: Client):
    return MusicStream(assistant)
