import asyncio
import logging

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality, Update
from pytgcalls.types.stream import StreamEnded

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

        self._register_handlers()

    def _register_handlers(self):
        @self.calls.on_update()
        async def on_update(_, update: Update):
            if isinstance(update, StreamEnded):
                chat_id = update.chat_id
                LOGGER.info("Stream ended in chat %s → playing next", chat_id)
                await self.play_next(chat_id)

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
        if not isinstance(track, dict):
            raise TypeError("Track must be a dictionary.")

        url = track.get("url")
        if not url:
            raise ValueError("Track has no playable stream URL.")

        media_type = str(track.get("media_type", "audio")).lower()

        if media_type == "video":
            return MediaStream(
                url,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
            )

        return MediaStream(
            url,
            audio_parameters=AudioQuality.HIGH,
            video_flags=MediaStream.Flags.IGNORE,
        )

    async def play_next(self, chat_id: int):
        async with self.lock_for(chat_id):
            next_track = await music_queue.get_next(chat_id)

            if not next_track:
                LOGGER.info("Queue empty in %s → leaving VC", chat_id)
                try:
                    await self.calls.leave_call(chat_id)
                except Exception:
                    pass
                await music_queue.clear(chat_id)
                return

            try:
                await self.calls.play(
                    chat_id,
                    self.make_media(next_track),
                )
                await music_queue.set_current(chat_id, next_track)
                LOGGER.info(
                    "Auto-playing next: %s",
                    next_track.get("title", "Unknown"),
                )
            except Exception:
                LOGGER.exception("Failed to auto-play next in %s", chat_id)
                await music_queue.set_current(chat_id, None)
                try:
                    await self.calls.leave_call(chat_id)
                except Exception:
                    pass

    async def play(self, chat_id, track, media_type="audio"):
        await self.start()

        if not isinstance(track, dict):
            raise TypeError("Track must be a dictionary.")

        item = dict(track)
        item["media_type"] = (
            "video" if str(media_type).lower() == "video" else "audio"
        )

        if not item.get("url"):
            raise ValueError("Track has no playable stream URL.")

        async with self.lock_for(chat_id):
            current = await music_queue.get_current(chat_id)

            if current:
                position = await music_queue.add(chat_id, item)
                LOGGER.info(
                    "Track queued in %s at position %s",
                    chat_id,
                    position,
                )
                return "queued"

            try:
                await self.calls.play(
                    chat_id,
                    self.make_media(item),
                )
            except Exception:
                LOGGER.exception("Failed to start playback in %s", chat_id)
                await music_queue.set_current(chat_id, None)
                raise

            await music_queue.set_current(chat_id, item)

        LOGGER.info(
            "%s started in %s: %s",
            item["media_type"].upper(),
            chat_id,
            item.get("title", "Unknown"),
        )
        return "playing"

    async def pause(self, chat_id):
        await self.start()
        async with self.lock_for(chat_id):
            if not await music_queue.get_current(chat_id):
                return False
            await self.calls.pause(chat_id)
            await music_queue.set_paused(chat_id, True)
        return True

    async def resume(self, chat_id):
        await self.start()
        async with self.lock_for(chat_id):
            if not await music_queue.get_current(chat_id):
                return False
            await self.calls.resume(chat_id)
            await music_queue.set_paused(chat_id, False)
        return True

    async def skip(self, chat_id):
        await self.start()
        await self.play_next(chat_id)
        return await music_queue.get_current(chat_id)

    async def stop(self, chat_id):
        await self.start()
        async with self.lock_for(chat_id):
            try:
                await self.calls.leave_call(chat_id)
            except Exception:
                pass
            await music_queue.clear(chat_id)
        return True

    async def replay(self, chat_id):
        await self.start()
        async with self.lock_for(chat_id):
            track = await music_queue.get_current(chat_id)
            if not track:
                return None
            try:
                await self.calls.play(chat_id, self.make_media(track))
            except Exception:
                LOGGER.exception("Replay failed in %s", chat_id)
                raise
            return track

    async def shutdown(self):
        async with self._shutdown_lock:
            if not self.started:
                return
            LOGGER.info("Shutting down music stream...")
            self.started = False


def setup_stream(assistant: Client):
    return MusicStream(assistant)
