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

        if len(clones) > MAX_CLONES:
            LOGGER.warning(
                "Found %s active clones. Only %s will be started.",
                len(clones),
                MAX_CLONES,
            )

        started = 0

        for clone in clones[:MAX_CLONES]:
            try:
                result = await self.start_clone(clone)

                if result:
                    started += 1

            except Exception:
                LOGGER.exception("Could not start a saved clone.")

        LOGGER.info(
            "Clone startup completed: %s/%s started.",
            started,
            min(len(clones), MAX_CLONES),
        )

    async def start_clone(self, clone):
        token = clone.get("bot_token")

        if not token:
            LOGGER.warning("Skipping clone with missing token.")
            return False

        if token in self.clients_by_token:
            return True

        if len(self.clients) >= MAX_CLONES:
            LOGGER.warning("Maximum clone limit reached.")
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
            await client.start()

            me = await client.get_me()

            register_handlers(
                client,
                self.stream,
                self.assistant,
                include_clone=False,
            )

            self.clients.append(client)
            self.clients_by_token[token] = client

            LOGGER.info(
                "Clone started successfully: @%s",
                me.username or me.id,
            )

            return True

        except Exception:
            LOGGER.exception("Clone startup failed.")

            try:
                if client.is_connected:
                    await client.stop()
            except Exception:
                LOGGER.exception("Failed to stop an unsuccessful clone.")

            return False

    async def stop_all(self):
        for client in reversed(self.clients):
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


clone_manager = CloneManager()
