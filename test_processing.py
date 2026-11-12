
from backend.windowing import WindowManager
from backend.processing import (
    process_window,
    process_ready_windows,
    calculate_statistics,
)


print("========== CANARY PROCESSING TESTS ==========")


# --------------------------------------------------
# TEST 1: Basic signal statistics
# --------------------------------------------------

print("\nTEST 1: Signal statistics")

stats = calculate_statistics([1, 2, 3, 4, 5])

assert stats["mean"] == 3
assert stats["minimum"] == 1
assert stats["maximum"] == 5
assert stats["sample_count"] == 5

print("PASSED: Basic statistics calculated correctly.")


# --------------------------------------------------
# TEST 2: ECG processing
# --------------------------------------------------

print("\nTEST 2: ECG processing")

ecg_window = {
    "sampling_rate_hz": 10,
    "duration_seconds": 2,
    "sample_count": 5,
    "expected_sample_count": 20,
    "is_full": False,
    "start_timestamp": 1000,
    "end_timestamp": 1000.4,
    "samples": [
        {"timestamp": 1000.0, "value": 1},
        {"timestamp": 1000.1, "value": 2},
        {"timestamp": 1000.2, "value": 3},
        {"timestamp": 1000.3, "value": 4},
        {"timestamp": 1000.4, "value": 5},
    ],
}

ecg_result = process_window("ecg", ecg_window)

assert ecg_result["features"]["mean"] == 3
assert ecg_result["features"]["valid_sample_count"] == 5

print("PASSED: ECG features calculated.")


# --------------------------------------------------
# TEST 3: PPG processing
# --------------------------------------------------

print("\nTEST 3: PPG processing")

ppg_window = {
    "sampling_rate_hz": 2,
    "duration_seconds": 2,
    "sample_count": 4,
    "expected_sample_count": 4,
    "is_full": True,
    "start_timestamp": 1000,
    "end_timestamp": 1001.5,
    "samples": [
        {"timestamp": 1000.0, "value": 2},
        {"timestamp": 1000.5, "value": 4},
        {"timestamp": 1001.0, "value": 6},
        {"timestamp": 1001.5, "value": 8},
    ],
}

ppg_result = process_window("ppg", ppg_window)

assert ppg_result["features"]["mean"] == 5
assert ppg_result["features"]["peak_to_peak"] == 6

print("PASSED: PPG features calculated.")


# --------------------------------------------------
# TEST 4: Bioimpedance processing
# --------------------------------------------------

print("\nTEST 4: Bioimpedance processing")

bioimpedance_window = {
    "sampling_rate_hz": 2,
    "duration_seconds": 2,
    "sample_count": 4,
    "expected_sample_count": 4,
    "is_full": True,
    "start_timestamp": 1000,
    "end_timestamp": 1001.5,
    "samples": [
        {"timestamp": 1000.0, "value": 500},
        {"timestamp": 1000.5, "value": 502},
        {"timestamp": 1001.0, "value": 504},
        {"timestamp": 1001.5, "value": 506},
    ],
}

bio_result = process_window(
    "bioimpedance",
    bioimpedance_window,
)

assert bio_result["features"]["mean"] == 503
assert bio_result["features"]["minimum"] == 500

print("PASSED: Bioimpedance features calculated.")


# --------------------------------------------------
# TEST 5: IMU processing
# --------------------------------------------------

print("\nTEST 5: IMU processing")

imu_window = {
    "sampling_rate_hz": 2,
    "duration_seconds": 2,
    "sample_count": 2,
    "expected_sample_count": 4,
    "is_full": False,
    "start_timestamp": 1000,
    "end_timestamp": 1000.5,
    "samples": [
        {
            "timestamp": 1000.0,
            "value": {
                "acceleration": {
                    "x": 1,
                    "y": 2,
                    "z": 2,
                },
                "magnetometer": {
                    "x": 3,
                    "y": 4,
                    "z": 0,
                },
                "gyroscope": {
                    "x": 0.1,
                    "y": 0.2,
                    "z": 0.3,
                },
            },
        },
        {
            "timestamp": 1000.5,
            "value": {
                "acceleration": {
                    "x": 2,
                    "y": 2,
                    "z": 1,
                },
                "magnetometer": {
                    "x": 0,
                    "y": 0,
                    "z": 5,
                },
                "gyroscope": {
                    "x": 0.2,
                    "y": 0.3,
                    "z": 0.4,
                },
            },
        },
    ],
}

imu_result = process_window("imu", imu_window)

assert "acceleration" in imu_result["features"]
assert "magnitude" in imu_result["features"]["acceleration"]

# First acceleration magnitude = sqrt(1 + 4 + 4) = 3.
assert imu_result["features"]["acceleration"]["magnitude"]["minimum"] == 3

print("PASSED: IMU vector features calculated.")


# --------------------------------------------------
# TEST 6: Temperature processing
# --------------------------------------------------

print("\nTEST 6: Temperature processing")

temperature_window = {
    "sampling_rate_hz": 1,
    "duration_seconds": 3,
    "sample_count": 3,
    "expected_sample_count": 3,
    "is_full": True,
    "start_timestamp": 1000,
    "end_timestamp": 1002,
    "samples": [
        {"timestamp": 1000, "value": 36.5},
        {"timestamp": 1001, "value": 37.0},
        {"timestamp": 1002, "value": 37.5},
    ],
}

temperature_result = process_window(
    "temperature",
    temperature_window,
)

assert temperature_result["features"]["mean"] == 37
assert temperature_result["features"]["trend_per_second"] == 0.5

print("PASSED: Temperature statistics and trend calculated.")


# --------------------------------------------------
# TEST 7: Multiple sensor windows
# --------------------------------------------------

print("\nTEST 7: Multiple sensor processing")

manager = WindowManager(
    sampling_rates={
        "ecg": 2,
        "temperature": 1,
    },
    duration_seconds=2,
    update_interval_seconds=1,
)

manager.add_samples(
    "ecg",
    [1, 2, 3, 4],
    start_timestamp=2000,
)

manager.add_samples(
    "temperature",
    [36, 37],
    start_timestamp=2000,
)

results = process_ready_windows(
    manager.get_all_windows()
)

assert "ecg" in results
assert "temperature" in results

print("PASSED: Multiple sensors processed together.")


# --------------------------------------------------
# TEST 8: Unknown sensor
# --------------------------------------------------

print("\nTEST 8: Unknown sensor")

try:
    process_window("unknown_sensor", {})

    raise AssertionError("Unknown sensor should be rejected.")

except ValueError:
    print("PASSED: Unknown sensors are rejected.")


print("\nALL PROCESSING TESTS PASSED!")
