
from backend.waveform import WaveformManager


print("========== CANARY WAVEFORM TESTS ==========")


manager = WaveformManager(
    sampling_rates={
        "ecg": 10,
        "ppg": 2,
        "temperature": 1,
    },
    retention_seconds=5,
)


# --------------------------------------------------
# TEST 1: Store raw waveform samples
# --------------------------------------------------

print("\nTEST 1: Store raw samples")

manager.add_samples(
    "ecg",
    [0.1, 0.2, 0.3, 0.4],
    start_timestamp=1000,
    unit="mV",
)

waveform = manager.get_waveform("ecg")

assert waveform["sample_count"] == 4
assert waveform["values"] == [0.1, 0.2, 0.3, 0.4]
assert waveform["timestamps"][0] == 1000
assert waveform["timestamps"][1] == 1000.1

print("PASSED: Raw samples and timestamps preserved.")


# --------------------------------------------------
# TEST 2: Independent sensor buffers
# --------------------------------------------------

print("\nTEST 2: Independent buffers")

manager.add_samples(
    "ppg",
    [1, 2, 3],
    start_timestamp=1000,
    unit="a.u.",
)

assert manager.get_waveform("ecg")["sample_count"] == 4
assert manager.get_waveform("ppg")["sample_count"] == 3

print("PASSED: Sensors have independent buffers.")


# --------------------------------------------------
# TEST 3: Retrieve a time range
# --------------------------------------------------

print("\nTEST 3: Time range retrieval")

manager.add_samples(
    "ecg",
    [0.5, 0.6, 0.7],
    start_timestamp=1000.4,
)

waveform = manager.get_waveform(
    "ecg",
    start_timestamp=1000.2,
    end_timestamp=1000.4,
)

assert waveform["sample_count"] == 3
assert waveform["values"] == [0.3, 0.4, 0.5]

print("PASSED: Time-range retrieval works.")


# --------------------------------------------------
# TEST 4: Retention limit
# --------------------------------------------------

print("\nTEST 4: Retention limit")

manager.add_samples(
    "ecg",
    [1, 2, 3, 4, 5, 6],
    start_timestamp=1010,
)

waveform = manager.get_waveform("ecg")

# ECG is 10 Hz with 5 seconds retention.
# Maximum buffer size = 50 samples.
assert waveform["sample_count"] <= 50

# Old samples should have been removed.
assert waveform["timestamps"][0] >= 1005

print("PASSED: Old waveform data is removed from memory.")


# --------------------------------------------------
# TEST 5: Sensor payload integration
# --------------------------------------------------

print("\nTEST 5: Sensor payload integration")

manager.ingest_sensor_payload(
    sensor_name="ecg",
    payload={
        "sampling_rate_hz": 10,
        "unit": "mV",
        "samples": [0.8, 0.9, 1.0],
    },
    fallback_timestamp=1020,
)

waveform = manager.get_waveform("ecg")

assert waveform["values"][-3:] == [0.8, 0.9, 1.0]
assert waveform["unit"] == "mV"

print("PASSED: Parsed sensor payload can be ingested.")


# --------------------------------------------------
# TEST 6: Individual temperature value
# --------------------------------------------------

print("\nTEST 6: Individual sensor value")

manager.ingest_sensor_payload(
    sensor_name="temperature",
    payload={
        "value": 36.7,
        "unit": "deg C",
    },
    fallback_timestamp=1020,
)

waveform = manager.get_waveform("temperature")

assert waveform["values"] == [36.7]
assert waveform["unit"] == "deg C"

print("PASSED: Individual sensor values are supported.")


# --------------------------------------------------
# TEST 7: Explicit sample timestamps
# --------------------------------------------------

print("\nTEST 7: Explicit timestamps")

manager.ingest_sensor_payload(
    sensor_name="ecg",
    payload={
        "sampling_rate_hz": 10,
        "unit": "mV",
        "samples": [
            {"timestamp": 1030.00, "value": 0.1},
            {"timestamp": 1030.12, "value": 0.2},
            {"timestamp": 1030.25, "value": 0.3},
        ],
    },
    fallback_timestamp=1030,
)

waveform = manager.get_waveform("ecg")

assert waveform["values"][-3:] == [0.1, 0.2, 0.3]
assert waveform["timestamps"][-3:] == [1030.0, 1030.12, 1030.25]

print("PASSED: Hardware timestamps are preserved.")


# --------------------------------------------------
# TEST 8: Unknown sensor
# --------------------------------------------------

print("\nTEST 8: Unknown sensor")

try:
    manager.add_sample(
        "unknown_sensor",
        1,
        1000,
    )

    raise AssertionError("Unknown sensor should be rejected.")

except ValueError:
    print("PASSED: Unknown sensors are rejected.")


print("\nALL WAVEFORM TESTS PASSED!")
