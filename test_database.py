
from datetime import datetime, timezone

from backend.database import (
    _build_raw_points,
    _flatten_features,
    write_batch,
)


class FakeWriteAPI:
    def __init__(self):
        self.written_points = []
        self.closed = False

    def write(self, bucket, org, record):
        self.written_points.extend(record)

    def close(self):
        self.closed = True


class FakeClient:
    def __init__(self):
        self.write_api_instance = FakeWriteAPI()

    def write_api(self, write_options=None):
        return self.write_api_instance


def make_batch():
    return {
        "device_id": "CANARY_001",
        "timestamp": "2026-11-12T15:00:00Z",
        "sensor_data": {
            "ecg": {
                "sampling_rate_hz": 250,
                "unit": "mV",
                "samples": [0.1, 0.2, 0.3],
            },
            "temperature": {
                "value": 36.7,
                "unit": "deg C",
            },
            "imu": {
                "samples": [
                    {
                        "acceleration": {"x": 1.0, "y": 2.0, "z": 3.0},
                        "magnetometer": {"x": 0.1, "y": 0.2, "z": 0.3},
                        "gyroscope": {"x": 0.4, "y": 0.5, "z": 0.6},
                    }
                ]
            },
        },
    }


def test_raw_sample_storage():
    points = _build_raw_points(make_batch())

    assert len(points) == 5
    print("PASSED: Raw samples from available sensors are stored.")


def test_missing_sensors():
    batch = make_batch()
    batch["sensor_data"] = {
        "temperature": {"value": 36.7, "unit": "deg C"}
    }

    points = _build_raw_points(batch)

    assert len(points) == 1
    print("PASSED: Missing sensors do not cause errors.")


def test_nested_imu():
    points = _build_raw_points(make_batch())

    imu_point = points[-1]
    fields = imu_point._fields

    assert "acceleration_x" in fields
    assert "magnetometer_y" in fields
    assert "gyroscope_z" in fields

    print("PASSED: Nested IMU components are supported.")


def test_explicit_hardware_timestamp():
    batch = make_batch()
    batch["sensor_data"] = {
        "ecg": {
            "samples": [
                {"value": 0.5, "timestamp": "2026-11-12T15:00:02Z"}
            ]
        }
    }

    points = _build_raw_points(batch)

    assert points[0]._time == datetime(
        2026, 11, 12, 15, 0, 2, tzinfo=timezone.utc
    )

    print("PASSED: Hardware timestamps are preserved.")


def test_feature_flattening():
    features = {
        "ecg": {"mean": 0.2, "std": 0.1},
        "imu": {"acceleration": {"mean": 9.8}},
    }

    flattened = _flatten_features(features)

    assert flattened["ecg_mean"] == 0.2
    assert flattened["ecg_std"] == 0.1
    assert flattened["imu_acceleration_mean"] == 9.8

    print("PASSED: Nested features are flattened.")


def test_batch_write():
    client = FakeClient()

    count = write_batch(
        client,
        make_batch(),
        features={
            "ecg": {"mean": 0.2},
            "temperature": {"mean": 36.7},
        },
    )

    assert count == 6
    assert len(client.write_api_instance.written_points) == 6
    assert client.write_api_instance.closed

    print("PASSED: Raw and processed points are written.")


def test_persistent_write_api():
    client = FakeClient()
    persistent_writer = FakeWriteAPI()

    count = write_batch(
        client,
        make_batch(),
        features=None,
        write_api=persistent_writer,
    )

    assert count == 5
    assert len(persistent_writer.written_points) == 5
    assert not persistent_writer.closed

    print("PASSED: Persistent writer remains open.")


if __name__ == "__main__":
    tests = [
        test_raw_sample_storage,
        test_missing_sensors,
        test_nested_imu,
        test_explicit_hardware_timestamp,
        test_feature_flattening,
        test_batch_write,
        test_persistent_write_api,
    ]

    print("========== CANARY DATABASE TESTS ==========\n")

    for test in tests:
        test()

    print("\nALL DATABASE TESTS PASSED!")
