
import backend.config as config

print("========== CANARY CONFIGURATION TEST ==========")

print("Application:", config.APP_NAME)
print("Mode:", config.OPERATING_MODE)

print("\nSensor sampling frequencies:")

for sensor, rate in config.SENSOR_SAMPLING_RATES.items():
    print(f"{sensor}: {rate} Hz")

print("\nSliding windows:")
print("Window duration:", config.WINDOW_DURATION_SECONDS, "seconds")
print("Update interval:", config.WINDOW_UPDATE_INTERVAL_SECONDS, "seconds")

print("\nReporting tiers:")

for tier, interval in config.REPORTING_INTERVALS.items():
    print(f"Tier {tier}: every {interval} seconds")

print("\nWebSocket URL:", config.WEBSOCKET_URL)
print("InfluxDB URL:", config.INFLUXDB_URL)
print("Device ID:", config.DEVICE_ID)

assert config.ECG_RATE == 250
assert config.PPG_RATE == 50
assert config.WINDOW_DURATION_SECONDS == 5
assert config.REPORTING_INTERVALS[1] == 600
assert config.DEFAULT_TIER == 1

print("\nALL CONFIGURATION TESTS PASSED!")
