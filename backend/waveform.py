
"""
CANARY Waveform Management
--------------------------
Preserves raw timestamped sensor samples for waveform visualization.

Responsibilities:
1. Store raw samples independently for each sensor.
2. Preserve timestamps and units.
3. Support individual samples and batches.
4. Retrieve waveform data over a requested time range.
5. Limit memory usage through a configurable retention period.

Long-term historical storage is handled separately by database.py.
"""

from collections import deque
from threading import RLock
from datetime import datetime, timezone
from typing import Any
import math

from backend.config import SENSOR_SAMPLING_RATES


# ---------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------

def is_valid_timestamp(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def normalize_timestamp(value):
    """
    Convert supported timestamps into Unix seconds.

    Supports:
        Unix timestamps
        ISO 8601 strings
    """

    if is_valid_timestamp(value):
        return float(value)

    if isinstance(value, str):

        try:
            parsed = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )

            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)

            return parsed.timestamp()

        except ValueError:
            raise ValueError(f"Invalid timestamp: {value}")

    raise ValueError(f"Invalid timestamp: {value}")


# ---------------------------------------------------------
# Individual sensor waveform buffer
# ---------------------------------------------------------

class WaveformBuffer:
    """Stores recent raw samples for one sensor."""

    def __init__(
        self,
        sensor_name: str,
        sampling_rate_hz: float,
        retention_seconds: float = 60,
        unit: str = None,
    ):

        if sampling_rate_hz <= 0:
            raise ValueError("Sampling rate must be positive.")

        if retention_seconds <= 0:
            raise ValueError("Retention duration must be positive.")

        self.sensor_name = sensor_name
        self.sampling_rate_hz = float(sampling_rate_hz)
        self.retention_seconds = float(retention_seconds)
        self.unit = unit

        self.max_samples = max(
            1,
            math.ceil(
                self.sampling_rate_hz * self.retention_seconds
            )
        )

        self.samples = deque(maxlen=self.max_samples)
        self.lock = RLock()

    def add_sample(
        self,
        value: Any,
        timestamp: float,
    ):
        """Store one raw sample with its timestamp."""

        timestamp = normalize_timestamp(timestamp)

        sample = {
            "timestamp": timestamp,
            "value": value,
        }

        with self.lock:

            self.samples.append(sample)

            # Remove samples older than the retention period.
            cutoff = timestamp - self.retention_seconds

            while (
                self.samples
                and self.samples[0]["timestamp"] < cutoff
            ):
                self.samples.popleft()

    def add_samples(
        self,
        values: list,
        start_timestamp: float,
        sampling_rate_hz: float = None,
        timestamps: list = None,
    ):
        """
        Store a batch of raw samples.

        If individual timestamps are supplied, preserve them.
        Otherwise, reconstruct timestamps using the sampling rate.

        start_timestamp refers to the first sample in the batch.
        """

        if not values:
            return

        start_timestamp = normalize_timestamp(start_timestamp)

        rate = (
            float(sampling_rate_hz)
            if sampling_rate_hz is not None
            else self.sampling_rate_hz
        )

        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("Sampling rate must be positive.")

        if timestamps is not None and len(timestamps) != len(values):
            raise ValueError(
                "Number of timestamps must match number of samples."
            )

        interval = 1.0 / rate

        for index, value in enumerate(values):

            if timestamps is not None:
                timestamp = normalize_timestamp(timestamps[index])
            else:
                timestamp = start_timestamp + index * interval

            self.add_sample(
                value=value,
                timestamp=timestamp,
            )

    def get_samples(
        self,
        start_timestamp: float = None,
        end_timestamp: float = None,
    ) -> list:
        """Retrieve samples within an optional time range."""

        if start_timestamp is not None:
            start_timestamp = normalize_timestamp(start_timestamp)

        if end_timestamp is not None:
            end_timestamp = normalize_timestamp(end_timestamp)

        if (
            start_timestamp is not None
            and end_timestamp is not None
            and start_timestamp > end_timestamp
        ):
            raise ValueError("Start timestamp exceeds end timestamp.")

        with self.lock:

            result = []

            for sample in self.samples:

                timestamp = sample["timestamp"]

                if (
                    start_timestamp is not None
                    and timestamp < start_timestamp
                ):
                    continue

                if (
                    end_timestamp is not None
                    and timestamp > end_timestamp
                ):
                    continue

                result.append(sample.copy())

            return result

    def get_waveform(
        self,
        start_timestamp: float = None,
        end_timestamp: float = None,
    ) -> dict:
        """
        Return waveform data in a frontend-friendly structure.

        The frontend can use timestamps as the X-axis
        and values as the Y-axis.
        """

        samples = self.get_samples(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )

        return {
            "sensor": self.sensor_name,
            "sampling_rate_hz": self.sampling_rate_hz,
            "unit": self.unit,
            "sample_count": len(samples),
            "timestamps": [
                sample["timestamp"]
                for sample in samples
            ],
            "values": [
                sample["value"]
                for sample in samples
            ],
        }

    def clear(self):
        """Remove all stored samples."""

        with self.lock:
            self.samples.clear()


# ---------------------------------------------------------
# Manager for all sensor waveforms
# ---------------------------------------------------------

class WaveformManager:
    """
    Manages independent waveform buffers for all sensors.
    """

    def __init__(
        self,
        sampling_rates=None,
        retention_seconds=60,
    ):

        self.sampling_rates = (
            sampling_rates
            if sampling_rates is not None
            else SENSOR_SAMPLING_RATES
        )

        self.retention_seconds = retention_seconds
        self.buffers = {}

        for sensor_name, rate in self.sampling_rates.items():

            self.buffers[sensor_name] = WaveformBuffer(
                sensor_name=sensor_name,
                sampling_rate_hz=rate,
                retention_seconds=retention_seconds,
            )

    def add_sample(
        self,
        sensor_name: str,
        value: Any,
        timestamp: float,
        unit: str = None,
    ):
        """Add one sample to a sensor's waveform buffer."""

        if sensor_name not in self.buffers:
            raise ValueError(f"Unknown sensor: {sensor_name}")

        buffer = self.buffers[sensor_name]

        if unit is not None:
            buffer.unit = unit

        buffer.add_sample(
            value=value,
            timestamp=timestamp,
        )

    def add_samples(
        self,
        sensor_name: str,
        values: list,
        start_timestamp: float,
        sampling_rate_hz: float = None,
        timestamps: list = None,
        unit: str = None,
    ):
        """Add a batch of samples to a sensor's buffer."""

        if sensor_name not in self.buffers:
            raise ValueError(f"Unknown sensor: {sensor_name}")

        buffer = self.buffers[sensor_name]

        if unit is not None:
            buffer.unit = unit

        buffer.add_samples(
            values=values,
            start_timestamp=start_timestamp,
            sampling_rate_hz=sampling_rate_hz,
            timestamps=timestamps,
        )

    def ingest_sensor_payload(
        self,
        sensor_name: str,
        payload: dict,
        fallback_timestamp: float,
    ):
        """
        Accept a sensor payload from the parsed hardware message.

        Supports:

        Batch:
            {
                "sampling_rate_hz": 250,
                "unit": "mV",
                "samples": [0.1, 0.2, 0.3]
            }

        Individual value:
            {
                "value": 36.7,
                "unit": "deg C"
            }

        Individual timestamped samples:
            {
                "samples": [
                    {"timestamp": 1000, "value": 0.1},
                    {"timestamp": 1000.004, "value": 0.2}
                ]
            }
        """

        if sensor_name not in self.buffers:
            raise ValueError(f"Unknown sensor: {sensor_name}")

        if not isinstance(payload, dict):
            raise TypeError("Sensor payload must be a dictionary.")

        rate = payload.get(
            "sampling_rate_hz",
            self.sampling_rates[sensor_name],
        )

        unit = payload.get("unit")

        raw_samples = payload.get("samples")

        if raw_samples is not None:

            if not isinstance(raw_samples, list):
                raise TypeError("Sensor samples must be a list.")

            if not raw_samples:
                return

            # Individual timestamped sample objects.
            if all(
                isinstance(sample, dict)
                and "value" in sample
                for sample in raw_samples
            ):

                values = [
                    sample["value"]
                    for sample in raw_samples
                ]

                timestamps = [
                    sample.get("timestamp")
                    for sample in raw_samples
                ]

                if all(timestamp is not None for timestamp in timestamps):

                    self.add_samples(
                        sensor_name=sensor_name,
                        values=values,
                        start_timestamp=timestamps[0],
                        sampling_rate_hz=rate,
                        timestamps=timestamps,
                        unit=unit,
                    )

                else:
                    self.add_samples(
                        sensor_name=sensor_name,
                        values=values,
                        start_timestamp=fallback_timestamp,
                        sampling_rate_hz=rate,
                        unit=unit,
                    )

            else:

                self.add_samples(
                    sensor_name=sensor_name,
                    values=raw_samples,
                    start_timestamp=payload.get(
                        "timestamp",
                        fallback_timestamp,
                    ),
                    sampling_rate_hz=rate,
                    unit=unit,
                )

        elif "value" in payload:

            self.add_sample(
                sensor_name=sensor_name,
                value=payload["value"],
                timestamp=payload.get(
                    "timestamp",
                    fallback_timestamp,
                ),
                unit=unit,
            )

        else:
            raise ValueError(
                f"No samples or value found for {sensor_name}."
            )

    def get_waveform(
        self,
        sensor_name: str,
        start_timestamp: float = None,
        end_timestamp: float = None,
    ) -> dict:
        """Retrieve one sensor's waveform."""

        if sensor_name not in self.buffers:
            raise ValueError(f"Unknown sensor: {sensor_name}")

        return self.buffers[sensor_name].get_waveform(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )

    def get_all_waveforms(self) -> dict:
        """Retrieve recent waveforms for all sensors."""

        return {
            sensor_name: buffer.get_waveform()
            for sensor_name, buffer in self.buffers.items()
        }

    def clear_all(self):
        """Clear every waveform buffer."""

        for buffer in self.buffers.values():
            buffer.clear()
