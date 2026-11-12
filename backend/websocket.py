import asyncio
import json
import logging
import math
import os
import statistics
import time

from datetime import datetime, timezone

import websockets


# --------------------------------------------------
# Configuration
# --------------------------------------------------

WEBSOCKET_URL = os.getenv(
    "CANARY_WEBSOCKET_URL",
    "ws://localhost:8000/ws/sensors"
)

DEVICE_ID = "CANARY_001"

BATCH_INTERVAL = 0.1  # 100 ms = 10 batches per second

RECONNECT_DELAY = 5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("canary.websocket")


# --------------------------------------------------
# Sensor sample buffer
# --------------------------------------------------

class BatchBuffer:

    def __init__(self):
        self.samples = {}

    def add_sample(self, sensor, value):
        if isinstance(value, bool):
            raise ValueError("Sensor values must be numeric.")

        value = float(value)

        if not math.isfinite(value):
            raise ValueError("Sensor values must be finite.")

        self.samples.setdefault(sensor, []).append(value)

    def create_batch(self, sequence_number, window_start, window_end):

        raw_samples = self.samples.copy()
        self.samples.clear()

        summaries = {}

        for sensor, values in raw_samples.items():

            if not values:
                continue

            summaries[sensor] = {
                "mean": statistics.mean(values),
                "minimum": min(values),
                "maximum": max(values),
                "std": (
                    statistics.pstdev(values)
                    if len(values) > 1
                    else 0.0
                ),
                "sample_count": len(values)
            }

        return {
            "type": "batch",
            "device_id": DEVICE_ID,
            "sequence_number": sequence_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "window_start": window_start,
            "window_end": window_end,
            "window_duration_seconds": BATCH_INTERVAL,
            "input_frequency_hz": 1 / BATCH_INTERVAL,
            "samples": raw_samples,
            "summary": summaries
        }


# --------------------------------------------------
# WebSocket transmission
# --------------------------------------------------

async def transmit_batches(sample_queue):

    sequence_number = 0

    while True:

        try:
            logger.info("Connecting to %s", WEBSOCKET_URL)

            async with websockets.connect(WEBSOCKET_URL) as websocket:

                logger.info("WebSocket connected.")

                while True:

                    window_start = datetime.now(timezone.utc).isoformat()
                    start_time = time.monotonic()

                    buffer = BatchBuffer()

                    # Collect samples for one fixed time window.
                    while True:

                        elapsed = time.monotonic() - start_time
                        remaining = BATCH_INTERVAL - elapsed

                        if remaining <= 0:
                            break

                        try:
                            sample = await asyncio.wait_for(
                                sample_queue.get(),
                                timeout=remaining
                            )

                            buffer.add_sample(
                                sample["sensor"],
                                sample["value"]
                            )

                        except asyncio.TimeoutError:
                            break

                    window_end = datetime.now(timezone.utc).isoformat()

                    sequence_number += 1

                    batch = buffer.create_batch(
                        sequence_number,
                        window_start,
                        window_end
                    )

                    await websocket.send(json.dumps(batch))

                    response = json.loads(await websocket.recv())

                    if response.get("type") == "ack":
                        logger.info(
                            "Batch %s acknowledged.",
                            sequence_number
                        )
                    else:
                        logger.warning(
                            "Unexpected server response: %s",
                            response
                        )

        except (OSError, websockets.ConnectionClosed) as error:

            logger.warning("WebSocket connection lost: %s", error)

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception("Unexpected WebSocket sender error.")

        logger.info("Reconnecting in %s seconds.", RECONNECT_DELAY)
        await asyncio.sleep(RECONNECT_DELAY)


# --------------------------------------------------
# Synthetic test data
# --------------------------------------------------

async def generate_test_samples(sample_queue):

    sensor_rates = {
        "ecg": 250,
        "ppg": 50,
        "bioimpedance": 25,
        "accel_x": 50,
        "accel_y": 50,
        "accel_z": 50,
        "temperature": 1
    }

    sensor_values = {
        "ecg": 0.12,
        "ppg": 0.42,
        "bioimpedance": 502.0,
        "accel_x": -0.88,
        "accel_y": 2.02,
        "accel_z": 9.91,
        "temperature": 26.18
    }

    tasks = []

    async def generate_sensor_samples(sensor, rate, value):

        interval = 1 / rate

        while True:

            await sample_queue.put({
                "sensor": sensor,
                "value": value
            })

            await asyncio.sleep(interval)

    for sensor, rate in sensor_rates.items():

        tasks.append(
            asyncio.create_task(
                generate_sensor_samples(
                    sensor,
                    rate,
                    sensor_values[sensor]
                )
            )
        )

    await asyncio.gather(*tasks)


# --------------------------------------------------
# Main
# --------------------------------------------------

async def main():

    sample_queue = asyncio.Queue()

    await asyncio.gather(
        transmit_batches(sample_queue),
        generate_test_samples(sample_queue)
    )


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print("\nCANARY WebSocket sender stopped.")