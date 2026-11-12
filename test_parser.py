from backend.data_parser import parse_message, SensorTextParser

print("========== TEST 1: JSON ==========")

data = {
    "device_id": "CANARY_001",
    "sensor_data": {
        "ecg": {
            "sampling_rate_hz": 250,
            "unit": "mV",
            "samples": [0.1, 0.2, 0.3]
        }
    }
}

result = parse_message(data)
print(result)

assert result["device_id"] == "CANARY_001"
assert result["sensor_data"]["ecg"]["samples"] == [0.1, 0.2, 0.3]

print("JSON TEST PASSED!")


print("\n========== TEST 2: TEXT ==========")

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

print(record)

assert record is not None
assert record["sensor_data"]["temperature"]["value"] == 26.18

print("TEXT TEST PASSED!")
