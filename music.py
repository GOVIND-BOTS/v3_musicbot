import asyncio
from collections import defaultdict, deque
from copy import deepcopy

class MusicQueue:
    def __init__(self):
        self._queues = defaultdict(deque)
        self._current = {}
        self._paused = set()
        self._locks = defaultdict(asyncio.Lock)

    def _prepare_track(self, track):
        if not isinstance(track, dict):
            raise TypeError("Track must be a dictionary.")
        if not track.get("url") and not track.get("webpage_url"):
            raise ValueError("Track must contain a URL.")
        item = dict(track)
        item.setdefault("title", "Unknown Title")
        item.setdefault("media_type", "audio")
        return item

    def _lock(self, chat_id):
        return self._locks[chat_id]

    async def add(self, chat_id, track):
        item = self._prepare_track(track)
        async with self._lock(chat_id):
            self._queues[chat_id].append(item)
            return len(self._queues[chat_id])

    async def add_many(self, chat_id, tracks):
        items = [self._prepare_track(t) for t in tracks]
        async with self._lock(chat_id):
            self._queues[chat_id].extend(items)
            return len(self._queues[chat_id])

    async def set_current(self, chat_id, track):
        async with self._lock(chat_id):
            self._current[chat_id] = self._prepare_track(track)
            self._paused.discard(chat_id)

    async def get_current(self, chat_id):
        async with self._lock(chat_id):
            value = self._current.get(chat_id)
            return deepcopy(value) if value else None

    async def get_next(self, chat_id):
        async with self._lock(chat_id):
            if not self._queues[chat_id]:
                self._current.pop(chat_id, None)
                self._paused.discard(chat_id)
                return None
            item = self._queues[chat_id].popleft()
            self._current[chat_id] = item
            self._paused.discard(chat_id)
            return deepcopy(item)

    async def get_queue(self, chat_id):
        async with self._lock(chat_id):
            return deepcopy(list(self._queues[chat_id]))

    async def clear(self, chat_id):
        async with self._lock(chat_id):
            self._queues[chat_id].clear()
            self._current.pop(chat_id, None)
            self._paused.discard(chat_id)

    async def queue_length(self, chat_id):
        async with self._lock(chat_id):
            return len(self._queues[chat_id])

    async def set_paused(self, chat_id, paused):
        async with self._lock(chat_id):
            self._paused.add(chat_id) if paused else self._paused.discard(chat_id)

    async def is_paused(self, chat_id):
        async with self._lock(chat_id):
            return chat_id in self._paused

music_queue = MusicQueue()
async def add_to_queue(chat_id, track): return await music_queue.add(chat_id, track)
async def get_next_track(chat_id): return await music_queue.get_next(chat_id)
async def get_current_track(chat_id): return await music_queue.get_current(chat_id)
async def get_queue(chat_id): return await music_queue.get_queue(chat_id)
async def clear_queue(chat_id): return await music_queue.clear(chat_id)
async def skip_track(chat_id): return await music_queue.get_next(chat_id)
