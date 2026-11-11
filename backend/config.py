# CANARY configuration

# Sensor collection interval (seconds)
COLLECTION_INTERVAL = 1

# Reporting intervals (seconds)
REPORTING_INTERVALS = {
    1: 600,  # 10 minutes - agreed baseline
    2: 10,   # Placeholder
    3: 1     # Placeholder
}

# Initial monitoring tier
DEFAULT_TIER = 1

# Sensor sampling rates (Hz)
ECG_RATE = 250
PPG_RATE = 50
BIOIMPEDANCE_RATE = 25
IMU_RATE = 50
TEMPERATURE_RATE = 1