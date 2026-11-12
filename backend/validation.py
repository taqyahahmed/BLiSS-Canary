
"""
CANARY Data Validation
----------------------
Validates normalized sensor messages produced by data_parser.py.

Design principles:
    - Sensors can be missing from a message.
    - Different sensors can have different sample counts.
    - Sampling frequencies are not assumed to be fixed.
    - Invalid numeric values are rejected.
    - Missing optional metadata is not invented.
"""

import math
from datetime import datetime
from typing import Any


# Sensors whose sample arrays contain ordinary numeric values.
NUMERIC_SENSORS = {
    "ecg",
    "ppg",
    "bioimpedance",
}

# Supported IMU components.
IMU_COMPONENTS = {
    "acceleration",
    "magnetometer",
    "gyroscope",
}


class ValidationError(ValueError):
    """Raised when incoming sensor data is malformed."""


def is_valid_number(value: Any) -> bool:
    """
    Check whether a value is a finite number.

    Booleans are explicitly rejected because Python treats
    True and False as integers.
    """

    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float)):
        return False

    return math.isfinite(value)


def validate_timestamp(timestamp: Any) -> bool:
    """Check whether a timestamp is a valid ISO 8601 string."""

    if not isinstance(timestamp, str):
        return False

    try:
        datetime.fromisoformat(
            timestamp.replace("Z", "+00:00")
        )
        return True

    except ValueError:
        return False


def validate_sample_rate(sensor_name: str, sensor: dict) -> None:
    """Validate sampling-rate metadata when it is provided."""

    rate = sensor.get("sampling_rate_hz")

    if rate is None:
        return

    if not is_valid_number(rate) or rate <= 0:
        raise ValidationError(
            f"{sensor_name}: sampling_rate_hz must be a "
            "positive finite number."
        )


def validate_numeric_samples(sensor_name: str, sensor: dict) -> None:
    """Validate a sensor containing a list of numeric samples."""

    samples = sensor.get("samples")

    if not isinstance(samples, list):
        raise ValidationError(
            f"{sensor_name}: samples must be a list."
        )

    if not samples:
        raise ValidationError(
            f"{sensor_name}: samples cannot be empty."
        )

    for index, sample in enumerate(samples):

        if not is_valid_number(sample):
            raise ValidationError(
                f"{sensor_name}: invalid numeric sample "
                f"at index {index}: {sample}"
            )


def validate_xyz(values: Any, description: str) -> None:
    """Validate an X/Y/Z measurement."""

    if not isinstance(values, dict):
        raise ValidationError(
            f"{description}: expected an X/Y/Z dictionary."
        )

    for axis in ("x", "y", "z"):

        if axis not in values:
            raise ValidationError(
                f"{description}: missing {axis} value."
            )

        if not is_valid_number(values[axis]):
            raise ValidationError(
                f"{description}: {axis} must be a finite number."
            )


def validate_imu(sensor: dict) -> None:
    """
    Validate IMU samples.

    Supports:
        1. Separate acceleration, magnetometer, and gyroscope
           dictionaries within each sample.
        2. Traditional samples containing only x, y, and z.
    """

    samples = sensor.get("samples")

    if not isinstance(samples, list):
        raise ValidationError("imu: samples must be a list.")

    if not samples:
        raise ValidationError("imu: samples cannot be empty.")

    for index, sample in enumerate(samples):

        if not isinstance(sample, dict):
            raise ValidationError(
                f"imu: sample {index} must be a dictionary."
            )

        # Format produced by our current text parser.
        if any(component in sample for component in IMU_COMPONENTS):

            for component in IMU_COMPONENTS:

                if component in sample:
                    validate_xyz(
                        sample[component],
                        f"imu sample {index} {component}"
                    )

        # Traditional accelerometer-style format.
        elif all(axis in sample for axis in ("x", "y", "z")):

            validate_xyz(sample, f"imu sample {index}")

        else:
            raise ValidationError(
                f"imu: sample {index} has an unsupported structure."
            )


def validate_temperature(sensor: dict) -> None:
    """Validate a temperature sensor reading."""

    # Support either:
    # {"value": 36.7}
    # or {"samples": [36.7, 36.8, ...]}

    if "value" in sensor:

        if not is_valid_number(sensor["value"]):
            raise ValidationError(
                "temperature: value must be a finite number."
            )

    elif "samples" in sensor:

        validate_numeric_samples("temperature", sensor)

    else:
        raise ValidationError(
            "temperature: expected a value or samples list."
        )


def validate_sensor(sensor_name: str, sensor: Any) -> None:
    """Validate one sensor entry."""

    if not isinstance(sensor, dict):
        raise ValidationError(
            f"{sensor_name}: sensor data must be a dictionary."
        )

    validate_sample_rate(sensor_name, sensor)

    if sensor_name in NUMERIC_SENSORS:
        validate_numeric_samples(sensor_name, sensor)

    elif sensor_name == "imu":
        validate_imu(sensor)

    elif sensor_name == "temperature":
        validate_temperature(sensor)

    else:
        raise ValidationError(
            f"Unsupported sensor name: {sensor_name}"
        )


def validate_batch(batch: dict) -> bool:
    """
    Validate a complete normalized CANARY message.

    Returns:
        True if valid.

    Raises:
        ValidationError if invalid.
    """

    if not isinstance(batch, dict):
        raise ValidationError(
            "Incoming batch must be a dictionary."
        )

    # Device identification
    device_id = batch.get("device_id")

    if not isinstance(device_id, str) or not device_id.strip():
        raise ValidationError(
            "Missing or invalid device_id."
        )

    # Timestamp
    if not validate_timestamp(batch.get("timestamp")):
        raise ValidationError(
            "Missing or invalid ISO 8601 timestamp."
        )

    # Sensor dictionary
    sensor_data = batch.get("sensor_data")

    if not isinstance(sensor_data, dict):
        raise ValidationError(
            "sensor_data must be a dictionary."
        )

    if not sensor_data:
        raise ValidationError(
            "sensor_data cannot be empty."
        )

    # Validate each sensor that is present.
    for sensor_name, sensor in sensor_data.items():

        validate_sensor(sensor_name, sensor)

    return True


def validate_batch_safely(batch: dict) -> tuple[bool, str]:
    """
    Safe wrapper for the main processing pipeline.

    Returns:
        (True, "Valid") if successful.
        (False, error_message) if invalid.
    """

    try:
        validate_batch(batch)
        return True, "Valid"

    except ValidationError as error:
        return False, str(error)
