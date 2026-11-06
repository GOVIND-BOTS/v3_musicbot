import hashlib
import logging

from pyrogram import Client
from config import API_ID, API_HASH
from database.clone_db import get_all_clones, MAX_CLONES

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

        started = 0

        for clone in clones[:MAX_CLONES]:
            try:
                if await self.start_clone(clone):
                    started += 1
            except Exception:
                LOGGER.exception("Failed to start saved clone.")

        LOGGER.info(
            "Clone startup completed: %s/%s",
            started,
            min(len(clones), MAX_CLONES),
        )

    async def start_clone(self, clone: dict) -> bool:
        token = (clone or {}).get("bot_token")

        if not token:
            LOGGER.warning("Clone token missing.")
            return False

        if token in self.clients_by_token:
            return True

        if len(self.clients) >= MAX_CLONES:
            LOGGER.warning("Maximum clone limit reached.")
            return False

        if self.stream is None or self.assistant is None:
            LOGGER.error("Stream or assistant not initialized.")
            return False

        token_hash = hashlib.sha256(
            token.encode()
        ).hexdigest()[:12]

        client = Client(
            f"v3_clone_{token_hash}",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=token,
            in_memory=True,
        )

        try:
            from handlers import register_handlers

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

            LOGGER.info(
                "Clone started: @%s",
                me.username or me.id,
            )

            return True

        except Exception:
            LOGGER.exception("Clone startup failed.")

            try:
                if client.is_connected:
                    await client.stop()
            except Exception:
                LOGGER.exception("Clone cleanup failed.")

            return False

    async def stop_clone(self, bot_token: str) -> bool:
        client = self.clients_by_token.get(bot_token)

        if not client:
            return False

        try:
            if client.is_connected:
                await client.stop()

        except Exception:
            LOGGER.exception("Failed to stop clone.")
            return False

        self.clients_by_token.pop(bot_token, None)

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

                    LOGGER.info(
                        "Clone stopped: @%s",
                        me.username or me.id,
                    )

            except Exception:
                LOGGER.exception("Clone shutdown failed.")

        self.clients.clear()
        self.clients_by_token.clear()

        LOGGER.info("All cloned bots stopped.")


clone_manager = CloneManager()
