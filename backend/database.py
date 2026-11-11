
from datetime import datetime, timedelta

from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# Local InfluxDB connection settings
INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "canary_dev_token_123456789"
INFLUXDB_ORG = "canary"
INFLUXDB_BUCKET = "sensor_data"


def create_client():
    """Create a connection to the InfluxDB database."""
    return InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG
    )


def write_batch(client, batch, features):
    """Write raw sensor samples and processed features to InfluxDB."""

    write_api = client.write_api(write_options=SYNCHRONOUS)

    start_time = datetime.fromisoformat(batch["timestamp"])
    sensor_data = batch["sensor_data"]

    points = []

    # Store ECG, PPG, and bioimpedance samples.
    signal_sensors = ["ecg", "ppg", "bioimpedance"]

    for sensor in signal_sensors:
        samples = sensor_data[sensor]["samples"]
        sampling_rate = sensor_data[sensor]["sampling_rate_hz"]

        for index, value in enumerate(samples):
            sample_time = start_time + timedelta(
                seconds=index / sampling_rate
            )

            point = (
                Point("sensor_samples")
                .tag("device_id", batch["device_id"])
                .tag("sensor", sensor)
                .field("value", float(value))
                .field("sample_index", index)
                .time(sample_time, WritePrecision.NS)
            )

            points.append(point)

    # Store individual IMU readings.
    imu_samples = sensor_data["imu"]["samples"]
    imu_rate = sensor_data["imu"]["sampling_rate_hz"]

    for index, sample in enumerate(imu_samples):
        sample_time = start_time + timedelta(
            seconds=index / imu_rate
        )

        point = (
            Point("sensor_samples")
            .tag("device_id", batch["device_id"])
            .tag("sensor", "imu")
            .field("x", float(sample["x"]))
            .field("y", float(sample["y"]))
            .field("z", float(sample["z"]))
            .field("sample_index", index)
            .time(sample_time, WritePrecision.NS)
        )

        points.append(point)

    # Store temperature reading.
    temperature_point = (
        Point("sensor_samples")
        .tag("device_id", batch["device_id"])
        .tag("sensor", "temperature")
        .field("value", float(sensor_data["temperature"]["value"]))
        .time(start_time, WritePrecision.NS)
    )

    points.append(temperature_point)

    # Store processed summary features.
    summary_point = (
        Point("sensor_readings")
        .tag("device_id", batch["device_id"])
        .field("ecg_mean", float(features["ecg"]["mean"]))
        .field("ppg_mean", float(features["ppg"]["mean"]))
        .field(
            "bioimpedance_mean",
            float(features["bioimpedance"]["mean"])
        )
        .field(
            "temperature",
            float(features["temperature"])
        )
        .field(
            "imu_acceleration",
            float(features["imu"]["average_acceleration_magnitude"])
        )
        .time(start_time, WritePrecision.NS)
    )

    points.append(summary_point)

    # Write all points from this batch.
    write_api.write(
        bucket=INFLUXDB_BUCKET,
        org=INFLUXDB_ORG,
        record=points
    )

    write_api.close()


if __name__ == "__main__":
    client = create_client()

    try:
        if client.ping():
            print("Successfully connected to InfluxDB!")
        else:
            print("Could not connect to InfluxDB.")
    finally:
        client.close()
