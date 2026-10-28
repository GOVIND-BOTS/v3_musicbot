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

    def lock_for(self, chat_id):
        if chat_id not in self.locks:
            self.locks[chat_id] = asyncio.Lock()

        return self.locks[chat_id]

    async def start(self):
        if not self.started:
            await self.calls.start()
            self.started = True

    def make_media(self, track):
        url = track.get("url")

        if not url:
            raise ValueError(
                "Track has no playable stream URL."
            )

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
            raise ValueError(
                "Track has no playable stream URL."
            )

        async with self.lock_for(chat_id):

            current = await music_queue.get_current(chat_id)

            if current:
                await music_queue.add(chat_id, item)
                return "queued"

            await self.calls.play(
                chat_id,
                self.make_media(item)
            )

            await music_queue.set_current(
                chat_id,
                item
            )

        return "playing"

    async def pause(self, chat_id):
        await self.start()

        await self.calls.pause(chat_id)

        await music_queue.set_paused(
            chat_id,
            True
        )

    async def resume(self, chat_id):
        await self.start()

        await self.calls.resume(chat_id)

        await music_queue.set_paused(
            chat_id,
            False
        )

    async def skip(self, chat_id):
        await self.start()

        async with self.lock_for(chat_id):

            track = await music_queue.get_next(
                chat_id
            )

            if not track:
                try:
                    await self.calls.leave_call(
                        chat_id
                    )
                except Exception:
                    LOGGER.info(
                        "No active call for %s",
                        chat_id
                    )

                return None

            await self.calls.play(
                chat_id,
                self.make_media(track)
            )

            await music_queue.set_current(
                chat_id,
                track
            )

            return track

    async def stop(self, chat_id):
        await self.start()

        async with self.lock_for(chat_id):

            try:
                await self.calls.leave_call(
                    chat_id
                )
            except Exception:
                LOGGER.info(
                    "No active call for %s",
                    chat_id
                )

            await music_queue.clear(
                chat_id
            )

    async def replay(self, chat_id):
        await self.start()

        async with self.lock_for(chat_id):

            track = await music_queue.get_current(
                chat_id
            )

            if track:
                await self.calls.play(
                    chat_id,
                    self.make_media(track)
                )

            return track

    async def shutdown(self):
        if not self.started:
            return

        # PyTgCalls 2.2.11 does not expose
        # a .stop() method.
        #
        # The active calls are left individually
        # when needed. Do not call self.calls.stop().
        self.started = False


def setup_stream(assistant):
    return MusicStream(assistant)
