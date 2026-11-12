
"""
CANARY main application.

Connects to the hardware WebSocket server and coordinates:
1. Message parsing
2. Sensor data validation
3. Raw waveform storage
4. Independent sensor sliding windows
5. Window-based feature processing
6. InfluxDB storage
7. Reporting-tier management
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

from backend.config import (
    WEBSOCKET_URL,
    WEBSOCKET_RECONNECT_DELAY,
    WEBSOCKET_TIMEOUT,
    SENSOR_SAMPLING_RATES,
)

from backend.websocket_client import WebSocketClient
from backend.data_parser import parse_message
from backend.validation import validate_batch, ValidationError
from backend.windowing import WindowManager
from backend.processing import process_ready_windows
from backend.database import create_client, write_batch
from backend.tier_logic import TierManager


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("CANARY")


def to_timestamp(value):
    """Convert supported timestamps to Unix seconds."""

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    if isinstance(value, str):
        normalized = value.strip()

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        parsed = datetime.fromisoformat(normalized)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.timestamp()

    raise ValueError(f"Unsupported timestamp: {value!r}")


def get_sensor_samples(payload):
    """Extract samples from an individual or batched sensor payload."""

    if not isinstance(payload, dict):
        return []

    if "samples" in payload:
        samples = payload["samples"]
        return samples if isinstance(samples, list) else []

    if "value" in payload:
        return [payload["value"]]

    if any(axis in payload for axis in ("x", "y", "z")):
        return [{
            axis: payload[axis]
            for axis in ("x", "y", "z")
            if axis in payload
        }]

    return []


def get_sample_value(sample):
    """Extract the measurement while preserving nested sensor data."""

    if isinstance(sample, dict) and "value" in sample:
        return sample["value"]

    return sample


def get_sample_timestamp(
    sample,
    batch_timestamp,
    sample_index,
    sampling_rate,
):
    """Preserve hardware timestamps or reconstruct them from sampling rate."""

    if isinstance(sample, dict) and sample.get("timestamp") is not None:
        return to_timestamp(sample["timestamp"])

    if sampling_rate and sampling_rate > 0:
        return batch_timestamp + sample_index / sampling_rate

    return batch_timestamp


class CanaryPipeline:
    """Coordinates all CANARY backend processing components."""

    def __init__(
        self,
        database_client,
        waveform_manager=None,
        window_manager=None,
        tier_manager=None,
        database_writer=None,
    ):
        self.database_client = database_client

        self.waveforms = waveform_manager or WaveformManager()
        self.windows = window_manager or WindowManager()
        self.tiers = tier_manager or TierManager()

        self.database_writer = database_writer or write_batch

        self.last_report_time = time.monotonic()
        self.message_count = 0
        self.invalid_batch_count = 0

    async def handle_message(self, raw_message):
        """Parse, validate, and process one incoming hardware message."""

        try:
            batch = parse_message(raw_message)
            validate_batch(batch)

        except (ValidationError, ValueError, TypeError) as error:
            self.invalid_batch_count += 1
            logger.warning("Invalid sensor batch: %s", error)
            return

        except Exception:
            self.invalid_batch_count += 1
            logger.exception("Could not parse incoming message.")
            return

        try:
            self._process_valid_batch(batch)

        except Exception:
            logger.exception("Error processing sensor batch.")
            return

        self.message_count += 1

    def _process_valid_batch(self, batch):
        """Process timestamped samples from all available sensors."""

        batch_timestamp = to_timestamp(
            batch.get("timestamp") or batch.get("received_at")
        )

        sensor_data = batch.get("sensor_data", {})

        for sensor_name, payload in sensor_data.items():

            if not isinstance(payload, dict):
                continue

            # Use the hardware sampling rate when provided.
            # Otherwise, fall back to the configured sensor rate.
            sampling_rate = payload.get(
                "sampling_rate_hz",
                SENSOR_SAMPLING_RATES.get(sensor_name),
            )

            if (
                not isinstance(sampling_rate, (int, float))
                or isinstance(sampling_rate, bool)
                or sampling_rate <= 0
            ):
                sampling_rate = None

            # Extract samples and calculate timestamps ONCE.
            samples = get_sensor_samples(payload)

            timestamped_samples = []

            for index, sample in enumerate(samples):

                value = get_sample_value(sample)

                timestamp = get_sample_timestamp(
                    sample,
                    batch_timestamp,
                    index,
                    sampling_rate,
                )

                timestamped_samples.append({
                    "value": value,
                    "timestamp": timestamp,
                })

            # Prepare a normalized payload for waveform storage.
            waveform_payload = {
                "sampling_rate_hz": sampling_rate,
                "unit": payload.get("unit"),
                "samples": timestamped_samples,
            }

            # 1. Store raw waveform samples.
            # These timestamps are the same ones used below.
            if timestamped_samples:
                self.waveforms.ingest_sensor_payload(
                    sensor_name,
                    waveform_payload,
                    batch_timestamp,
                )

            # 2. Add the exact same samples to sliding windows.
            for sample in timestamped_samples:

                self.windows.add_sample(
                    sensor_name,
                    sample["value"],
                    sample["timestamp"],
                )

        # 3. Retrieve windows ready for processing.
        ready_windows = self.windows.get_ready_windows()

        # 4. Calculate features from ready windows.
        features = {}

        if ready_windows:
            features = process_ready_windows(ready_windows)

            logger.info(
                "Processed features for sensors: %s",
                list(features.keys()),
            )

        # 5. Persist raw samples and processed features.
        self.database_writer(
            self.database_client,
            batch,
            features,
        )

        # 6. Update reporting tier and check reporting schedule.
        self.tiers.update()

        self._check_reporting_schedule(batch)

    def _check_reporting_schedule(self, batch):
        """Print a report when the current tier's interval has elapsed."""

        now = time.monotonic()
        interval = self.tiers.get_reporting_interval()

        if now - self.last_report_time >= interval:

            status = self.tiers.get_status()

            logger.info(
                "\n--- CANARY REPORT ---\n"
                "Device: %s\n"
                "Timestamp: %s\n"
                "Messages received: %s\n"
                "Current tier: %s\n"
                "Reporting interval: %s seconds\n"
                "Active alerts: %s\n"
                "---------------------",
                batch["device_id"],
                batch.get("timestamp"),
                self.message_count + 1,
                status["current_tier"],
                status["reporting_interval_seconds"],
                status["active_alerts"],
            )

            self.last_report_time = now


async def main():
    """Start the CANARY hardware monitoring application."""

    logger.info("Starting CANARY monitoring system.")
    logger.info("Hardware WebSocket target: %s", WEBSOCKET_URL)

    database_client = create_client()

    pipeline = CanaryPipeline(
        database_client=database_client,
    )

    websocket_client = WebSocketClient(
        url=WEBSOCKET_URL,
        reconnect_delay=WEBSOCKET_RECONNECT_DELAY,
        connection_timeout=WEBSOCKET_TIMEOUT,
    )

    logger.info("CANARY backend initialized.")
    logger.info("Waiting for hardware sensor messages...")
    logger.info("Press Ctrl+C to stop.")

    try:
        await websocket_client.run(pipeline.handle_message)

    except KeyboardInterrupt:
        logger.info("Stopping CANARY monitoring system.")

    finally:
        database_client.close()
        logger.info("Database connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
