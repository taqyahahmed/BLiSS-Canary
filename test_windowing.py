
from backend.windowing import WindowManager


print("========== CANARY WINDOWING TESTS ==========")


# Use smaller sampling rates to make testing easier.
manager = WindowManager(
    sampling_rates={
        "ecg": 10,
        "ppg": 2,
        "temperature": 1,
    },
    duration_seconds=2,
    update_interval_seconds=1,
)

# --------------------------------------------------
# TEST 1: Expected window sizes
# --------------------------------------------------

print("\nTEST 1: Expected window sizes")

assert manager.windows["ecg"].max_samples == 20
assert manager.windows["ppg"].max_samples == 4
assert manager.windows["temperature"].max_samples == 2

print("PASSED: Each sensor has its own window size.")


# --------------------------------------------------
# TEST 2: Add samples
# --------------------------------------------------

print("\nTEST 2: Add samples")

manager.add_samples(
    "ecg",
    list(range(20)),
    start_timestamp=1000,
)

ecg_window = manager.get_window("ecg")

assert ecg_window["sample_count"] == 20
assert ecg_window["is_full"] is True
assert ecg_window["samples"][0]["value"] == 0
assert ecg_window["samples"][-1]["value"] == 19

print("PASSED: ECG samples were added correctly.")


# --------------------------------------------------
# TEST 3: Independent sensor windows
# --------------------------------------------------

print("\nTEST 3: Independent sensor windows")

manager.add_samples(
    "ppg",
    [1, 2, 3, 4],
    start_timestamp=1000,
)

assert manager.get_window("ppg")["is_full"] is True

# Temperature is still empty.
assert manager.get_window("temperature")["sample_count"] == 0

print("PASSED: Sensors maintain independent windows.")


# --------------------------------------------------
# TEST 4: Sliding window removes old samples
# --------------------------------------------------

print("\nTEST 4: Sliding window")

manager.add_sample(
    "ecg",
    value=20,
    timestamp=1002,
)

ecg_window = manager.get_window("ecg")

assert ecg_window["sample_count"] == 20
assert ecg_window["samples"][0]["value"] == 1
assert ecg_window["samples"][-1]["value"] == 20

print("PASSED: Oldest sample was removed automatically.")


# --------------------------------------------------
# TEST 5: Window emission
# --------------------------------------------------

print("\nTEST 5: Window emission")

manager.clear_all()

manager.add_samples(
    "ecg",
    list(range(20)),
    start_timestamp=2000,
)

first_ready = manager.get_ready_windows(
    current_time=2000
)

assert "ecg" in first_ready

second_ready = manager.get_ready_windows(
    current_time=2000.5
)

assert "ecg" not in second_ready

third_ready = manager.get_ready_windows(
    current_time=2001
)

assert "ecg" in third_ready

print("PASSED: Windows emit at the configured interval.")


# --------------------------------------------------
# TEST 6: Unknown sensor
# --------------------------------------------------

print("\nTEST 6: Unknown sensor")

try:
    manager.add_sample(
        "unknown_sensor",
        value=10,
        timestamp=2000,
    )

    raise AssertionError("Unknown sensor should have been rejected.")

except ValueError:
    print("PASSED: Unknown sensors are rejected.")


print("\nALL WINDOWING TESTS PASSED!")
