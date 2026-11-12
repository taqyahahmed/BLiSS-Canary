
"""
CANARY Sliding Window Manager
-----------------------------
Maintains independent rolling windows for each sensor.

Raw samples are retained with timestamps.
Each sensor has its own sampling frequency and therefore
its own expected number of samples per window.

Example:
    ECG: 250 Hz * 5 seconds = 1250 samples
    PPG:  50 Hz * 5 seconds =  250 samples

Windows advance according to WINDOW_UPDATE_INTERVAL_SECONDS.
"""

from collections import deque
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from backend.config import (
    SENSOR_SAMPLING_RATES,
    WINDOW_DURATION_SECONDS,
    WINDOW_UPDATE_INTERVAL_SECONDS,
)


class SensorWindow:
    """Rolling sample window for one sensor."""

    def __init__(
        self,
        sensor_name: str,
        sampling_rate_hz: float,
        duration_seconds: float,
        update_interval_seconds: float,
    ):
        if sampling_rate_hz <= 0:
            raise ValueError("Sampling rate must be positive.")

        if duration_seconds <= 0:
            raise ValueError("Window duration must be positive.")

        if update_interval_seconds <= 0:
            raise ValueError("Update interval must be positive.")

        if update_interval_seconds > duration_seconds:
            raise ValueError(
                "Update interval cannot exceed window duration."
            )

        self.sensor_name = sensor_name
        self.sampling_rate_hz = float(sampling_rate_hz)
        self.duration_seconds = float(duration_seconds)
        self.update_interval_seconds = float(update_interval_seconds)

        self.max_samples = max(
            1,
            round(self.sampling_rate_hz * self.duration_seconds)
        )

        self.samples = deque(maxlen=self.max_samples)

        self.last_emission_time = None
        self.lock = RLock()

    def add_sample(
        self,
        value: Any,
        timestamp: float,
    ) -> None:
        """
        Add one timestamped sample.

        timestamp is expected to be Unix time in seconds.
        """

        if not isinstance(timestamp, (int, float)):
            raise TypeError("Timestamp must be numeric.")

        with self.lock:
            self.samples.append({
                "timestamp": float(timestamp),
                "value": value,
            })

    def add_samples(
        self,
        values: list,
        start_timestamp: float,
    ) -> None:
        """
        Add a batch of samples.

        Sample timestamps are reconstructed using the configured
        sampling frequency when individual timestamps are absent.

        start_timestamp represents the time of the first sample.
        """

        if not isinstance(start_timestamp, (int, float)):
            raise TypeError("Start timestamp must be numeric.")

        if not values:
            return

        interval = 1.0 / self.sampling_rate_hz

        with self.lock:
            for index, value in enumerate(values):
                timestamp = start_timestamp + index * interval

                self.samples.append({
                    "timestamp": timestamp,
                    "value": value,
                })

    def get_samples(self) -> list:
        """Return a snapshot of the current window."""

        with self.lock:
            return list(self.samples)

    def get_values(self) -> list:
        """Return only the sample values."""

        with self.lock:
            return [
                sample["value"]
                for sample in self.samples
            ]

    def is_full(self) -> bool:
        """Check whether the window contains its expected sample count."""

        with self.lock:
            return len(self.samples) >= self.max_samples

    def should_emit(self, current_time: float) -> bool:
        """
        Determine whether enough time has passed to emit another window.

        The first window is emitted once it is full.
        Subsequent windows are emitted at the configured update interval.
        """

        with self.lock:
            if not self.is_full():
                return False

            if self.last_emission_time is None:
                self.last_emission_time = current_time
                return True

            elapsed = current_time - self.last_emission_time

            if elapsed >= self.update_interval_seconds:
                self.last_emission_time = current_time
                return True

            return False

    def get_window(self) -> dict:
        """Return the current window and its metadata."""

        with self.lock:
            samples = list(self.samples)

            if not samples:
                return {
                    "sensor": self.sensor_name,
                    "sampling_rate_hz": self.sampling_rate_hz,
                    "duration_seconds": self.duration_seconds,
                    "sample_count": 0,
                    "expected_sample_count": self.max_samples,
                    "is_full": False,
                    "start_timestamp": None,
                    "end_timestamp": None,
                    "samples": [],
                }

            return {
                "sensor": self.sensor_name,
                "sampling_rate_hz": self.sampling_rate_hz,
                "duration_seconds": self.duration_seconds,
                "sample_count": len(samples),
                "expected_sample_count": self.max_samples,
                "is_full": len(samples) >= self.max_samples,
                "start_timestamp": samples[0]["timestamp"],
                "end_timestamp": samples[-1]["timestamp"],
                "samples": samples,
            }

    def clear(self) -> None:
        """Clear the window."""

        with self.lock:
            self.samples.clear()
            self.last_emission_time = None


class WindowManager:
    """
    Manages independent sliding windows for all configured sensors.
    """

    def __init__(
        self,
        sampling_rates=None,
        duration_seconds=WINDOW_DURATION_SECONDS,
        update_interval_seconds=WINDOW_UPDATE_INTERVAL_SECONDS,
    ):

        self.sampling_rates = (
            sampling_rates
            if sampling_rates is not None
            else SENSOR_SAMPLING_RATES
        )

        self.duration_seconds = duration_seconds
        self.update_interval_seconds = update_interval_seconds

        self.windows = {}

        for sensor_name, sampling_rate in self.sampling_rates.items():

            self.windows[sensor_name] = SensorWindow(
                sensor_name=sensor_name,
                sampling_rate_hz=sampling_rate,
                duration_seconds=duration_seconds,
                update_interval_seconds=update_interval_seconds,
            )

    def add_sample(
        self,
        sensor_name: str,
        value: Any,
        timestamp: float,
    ) -> None:
        """Add one sample to the specified sensor window."""

        if sensor_name not in self.windows:
            raise ValueError(
                f"Unknown sensor: {sensor_name}"
            )

        self.windows[sensor_name].add_sample(
            value=value,
            timestamp=timestamp,
        )

    def add_samples(
        self,
        sensor_name: str,
        values: list,
        start_timestamp: float,
    ) -> None:
        """Add a batch of samples to the specified sensor window."""

        if sensor_name not in self.windows:
            raise ValueError(
                f"Unknown sensor: {sensor_name}"
            )

        self.windows[sensor_name].add_samples(
            values=values,
            start_timestamp=start_timestamp,
        )

    def get_window(self, sensor_name: str) -> dict:
        """Get one sensor's current window."""

        if sensor_name not in self.windows:
            raise ValueError(
                f"Unknown sensor: {sensor_name}"
            )

        return self.windows[sensor_name].get_window()

    def get_all_windows(self) -> dict:
        """Get snapshots of every sensor's current window."""

        return {
            sensor_name: window.get_window()
            for sensor_name, window in self.windows.items()
        }

    def get_ready_windows(
        self,
        current_time: float | None = None,
    ) -> dict:
        """
        Return windows ready for processing.

        Each sensor is checked independently, so one sensor
        does not need to block another sensor's processing.
        """

        if current_time is None:
            current_time = datetime.now(timezone.utc).timestamp()

        ready = {}

        for sensor_name, window in self.windows.items():

            if window.should_emit(current_time):
                ready[sensor_name] = window.get_window()

        return ready

    def clear_all(self) -> None:
        """Clear all sensor windows."""

        for window in self.windows.values():
            window.clear()
