
from backend.data_parser import parse_message, SensorTextParser
from backend.validation import validate_batch, validate_batch_safely


# -----------------------------------------
# TEST 1: Valid JSON message
# -----------------------------------------

print("\nTEST 1: Valid JSON")

data = {
    "device_id": "CANARY_001",
    "timestamp": "2026-11-12T15:00:00Z",
    "sensor_data": {
        "ecg": {
            "sampling_rate_hz": 250,
            "unit": "mV",
            "samples": [0.1, 0.2, 0.3]
        },
        "ppg": {
            "sampling_rate_hz": 50,
            "unit": "arbitrary",
            "samples": [0.5, 0.6]
        }
    }
}

assert validate_batch(data) is True
print("PASSED")


# -----------------------------------------
# TEST 2: Valid text-parser output
# -----------------------------------------

print("\nTEST 2: Text parser integration")

parser = SensorTextParser()

lines = [
    "Temperature 26.18 deg C",
    "Accel X: -0.88 Y: 2.02 Z: 9.91 m/s^2",
    "Mag X: -20.85 Y: 22.95 Z: 92.85 uT",
    "Gyro X: 0.03 Y: -0.02 Z: 0.01 radians/s"
]

record = None

for line in lines:
    record = parser.parse_line(line)

assert validate_batch(record) is True
print("PASSED")


# -----------------------------------------
# TEST 3: Missing optional sensor
# -----------------------------------------

print("\nTEST 3: Missing optional sensor")

partial_data = {
    "device_id": "CANARY_001",
    "timestamp": "2026-11-12T15:00:00Z",
    "sensor_data": {
        "ecg": {
            "samples": [0.1, 0.2]
        }
    }
}

assert validate_batch(partial_data) is True
print("PASSED")


# -----------------------------------------
# TEST 4: Invalid numeric sample
# -----------------------------------------

print("\nTEST 4: Invalid numeric sample")

invalid_data = {
    "device_id": "CANARY_001",
    "timestamp": "2026-11-12T15:00:00Z",
    "sensor_data": {
        "ecg": {
            "samples": [0.1, float("nan"), 0.3]
        }
    }
}

valid, message = validate_batch_safely(invalid_data)

assert valid is False
print("PASSED:", message)


# -----------------------------------------
# TEST 5: Invalid sampling frequency
# -----------------------------------------

print("\nTEST 5: Invalid sampling frequency")

invalid_rate = {
    "device_id": "CANARY_001",
    "timestamp": "2026-11-12T15:00:00Z",
    "sensor_data": {
        "ecg": {
            "sampling_rate_hz": -250,
            "samples": [0.1, 0.2]
        }
    }
}

valid, message = validate_batch_safely(invalid_rate)

assert valid is False
print("PASSED:", message)


print("\nALL VALIDATION TESTS COMPLETED SUCCESSFULLY!")
