
import asyncio

from backend.main import (
    CanaryPipeline,
    to_timestamp,
    get_sensor_samples,
    get_sample_timestamp,
)


class FakeWaveformManager:
    def __init__(self):
        self.received = []

    def ingest_sensor_payload(
        self,
        sensor_name,
        payload,
        fallback_timestamp,
    ):
        self.received.append(
            (sensor_name, payload, fallback_timestamp)
        )


class FakeWindowManager:
    def __init__(self):
        self.received = []

    def add_sample(self, sensor_name, value, timestamp):
        self.received.append((sensor_name, value, timestamp))

    def get_ready_windows(self):
        return {}


class FakeTierManager:
    def update(self):
        return 1

    def get_reporting_interval(self):
        return 600

    def get_status(self):
        return {
            "current_tier": 1,
            "reporting_interval_seconds": 600,
            "active_alerts": {},
        }


class FakeDatabase:
    pass


def test_timestamp_conversion():
    timestamp = to_timestamp("2026-11-12T15:00:00Z")

    assert isinstance(timestamp, float)

    print("PASSED: Timestamp conversion.")


def test_individual_sensor_value():
    samples = get_sensor_samples({"value": 36.7})

    assert samples == [36.7]

    print("PASSED: Individual sensor values.")


def test_batch_sensor_values():
    samples = get_sensor_samples({
        "sampling_rate_hz": 250,
        "samples": [0.1, 0.2, 0.3],
    })

    assert len(samples) == 3

    print("PASSED: Multiple samples extracted.")


def test_sample_timestamp_reconstruction():
    timestamp = get_sample_timestamp(
        sample=0.5,
        batch_timestamp=1000.0,
        sample_index=2,
        sampling_rate=250,
    )

    assert timestamp == 1000.008

    print("PASSED: Sample timestamps reconstructed.")


def test_independent_sensor_ingestion():
    waveform = FakeWaveformManager()
    windows = FakeWindowManager()
    database_calls = []

    def fake_database_writer(client, batch, features):
        database_calls.append((batch, features))

    pipeline = CanaryPipeline(
        database_client=FakeDatabase(),
        waveform_manager=waveform,
        window_manager=windows,
        tier_manager=FakeTierManager(),
        database_writer=fake_database_writer,
    )

    batch = {
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
        },
    }

    asyncio.run(pipeline.handle_message(batch))

    # Both sensors reached the waveform manager.
    assert len(waveform.received) == 2

    # ECG contributed three samples; temperature contributed one.
    assert len(windows.received) == 4

    ecg_samples = [
        item for item in windows.received
        if item[0] == "ecg"
    ]

    temperature_samples = [
        item for item in windows.received
        if item[0] == "temperature"
    ]

    assert len(ecg_samples) == 3
    assert len(temperature_samples) == 1

    # The raw batch was submitted to the database writer.
    assert len(database_calls) == 1

    print("PASSED: Independent sensor ingestion.")
    print("PASSED: Raw batch submitted to database.")


if __name__ == "__main__":
    tests = [
        test_timestamp_conversion,
        test_individual_sensor_value,
        test_batch_sensor_values,
        test_sample_timestamp_reconstruction,
        test_independent_sensor_ingestion,
    ]

    print("========== CANARY MAIN TESTS ==========\n")

    for test in tests:
        test()

    print("\nALL MAIN TESTS PASSED!")
