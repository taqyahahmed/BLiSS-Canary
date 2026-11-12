
"""
CANARY Data Parser
------------------
Purpose:
    Convert incoming hardware messages into one consistent internal format.

Supported inputs:
    1. JSON messages (provisional hardware format)
    2. Existing line-based sensor text format:
       Temperature 26.18 deg C
       Accel X: -0.88 Y: 2.02 Z: 9.91 m/s^2
       Mag X: -20.85 Y: 22.95 Z: 92.85 uT
       Gyro X: 0.03 Y: -0.02 Z: 0.01 radians/s

This file normalizes data. Validation and signal processing happen elsewhere.
"""

import copy
import json
import re

from datetime import datetime, timezone
from typing import Any, Optional


# ---------------------------------------------------------
# General helpers
# ---------------------------------------------------------

def current_timestamp() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_message(raw_message: Any):
    """
    Main entry point for incoming messages.

    Args:
        raw_message:
            A JSON string, bytes message, or already-decoded dictionary.

    Returns:
        A normalized dictionary for JSON messages.
        A normalized dictionary or None for text messages.

    Raises:
        ValueError if the message cannot be interpreted.
    """

    # Already-decoded JSON object
    if isinstance(raw_message, dict):
        return normalize_payload(raw_message)

    # Decode bytes
    if isinstance(raw_message, bytes):
        try:
            raw_message = raw_message.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                "Incoming message is not valid UTF-8 text."
            ) from error

    if not isinstance(raw_message, str):
        raise ValueError(
            f"Unsupported message type: {type(raw_message).__name__}"
        )

    raw_message = raw_message.strip()

    if not raw_message:
        return None

    # First, attempt to interpret the message as JSON.
    try:
        payload = json.loads(raw_message)

        if not isinstance(payload, dict):
            raise ValueError(
                "Expected a JSON object, not a JSON list or scalar."
            )

        return normalize_payload(payload)

    except json.JSONDecodeError:
        pass

    # If it isn't JSON, treat it as the provisional text format.
    return parse_text_message(raw_message)


# ---------------------------------------------------------
# JSON normalization
# ---------------------------------------------------------

def normalize_payload(payload: dict) -> dict:
    """
    Convert a decoded JSON object into the CANARY internal format.

    Existing sensor metadata and sample values are preserved.
    Missing sampling frequencies are NOT invented.
    """

    normalized = copy.deepcopy(payload)

    # Record when our backend received the message.
    received_at = normalized.get("received_at") or current_timestamp()

    # Use the hardware timestamp when available.
    # Otherwise, use the backend receipt time as a fallback.
    timestamp = normalized.get("timestamp") or received_at

    # Support both:
    #   {"sensor_data": {...}}
    # and the provisional batch format:
    #   {"samples": {...}}
    sensor_data = normalized.get("sensor_data")

    if sensor_data is None:
        incoming_samples = normalized.get("samples")

        if isinstance(incoming_samples, dict):
            sensor_data = {}

            for sensor_name, samples in incoming_samples.items():
                sensor_data[sensor_name] = {
                    "samples": copy.deepcopy(samples)
                }
        else:
            raise ValueError(
                "JSON message must contain either "
                "'sensor_data' or a 'samples' dictionary."
            )

    if not isinstance(sensor_data, dict):
        raise ValueError("'sensor_data' must be a dictionary.")

    normalized["device_id"] = normalized.get("device_id")
    normalized["timestamp"] = timestamp
    normalized["received_at"] = received_at
    normalized["sensor_data"] = sensor_data

    return normalized


# ---------------------------------------------------------
# Text message parsing
# ---------------------------------------------------------

class SensorTextParser:
    """
    Parses the existing line-based hardware text format.

    A record is emitted after temperature, acceleration,
    magnetometer, and gyroscope readings have all arrived.

    This is a provisional adapter for the text format previously
    provided. It does not assume this will be the final hardware format.
    """

    def __init__(self, device_id: str = "CANARY_001"):
        self.device_id = device_id
        self.sequence_number = 0
        self.reset()

    def reset(self):
        """Clear the readings currently being assembled."""

        self.current_readings = {
            "temperature": None,
            "acceleration": None,
            "magnetometer": None,
            "gyroscope": None
        }

    @staticmethod
    def extract_xyz(line: str) -> Optional[dict]:
        """Extract X, Y, and Z values from a sensor text line."""

        pattern = (
            r"X:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
            r".*?Y:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
            r".*?Z:\s*(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)"
        )

        match = re.search(pattern, line, re.IGNORECASE)

        if not match:
            return None

        return {
            "x": float(match.group(1)),
            "y": float(match.group(2)),
            "z": float(match.group(3))
        }

    def parse_line(self, line: str) -> Optional[dict]:
        """
        Process one line of sensor text.

        Returns a normalized record once all four readings
        have been collected. Otherwise returns None.
        """

        line = line.strip()

        if not line:
            return None

        lower_line = line.lower()

        # Temperature
        if lower_line.startswith("temperature"):

            # A new temperature reading indicates a new record.
            if self.current_readings["temperature"] is not None:
                self.reset()

            match = re.search(
                r"(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)",
                line
            )

            if match:
                self.current_readings["temperature"] = float(
                    match.group(1)
                )

        # Accelerometer
        elif lower_line.startswith("accel"):

            values = self.extract_xyz(line)

            if values:
                self.current_readings["acceleration"] = values

        # Magnetometer
        elif lower_line.startswith("mag"):

            values = self.extract_xyz(line)

            if values:
                self.current_readings["magnetometer"] = values

        # Gyroscope
        elif lower_line.startswith("gyro"):

            values = self.extract_xyz(line)

            if values:
                self.current_readings["gyroscope"] = values

        return self.create_record_if_complete()

    def create_record_if_complete(self) -> Optional[dict]:
        """Emit a record once all expected readings are present."""

        if any(
            value is None
            for value in self.current_readings.values()
        ):
            return None

        self.sequence_number += 1

        received_at = current_timestamp()

        record = {
            "device_id": self.device_id,
            "sequence_number": self.sequence_number,
            "timestamp": received_at,
            "received_at": received_at,
            "synthetic": False,

            "sensor_data": {
                "temperature": {
                    "value": self.current_readings["temperature"],
                    "unit": "deg C"
                },

                "imu": {
                    "samples": [
                        {
                            "acceleration": copy.deepcopy(
                                self.current_readings["acceleration"]
                            ),
                            "magnetometer": copy.deepcopy(
                                self.current_readings["magnetometer"]
                            ),
                            "gyroscope": copy.deepcopy(
                                self.current_readings["gyroscope"]
                            )
                        }
                    ]
                }
            }
        }

        self.reset()

        return record


# ---------------------------------------------------------
# Text message adapter
# ---------------------------------------------------------

# One parser instance maintains readings across incoming lines.
text_parser = SensorTextParser()


def parse_text_message(raw_message: str) -> Optional[dict]:
    """
    Parse a text message containing one or more sensor lines.

    If the message contains multiple lines, process them in order.
    Returns the most recently completed record, if any.
    """

    completed_record = None

    for line in raw_message.splitlines():

        record = text_parser.parse_line(line)

        if record is not None:
            completed_record = record

    return completed_record
