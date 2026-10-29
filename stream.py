import asyncio
import logging
from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream, AudioQuality, VideoQuality
from pytgcalls import filters as fl
from pytgcalls.types import StreamEnded

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
            # Auto next track jab song khatam ho
            @self.calls.on_update(fl.stream_end())
            async def on_stream_end(_, update: StreamEnded):
                chat_id = update.chat_id
                try:
                    next_track = await music_queue.get_next(chat_id)
                    if next_track:
                        await self.calls.play(chat_id, self.make_media(next_track))
                        await music_queue.set_current(chat_id, next_track)
                    else:
                        try:
                            await self.calls.leave_call(chat_id)
                        except Exception:
                            pass
                except Exception:
                    LOGGER.exception("Stream end handler failed for %s", chat_id)

    def make_media(self, track):
        # Prefer YouTube URL (best reliability)
        url = track.get("webpage_url") or track.get("url")
        if not url:
            raise ValueError("Track has no playable URL.")

        media_type = track.get("media_type", "audio")

        if media_type == "video":
            return MediaStream(
                url,
                audio_parameters=AudioQuality.HIGH,
                video_parameters=VideoQuality.SD_480p,
            )
        # Audio only
        return MediaStream(
            url,
            audio_parameters=AudioQuality.HIGH,
            video_flags=MediaStream.Flags.IGNORE,   # important
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

            await self.calls.play(chat_id, self.make_media(item))
            await music_queue.set_current(chat_id, item)
        return "playing"

    # ... baaki methods (pause/resume/skip/stop/replay) same rehne do
