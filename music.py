import asyncio
import random
from collections import defaultdict, deque
from copy import deepcopy


class MusicQueue:
    """Per-chat queue with repeat and shuffle support."""

    LOOP_MODES = {"off", "track", "queue"}

    def __init__(self):
        self._queues = defaultdict(deque)
        self._current = {}
        self._paused = set()
        self._loop_modes = defaultdict(lambda: "off")
        self._shuffle = defaultdict(bool)
        self._locks = defaultdict(asyncio.Lock)

    def _lock(self, chat_id):
        return self._locks[chat_id]

    def _prepare_track(self, track):
        if not isinstance(track, dict):
            raise TypeError("Track must be a dictionary.")

        if not track.get("url") and not track.get("webpage_url"):
            raise ValueError("Track must contain a playable URL.")

        item = dict(track)
        item.setdefault("title", "Unknown Title")
        item.setdefault("media_type", "audio")
        item.setdefault("requested_by_id", 0)
        item.setdefault("requested_by_name", "Group member")
        item.setdefault("requested_by_username", "")
        item.setdefault("duration_text", "Unknown")
        item.setdefault("is_live", False)
        return item

    async def add(self, chat_id, track):
        item = self._prepare_track(track)
        async with self._lock(chat_id):
            self._queues[chat_id].append(item)
            return len(self._queues[chat_id])

    async def add_many(self, chat_id, tracks):
        items = [self._prepare_track(track) for track in tracks]
        async with self._lock(chat_id):
            self._queues[chat_id].extend(items)
            if self._shuffle[chat_id]:
                shuffled = list(self._queues[chat_id])
                random.shuffle(shuffled)
                self._queues[chat_id] = deque(shuffled)
            return len(self._queues[chat_id])

    async def set_current(self, chat_id, track):
        async with self._lock(chat_id):
            if track is None:
                self._current.pop(chat_id, None)
                self._paused.discard(chat_id)
                return
            self._current[chat_id] = self._prepare_track(track)
            self._paused.discard(chat_id)

    async def get_current(self, chat_id):
        async with self._lock(chat_id):
            item = self._current.get(chat_id)
            return deepcopy(item) if item is not None else None

    async def get_next(self, chat_id, skip_current=False):
        """
        Return the next track.

        skip_current=False is used by StreamEnded:
          - track mode repeats the current track
          - queue mode appends current track to the queue
        skip_current=True is used by manual Skip:
          - never repeats the current track immediately
          - queue mode still cycles it to the end
        """
        async with self._lock(chat_id):
            current = self._current.get(chat_id)
            mode = self._loop_modes[chat_id]
            queue = self._queues[chat_id]

            if current and mode == "track" and not skip_current:
                self._paused.discard(chat_id)
                return deepcopy(current)

            if current and mode == "queue":
                queue.append(deepcopy(current))

            if not queue:
                self._current.pop(chat_id, None)
                self._paused.discard(chat_id)
                return None

            item = queue.popleft()
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
            self._loop_modes[chat_id] = "off"
            self._shuffle[chat_id] = False

    async def clear_upcoming(self, chat_id):
        async with self._lock(chat_id):
            self._queues[chat_id].clear()

    async def queue_length(self, chat_id):
        async with self._lock(chat_id):
            return len(self._queues[chat_id])

    async def remove(self, chat_id, position):
        """Remove a 1-based position from the upcoming queue."""
        async with self._lock(chat_id):
            if position < 1 or position > len(self._queues[chat_id]):
                return None
            items = list(self._queues[chat_id])
            removed = items.pop(position - 1)
            self._queues[chat_id] = deque(items)
            return deepcopy(removed)

    async def shuffle(self, chat_id, enabled=None):
        async with self._lock(chat_id):
            if enabled is None:
                enabled = not self._shuffle[chat_id]
            self._shuffle[chat_id] = bool(enabled)

            if enabled:
                items = list(self._queues[chat_id])
                random.shuffle(items)
                self._queues[chat_id] = deque(items)

            return self._shuffle[chat_id]

    async def is_shuffle(self, chat_id):
        async with self._lock(chat_id):
            return self._shuffle[chat_id]

    async def set_loop(self, chat_id, mode):
        mode = str(mode or "off").lower().strip()
        if mode not in self.LOOP_MODES:
            raise ValueError(
                "Invalid loop mode. Use: off, track, or queue."
            )
        async with self._lock(chat_id):
            self._loop_modes[chat_id] = mode
            return mode

    async def get_loop(self, chat_id):
        async with self._lock(chat_id):
            return self._loop_modes[chat_id]

    async def cycle_loop(self, chat_id):
        order = ("off", "track", "queue")
        async with self._lock(chat_id):
            current = self._loop_modes[chat_id]
            next_mode = order[(order.index(current) + 1) % len(order)]
            self._loop_modes[chat_id] = next_mode
            return next_mode

    async def set_paused(self, chat_id, paused):
        async with self._lock(chat_id):
            if paused:
                self._paused.add(chat_id)
            else:
                self._paused.discard(chat_id)

    async def is_paused(self, chat_id):
        async with self._lock(chat_id):
            return chat_id in self._paused


music_queue = MusicQueue()


async def add_to_queue(chat_id, track):
    return await music_queue.add(chat_id, track)


async def get_next_track(chat_id):
    return await music_queue.get_next(chat_id)


async def get_current_track(chat_id):
    return await music_queue.get_current(chat_id)


async def get_queue(chat_id):
    return await music_queue.get_queue(chat_id)


async def clear_queue(chat_id):
    return await music_queue.clear(chat_id)


async def skip_track(chat_id):
    return await music_queue.get_next(chat_id, skip_current=True)
