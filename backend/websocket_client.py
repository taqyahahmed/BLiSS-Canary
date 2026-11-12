
"""
CANARY WebSocket Client
-----------------------
Connects the CANARY backend to the hardware team's WebSocket server.

The backend is the CLIENT.
The hardware team's system hosts the SERVER.

This module:
1. Connects to the configured WebSocket URL.
2. Receives incoming messages.
3. Passes raw messages to a callback for parsing.
4. Automatically attempts to reconnect if the connection drops.

Parsing and validation are handled by separate modules.
"""

import asyncio
import inspect
import logging

import websockets
from websockets.exceptions import ConnectionClosed

from backend.config import (
    WEBSOCKET_URL,
    WEBSOCKET_TIMEOUT,
    WEBSOCKET_RECONNECT_DELAY,
)


# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# WebSocket Client
# ---------------------------------------------------------

class WebSocketClient:

    def __init__(
        self,
        url=WEBSOCKET_URL,
        reconnect_delay=WEBSOCKET_RECONNECT_DELAY,
        connection_timeout=WEBSOCKET_TIMEOUT,
    ):
        self.url = url
        self.reconnect_delay = reconnect_delay
        self.connection_timeout = connection_timeout

        if not self.url.startswith(("ws://", "wss://")):
            raise ValueError(
                "WebSocket URL must begin with ws:// or wss://."
            )

        if self.reconnect_delay < 0:
            raise ValueError("Reconnect delay cannot be negative.")

        if self.connection_timeout <= 0:
            raise ValueError("Connection timeout must be positive.")

        self.connected = False

    # -----------------------------------------------------
    # Connect and receive messages
    # -----------------------------------------------------

    async def run(self, on_message):
        """
        Connect to the hardware WebSocket server and continuously
        receive incoming messages.

        Parameters
        ----------
        on_message:
            Function called whenever a message is received.

            It receives the raw WebSocket message.
            It can be either synchronous or asynchronous.
        """

        logger.info("Starting CANARY WebSocket client.")
        logger.info("Target server: %s", self.url)

        while True:

            try:
                logger.info("Attempting WebSocket connection...")

                async with websockets.connect(
                    self.url,
                    open_timeout=self.connection_timeout,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=10 * 1024 * 1024,
                ) as websocket:

                    self.connected = True

                    logger.info(
                        "Connected to hardware WebSocket server."
                    )

                    # Receive messages continuously.
                    async for raw_message in websocket:

                        try:
                            result = on_message(raw_message)

                            # Support asynchronous and synchronous callbacks.
                            if inspect.isawaitable(result):
                                await result

                        except Exception:
                            logger.exception(
                                "Error processing received message."
                            )

            except ConnectionClosed as error:

                logger.warning(
                    "WebSocket connection closed: %s",
                    error
                )

            except (OSError, asyncio.TimeoutError) as error:

                logger.warning(
                    "Unable to connect to WebSocket server: %s",
                    error
                )

            except Exception:

                logger.exception(
                    "Unexpected WebSocket client error."
                )

            finally:

                self.connected = False

            logger.info(
                "Reconnecting in %s seconds...",
                self.reconnect_delay
            )

            await asyncio.sleep(self.reconnect_delay)
