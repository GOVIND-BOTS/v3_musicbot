
import asyncio
import hashlib
import logging

from pyrogram import Client

from config import API_ID, API_HASH
from database.clone_db import get_all_clones
from handlers import register_handlers


LOGGER = logging.getLogger(__name__)


class CloneManager:

    def __init__(self):
        self.clients = {}
        self._lock = asyncio.Lock()

    async def start_all(self, stream, assistant):

        async with self._lock:

            try:
                clones = await get_all_clones()

            except Exception:
                LOGGER.exception(
                    "Failed to retrieve cloned bots from database."
                )
                return

            if not clones:
                LOGGER.info("No cloned bots found.")
                return

            LOGGER.info(
                "Starting %s cloned bots...",
                len(clones),
            )

            for clone in clones:

                token = clone.get("bot_token")

                if not token:
                    LOGGER.warning(
                        "Skipping clone: Bot token is missing."
                    )
                    continue

                client_id = hashlib.sha256(
                    token.encode()
                ).hexdigest()[:16]

                if client_id in self.clients:
                    continue

                client = Client(
                    name=f"clone_{client_id}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    bot_token=token,
                    in_memory=True,
                )

                started = False

                try:
                    register_handlers(
                        client,
                        stream,
                        assistant,
                        include_clone=False,
                    )

                    await client.start()
                    started = True

                    me = await client.get_me()

                    self.clients[client_id] = client

                    LOGGER.info(
                        "Clone started successfully: @%s",
                        me.username or me.id,
                    )

                except Exception:

                    LOGGER.exception(
                        "Failed to start cloned bot: %s",
                        client_id,
                    )

                    if started:
                        try:
                            await client.stop()

                        except Exception:
                            LOGGER.exception(
                                "Failed to stop clone: %s",
                                client_id,
                            )

            LOGGER.info(
                "Clone startup completed. Active clones: %s",
                len(self.clients),
            )

    async def stop_all(self):

        async with self._lock:

            LOGGER.info("Stopping all cloned bots...")

            for client_id, client in list(
                self.clients.items()
            ):

                try:
                    if client.is_connected:
                        await client.stop()

                    LOGGER.info(
                        "Clone stopped: %s",
                        client_id,
                    )

                except Exception:
                    LOGGER.exception(
                        "Failed to stop clone: %s",
                        client_id,
                    )

            self.clients.clear()

            LOGGER.info("All cloned bots stopped.")


clone_manager = CloneManager()
