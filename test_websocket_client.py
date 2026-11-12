
"""
CANARY WebSocket Client Tests
-----------------------------
Tests the backend WebSocket client against a temporary
local WebSocket server.

No hardware connection is required.
"""

import asyncio
import logging

import websockets

from backend.websocket_client import WebSocketClient


logging.basicConfig(level=logging.INFO)


async def test_websocket_connection():

    received_messages = []
    messages_received = asyncio.Event()

    # -----------------------------------------------------
    # Temporary WebSocket server
    # -----------------------------------------------------

    async def server_handler(websocket):

        print("\nTEST SERVER: Client connected.")

        await websocket.send("message 1")
        await websocket.send("message 2")
        await websocket.send("message 3")

        # Keep the connection open until the client disconnects.
        await websocket.wait_closed()

    async with websockets.serve(
        server_handler,
        "127.0.0.1",
        0
    ) as server:

        # Get the temporary server port.
        port = server.sockets[0].getsockname()[1]

        test_url = f"ws://127.0.0.1:{port}"

        print("\nTEST SERVER URL:", test_url)

        # -------------------------------------------------
        # Create client
        # -------------------------------------------------

        client = WebSocketClient(
            url=test_url,
            reconnect_delay=1,
            connection_timeout=3
        )

        # -------------------------------------------------
        # Message callback
        # -------------------------------------------------

        def on_message(raw_message):

            # Test synchronous callback.
            if raw_message != "message 2":
                received_messages.append(raw_message)

            # Test asynchronous callback.
            else:

                async def process_message():
                    received_messages.append(raw_message)

                return process_message()

            if len(received_messages) == 3:
                messages_received.set()

        # -------------------------------------------------
        # Start client
        # -------------------------------------------------

        client_task = asyncio.create_task(
            client.run(on_message)
        )

        try:

            # Wait until all three messages arrive.
            await asyncio.wait_for(
                messages_received.wait(),
                timeout=5
            )

            print("\nTEST 1: WebSocket connection")
            assert client.connected is True
            print("PASSED")

            print("\nTEST 2: Message reception")
            assert received_messages == [
                "message 1",
                "message 2",
                "message 3"
            ]

            for message in received_messages:
                print("Received:", message)

            print("PASSED")

            print("\nTEST 3: Synchronous and asynchronous callbacks")
            assert len(received_messages) == 3
            print("PASSED")

        finally:

            # Stop the client cleanly.
            client_task.cancel()

            try:
                await client_task
            except asyncio.CancelledError:
                pass

            print("\nClient disconnected.")

    print("\nALL WEBSOCKET TESTS PASSED!")


# ---------------------------------------------------------
# Run tests
# ---------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(test_websocket_connection())
