
"""
CANARY InfluxDB storage layer.

Stores:
1. Raw sensor samples for waveform reconstruction and historical review.
2. Processed sliding-window features for dashboard metrics and trends.

Supports missing sensors, nested IMU readings, individual sample
timestamps, and configurable InfluxDB credentials.
"""

import math
from datetime import datetime, timezone, timedelta
from typing import Optional

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

try:
    from backend.config import (
        INFLUXDB_URL,
        INFLUXDB_TOKEN,
        INFLUXDB_ORG,
        INFLUXDB_BUCKET,
        SENSOR_SAMPLING_RATES,
    )
except ImportError:
    from config import (
        INFLUXDB_URL,
        INFLUXDB_TOKEN,
        INFLUXDB_ORG,
        INFLUXDB_BUCKET,
        SENSOR_SAMPLING_RATES,
    )


RAW_MEASUREMENT = "sensor_samples"
FEATURE_MEASUREMENT = "sensor_readings"


def create_client():
    """Create an InfluxDB client using configuration settings."""
    return InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
    )


def normalize_timestamp(value):
    """
    Convert supported timestamp formats to timezone-aware datetime.

    Numeric timestamps are interpreted as seconds, milliseconds,
    or nanoseconds depending on their magnitude.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if not math.isfinite(value):
            raise ValueError("Timestamp must be finite.")

        if abs(value) > 1e17:
            value = value / 1e9
        elif abs(value) > 1e11:
            value = value / 1e3

        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        normalized = value.strip()

        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"

        result = datetime.fromisoformat(normalized)

        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)

        return result

    raise ValueError(f"Unsupported timestamp: {value!r}")


def is_numeric(value):
    """Return True for finite numeric values, excluding booleans."""
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _get_sample_fields(sample):
    """
    Convert a sample into InfluxDB numeric fields.

    Supports:
    - Individual numeric values
    - {"value": 0.1}
    - {"x": 1, "y": 2, "z": 3}
    - Nested IMU components
    """
    if is_numeric(sample):
        return {"value": float(sample)}

    if not isinstance(sample, dict):
        return {}

    fields = {}

    if is_numeric(sample.get("value")):
        fields["value"] = float(sample["value"])

    for axis in ("x", "y", "z"):
        if is_numeric(sample.get(axis)):
            fields[axis] = float(sample[axis])

    for component in ("acceleration", "magnetometer", "gyroscope"):
        component_data = sample.get(component)

        if isinstance(component_data, dict):
            for axis in ("x", "y", "z"):
                value = component_data.get(axis)

                if is_numeric(value):
                    fields[f"{component}_{axis}"] = float(value)

    return fields


def _get_sample_timestamp(
    sample,
    batch_timestamp,
    sample_index,
    sampling_rate,
):
    """Use a hardware timestamp when available; otherwise reconstruct it."""
    if isinstance(sample, dict) and sample.get("timestamp") is not None:
        return normalize_timestamp(sample["timestamp"])

    if sampling_rate is None or sampling_rate <= 0:
        return batch_timestamp

    return batch_timestamp + timedelta(
        seconds=sample_index / sampling_rate
    )


def _build_raw_points(batch):
    """Build raw InfluxDB points for all sensors present in a batch."""
    device_id = batch["device_id"]
    batch_timestamp = normalize_timestamp(
        batch.get("timestamp") or batch.get("received_at")
    )

    sensor_data = batch.get("sensor_data", {})
    points = []

    for sensor_name, payload in sensor_data.items():
        if not isinstance(payload, dict):
            continue

        unit = payload.get("unit")
        sampling_rate = payload.get("sampling_rate_hz")

        if not is_numeric(sampling_rate) or sampling_rate <= 0:
            sampling_rate = SENSOR_SAMPLING_RATES.get(sensor_name)

        # Support sensors that report one individual value.
        if "samples" not in payload:
            samples = []

            if "value" in payload:
                samples = [
                    {
                        "value": payload["value"],
                        "timestamp": payload.get("timestamp"),
                    }
                ]
            elif any(axis in payload for axis in ("x", "y", "z")):
                samples = [
                    {
                        "x": payload.get("x"),
                        "y": payload.get("y"),
                        "z": payload.get("z"),
                        "timestamp": payload.get("timestamp"),
                    }
                ]
            else:
                continue
        else:
            samples = payload["samples"]

        if not isinstance(samples, list):
            continue

        for index, sample in enumerate(samples):
            fields = _get_sample_fields(sample)

            if not fields:
                continue

            sample_timestamp = _get_sample_timestamp(
                sample,
                batch_timestamp,
                index,
                sampling_rate,
            )

            point = (
                Point(RAW_MEASUREMENT)
                .tag("device_id", str(device_id))
                .tag("sensor", str(sensor_name))
                .field("sample_index", index)
            )

            if isinstance(unit, str) and unit:
                point = point.tag("unit", unit)

            for field_name, value in fields.items():
                point = point.field(field_name, value)

            point = point.time(sample_timestamp, WritePrecision.NS)
            points.append(point)

    return points


def _flatten_features(features, prefix=""):
    """
    Flatten nested numeric features into InfluxDB field names.

    Example:
        {"ecg": {"mean": 0.2, "std": 0.1}}

    Becomes:
        {"ecg_mean": 0.2, "ecg_std": 0.1}
    """
    flattened = {}

    if not isinstance(features, dict):
        return flattened

    for key, value in features.items():
        field_name = f"{prefix}_{key}" if prefix else str(key)

        if isinstance(value, dict):
            flattened.update(
                _flatten_features(value, field_name)
            )
        elif is_numeric(value):
            flattened[field_name] = float(value)

    return flattened


def _build_feature_point(batch, features):
    """Build one point containing the processed window features."""
    if not features:
        return None

    fields = _flatten_features(features)

    if not fields:
        return None

    timestamp = normalize_timestamp(
        batch.get("timestamp") or batch.get("received_at")
    )

    point = (
        Point(FEATURE_MEASUREMENT)
        .tag("device_id", str(batch["device_id"]))
        .time(timestamp, WritePrecision.NS)
    )

    for field_name, value in fields.items():
        point = point.field(field_name, value)

    return point


def write_batch(client, batch, features=None, write_api=None):
    """
    Write raw samples and processed features to InfluxDB.

    Args:
        client: Connected InfluxDBClient.
        batch: Parsed and validated sensor batch.
        features: Processed window features, if available.
        write_api: Optional persistent InfluxDB WriteApi.

    Returns:
        Number of InfluxDB points submitted.
    """
    if not isinstance(batch, dict):
        raise ValueError("Batch must be a dictionary.")

    if not batch.get("device_id"):
        raise ValueError("Batch is missing device_id.")

    if not batch.get("timestamp") and not batch.get("received_at"):
        raise ValueError("Batch is missing its timestamp.")

    points = _build_raw_points(batch)

    feature_point = _build_feature_point(batch, features)

    if feature_point is not None:
        points.append(feature_point)

    if not points:
        return 0

    owns_write_api = write_api is None

    if owns_write_api:
        write_api = client.write_api(write_options=SYNCHRONOUS)

    try:
        write_api.write(
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
            record=points,
        )
    finally:
        if owns_write_api:
            write_api.close()

    return len(points)


if __name__ == "__main__":
    client = create_client()

    try:
        if client.ping():
            print("Successfully connected to InfluxDB!")
        else:
            print("Could not connect to InfluxDB.")
    finally:
        client.close()

