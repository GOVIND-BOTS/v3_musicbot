import hashlib
import logging
from pyrogram import Client
from config import API_ID, API_HASH
from database.clone_db import get_all_clones, MAX_CLONES
from handlers import register_handlers

LOGGER = logging.getLogger(__name__)


class CloneManager:
    def __init__(self):
        self.clients = []
        self.clients_by_token = {}
        self.stream = None
        self.assistant = None

    async def start_all(self, stream, assistant):
        self.stream = stream
        self.assistant = assistant

        clones = await get_all_clones()
        if not clones:
            LOGGER.info("No cloned bots found.")
            return

        if len(clones) > MAX_CLONES:
            LOGGER.warning(
                "Found %s active clones. Only first %s will start.",
                len(clones),
                MAX_CLONES,
            )

        started = 0
        for clone in clones[:MAX_CLONES]:
            try:
                if await self.start_clone(clone):
                    started += 1
            except Exception:
                LOGGER.exception("Could not start a saved clone.")

        LOGGER.info(
            "Clone startup completed: %s/%s started.",
            started,
            min(len(clones), MAX_CLONES),
        )

    async def start_clone(self, clone: dict) -> bool:
        token = (clone or {}).get("bot_token")
        if not token:
            LOGGER.warning("Skipping clone: missing bot_token.")
            return False

        if token in self.clients_by_token:
            LOGGER.info("Clone already running for this token.")
            return True

        if len(self.clients) >= MAX_CLONES:
            LOGGER.warning("Maximum clone limit reached (%s).", MAX_CLONES)
            return False

        if self.stream is None or self.assistant is None:
            LOGGER.error("CloneManager stream/assistant not set. Call start_all first.")
            return False

        token_hash = hashlib.sha256(token.encode()).hexdigest()[:12]
        client = Client(
            f"v3_clone_{token_hash}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=token,
            in_memory=True,
        )

        try:
            # Handlers FIRST, then start
            register_handlers(
                client,
                self.stream,
                self.assistant,
                include_clone=False,
            )

            await client.start()
            me = await client.get_me()

            self.clients.append(client)
            self.clients_by_token[token] = client

            LOGGER.info("Clone started: @%s", me.username or me.id)
            return True

        except Exception:
            LOGGER.exception("Clone startup failed.")
            try:
                if getattr(client, "is_connected", False):
                    await client.stop()
            except Exception:
                pass
            return False

    async def stop_clone(self, bot_token: str) -> bool:
        client = self.clients_by_token.pop(bot_token, None)
        if not client:
            return False

        try:
            if client.is_connected:
                await client.stop()
        except Exception:
            LOGGER.exception("Failed to stop clone.")

        if client in self.clients:
            self.clients.remove(client)
        return True

    async def stop_all(self):
        LOGGER.info("Stopping all cloned bots...")
        for client in reversed(list(self.clients)):
            try:
                if client.is_connected:
                    me = await client.get_me()
                    await client.stop()
                    LOGGER.info("Clone stopped: @%s", me.username or me.id)
            except Exception:
                LOGGER.exception("Clone shutdown failed.")

        self.clients.clear()
        self.clients_by_token.clear()
        LOGGER.info("All cloned bots stopped.")


clone_manager = CloneManager()
