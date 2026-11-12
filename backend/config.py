
"""
CANARY Configuration
--------------------
Central settings for the backend application.

Sampling frequencies and reporting intervals are provisional
until confirmed by the hardware and systems teams.
"""

import os
from pathlib import Path


# ---------------------------------------------------------
# Project paths
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------
# Application settings
# ---------------------------------------------------------

APP_NAME = "CANARY"
APP_ENV = os.getenv("CANARY_ENV", "development")

# Select "simulator" or "hardware".
OPERATING_MODE = os.getenv("CANARY_MODE", "simulator").lower()

if OPERATING_MODE not in {"simulator", "hardware"}:
    raise ValueError(
        "CANARY_MODE must be either 'simulator' or 'hardware'."
    )


# ---------------------------------------------------------
# Hardware connection settings
# ---------------------------------------------------------

# Placeholder URL.
# Replace with the hardware team's actual WebSocket address.
WEBSOCKET_URL = os.getenv(
    "CANARY_WEBSOCKET_URL",
    "ws://localhost:8000/ws/sensors"
)

WEBSOCKET_RECONNECT_DELAY = float(
    os.getenv("CANARY_WEBSOCKET_RECONNECT_DELAY", "5")
)

WEBSOCKET_TIMEOUT = float(
    os.getenv("CANARY_WEBSOCKET_TIMEOUT", "10")
)


# ---------------------------------------------------------
# Sensor sampling frequencies
# ---------------------------------------------------------

# Provisional values from our existing simulator.
# These must eventually be confirmed by the hardware team.

SENSOR_SAMPLING_RATES = {
    "ecg": 250,
    "ppg": 50,
    "bioimpedance": 25,
    "imu": 50,
    "temperature": 1
}

ECG_RATE = SENSOR_SAMPLING_RATES["ecg"]
PPG_RATE = SENSOR_SAMPLING_RATES["ppg"]
BIOIMPEDANCE_RATE = SENSOR_SAMPLING_RATES["bioimpedance"]
IMU_RATE = SENSOR_SAMPLING_RATES["imu"]
TEMPERATURE_RATE = SENSOR_SAMPLING_RATES["temperature"]


# ---------------------------------------------------------
# Sliding-window settings
# ---------------------------------------------------------

# Duration of each sensor's rolling analysis window.
# Example: a 5-second ECG window contains 1250 samples at 250 Hz.

WINDOW_DURATION_SECONDS = float(
    os.getenv("CANARY_WINDOW_DURATION", "5")
)

# How often we update rolling-window features.
# A 1-second update means windows overlap.

WINDOW_UPDATE_INTERVAL_SECONDS = float(
    os.getenv("CANARY_WINDOW_UPDATE_INTERVAL", "1")
)

if WINDOW_DURATION_SECONDS <= 0:
    raise ValueError("Window duration must be positive.")

if WINDOW_UPDATE_INTERVAL_SECONDS <= 0:
    raise ValueError("Window update interval must be positive.")

if WINDOW_UPDATE_INTERVAL_SECONDS > WINDOW_DURATION_SECONDS:
    raise ValueError(
        "Window update interval cannot exceed window duration."
    )


# ---------------------------------------------------------
# Reporting tiers
# ---------------------------------------------------------

# These are reporting intervals, NOT sensor sampling rates.
#
# Tier 1: baseline reporting every 10 minutes.
# Tier 2: increased reporting every 10 seconds (provisional).
# Tier 3: high-frequency reporting every 1 second (provisional).

REPORTING_INTERVALS = {
    1: 600,
    2: 10,
    3: 1
}

DEFAULT_TIER = int(os.getenv("CANARY_DEFAULT_TIER", "1"))

if DEFAULT_TIER not in REPORTING_INTERVALS:
    raise ValueError("Default tier must be 1, 2, or 3.")


# ---------------------------------------------------------
# InfluxDB settings
# ---------------------------------------------------------

# When running locally outside Docker, localhost is appropriate.
# Inside Docker Compose, set INFLUXDB_URL=http://influxdb:8086.

INFLUXDB_URL = os.getenv(
    "INFLUXDB_URL",
    "http://localhost:8086"
)

INFLUXDB_TOKEN = os.getenv(
    "INFLUXDB_TOKEN",
    ""
)

INFLUXDB_ORG = os.getenv(
    "INFLUXDB_ORG",
    "canary"
)

INFLUXDB_BUCKET = os.getenv(
    "INFLUXDB_BUCKET",
    "sensor_data"
)


# ---------------------------------------------------------
# Database write settings
# ---------------------------------------------------------

# Number of points to accumulate before writing to InfluxDB.
# This is a storage batching setting, not a sensor sampling rate.

DATABASE_BATCH_SIZE = int(
    os.getenv("CANARY_DATABASE_BATCH_SIZE", "500")
)

DATABASE_FLUSH_INTERVAL_SECONDS = float(
    os.getenv("CANARY_DATABASE_FLUSH_INTERVAL", "1")
)


# ---------------------------------------------------------
# Device settings
# ---------------------------------------------------------

DEVICE_ID = os.getenv(
    "CANARY_DEVICE_ID",
    "CANARY_001"
)


# ---------------------------------------------------------
# Logging settings
# ---------------------------------------------------------

LOG_LEVEL = os.getenv(
    "CANARY_LOG_LEVEL",
    "INFO"
).upper()
