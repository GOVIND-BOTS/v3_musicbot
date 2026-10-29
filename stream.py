
import asyncio
import logging

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls import filters as fl
from pytgcalls.types import (
    MediaStream,
    AudioQuality,
    VideoQuality,
    StreamEnded,
)

from music import music_queue

LOGGER = logging.getLogger(__name__)


class MusicStream:
    def __init__(self, assistant: Client):
        self.assistant = assistant
        self.calls = PyTgCalls(assistant)
        self.locks = {}
        self.started = False
        self._handler_registered = False

    def lock_for(self, chat_id):
        if chat_id not in self.locks:
            self.locks[chat_id] = asyncio.Lock()
        return self.locks[chat_id]

    async def start(self):
        if self.started:
            return

        await self.calls.start()
        self.started = True

        if not self._handler_registered:

            @self.calls.on_update(fl.stream_end())
            async def on_stream_end(_, update: StreamEnded):
                chat_id = update.chat_id

                try:
                    async with self.lock_for(chat_id):
                        next_track = await music_queue.get_next(chat_id)

                        if next_track:
                            await self.calls.play(
                                chat_id,
                                self.make_media(next_track),
                            )
                            await music_queue.set_current(
                                chat_id, next_track
                            )
                        else:
                            try:
                                await self.calls.leave_call(chat_id)
                            except Exception:
                                LOGGER.exception(
                                    "Failed to leave call: %s",
                                    chat_id,
                                )
                            finally:
                                await music_queue.set_current(chat_id, None)

                except Exception:
                    LOGGER.exception(
                        "Stream end handler failed for %s",
                        chat_id,
                    )

            self._handler_registered = True

    def make_media(self, track):
        url = track.get("url") or track.get("webpage_url")

        if not url:
            raise ValueError("Track has no playable URL.")

        media_type = track.get("media_type", "audio")

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

    async def play(self, chat_id, track, media_type="audio"):
        await self.start()

        item = dict(track)
        item["media_type"] = media_type

        if not (item.get("url") or item.get("webpage_url")):
            raise ValueError("Track has no playable stream URL.")

        async with self.lock_for(chat_id):
            current = await music_queue.get_current(chat_id)

            if current:
                await music_queue.add(chat_id, item)
                return "queued"

            await self.calls.play(
                chat_id,
                self.make_media(item),
            )
            await music_queue.set_current(chat_id, item)

        return "playing"

    async def pause(self, chat_id):
        await self.calls.pause_stream(chat_id)
        return "paused"

    async def resume(self, chat_id):
        await self.calls.resume_stream(chat_id)
        return "resumed"

    async def skip(self, chat_id):
        async with self.lock_for(chat_id):
            next_track = await music_queue.get_next(chat_id)

            if next_track:
                await self.calls.play(
                    chat_id,
                    self.make_media(next_track),
                )
                await music_queue.set_current(chat_id, next_track)
                return "skipped"

            try:
                await self.calls.leave_call(chat_id)
            except Exception:
                LOGGER.exception("Failed to leave call: %s", chat_id)
            finally:
                await music_queue.set_current(chat_id, None)

            return "empty"

    async def stop(self, chat_id):
        async with self.lock_for(chat_id):
            try:
                await self.calls.leave_call(chat_id)
            except Exception:
                LOGGER.exception(
                    "Failed to stop stream in chat %s",
                    chat_id,
                )
            finally:
                await music_queue.set_current(chat_id, None)

            return "stopped"

    async def replay(self, chat_id):
        async with self.lock_for(chat_id):
            current = await music_queue.get_current(chat_id)

            if not current:
                return "empty"

            await self.calls.play(
                chat_id,
                self.make_media(current),
            )

            return "playing"

    async def shutdown(self):
        if not self.started:
            return

        LOGGER.info("Shutting down music stream...")

        try:
            for chat_id in list(self.locks.keys()):
                try:
                    await self.calls.leave_call(chat_id)
                except Exception:
                    LOGGER.exception(
                        "Failed to clean up chat %s",
                        chat_id,
                    )
                finally:
                    try:
                        await music_queue.set_current(chat_id, None)
                    except Exception:
                        LOGGER.exception(
                            "Failed to clear queue for chat %s",
                            chat_id,
                        )
        finally:
            self.started = False
            LOGGER.info("Music stream shutdown completed.")


def setup_stream(assistant: Client) -> MusicStream:
    return MusicStream(assistant)
