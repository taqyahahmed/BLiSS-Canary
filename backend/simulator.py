import time
import math
import random
import json
from datetime import datetime, timezone
from backend.validation import validate_batch


from backend.config import (
    ECG_RATE,
    PPG_RATE,
    BIOIMPEDANCE_RATE,
    IMU_RATE,
    TEMPERATURE_RATE
)


def generate_batch(sequence_number):

    # Timestamp marking the beginning of this batch
    timestamp = datetime.now(timezone.utc).isoformat()

    # Generate synthetic ECG readings
    ecg = [
        0.5 * math.sin(2 * math.pi * 1.2 * i / ECG_RATE)
        + random.uniform(-0.05, 0.05)
        for i in range(ECG_RATE)
    ]

    # Generate synthetic PPG readings
    ppg = [
        1.0 + 0.3 * math.sin(2 * math.pi * 1.2 * i / PPG_RATE)
        + random.uniform(-0.03, 0.03)
        for i in range(PPG_RATE)
    ]

    # Generate synthetic bioimpedance readings (ohms)
    bioimpedance = [
        500 + 5 * math.sin(2 * math.pi * 0.2 * i / BIOIMPEDANCE_RATE)
        + random.uniform(-0.5, 0.5)
        for i in range(BIOIMPEDANCE_RATE)
    ]

    # Generate synthetic IMU readings (three axes)
    imu = [
        {
            "x": random.uniform(-0.1, 0.1),
            "y": random.uniform(-0.1, 0.1),
            "z": 9.81 + random.uniform(-0.1, 0.1)
        }
        for _ in range(IMU_RATE)
    ]

    # Generate one temperature reading
    temperature = 36.8 + random.uniform(-0.1, 0.1)

    # Combine everything into one batch
    batch = {
        "device_id": "CANARY_001",
        "sequence_number": sequence_number,
        "timestamp": timestamp,
        "synthetic": True,
        "duration_seconds": 1,
        "sensor_data": {
            "ecg": {
                "sampling_rate_hz": ECG_RATE,
                "unit": "mV",
                "samples": ecg
            },
            "ppg": {
                "sampling_rate_hz": PPG_RATE,
                "unit": "arbitrary",
                "samples": ppg
            },
            "bioimpedance": {
                "sampling_rate_hz": BIOIMPEDANCE_RATE,
                "unit": "ohm",
                "samples": bioimpedance
            },
            "imu": {
                "sampling_rate_hz": IMU_RATE,
                "unit": "m/s^2",
                "samples": imu
            },
            "temperature": {
                "sampling_rate_hz": TEMPERATURE_RATE,
                "unit": "C",
                "value": temperature
            }
        }
    }

    return batch


if __name__ == "__main__":

    sequence_number = 1

    print("Starting CANARY sensor simulator...")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:

            # Record when this collection cycle starts
            start_time = time.monotonic()

            # Generate a batch
            batch = generate_batch(sequence_number)

            # Validate the batch
            errors = validate_batch(batch)

            if not errors:
                print(
                    f"Batch {sequence_number} | "
                    f"Timestamp: {batch['timestamp']} | "
                    "VALID"
                )
            else:
                print(f"Batch {sequence_number} | INVALID")
                for error in errors:
                    print("-", error)

            sequence_number += 1

            # Wait until approximately one second has passed
            elapsed = time.monotonic() - start_time
            remaining = 1.0 - elapsed

            if remaining > 0:
                time.sleep(remaining)

    except KeyboardInterrupt:
        print("\nStopping CANARY simulator...")
