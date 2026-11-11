
from backend.config import (
    ECG_RATE,
    PPG_RATE,
    BIOIMPEDANCE_RATE,
    IMU_RATE,
)


def validate_batch(batch):
    """
    Checks whether a sensor batch contains valid, complete data.

    Returns:
        A list of errors. An empty list means the batch is valid.
    """

    errors = []

    # Check required metadata
    required_fields = ["device_id", "timestamp", "sequence_number", "sensor_data"]

    for field in required_fields:
        if field not in batch:
            errors.append(f"Missing field: {field}")

    if errors:
        return errors

    sensor_data = batch["sensor_data"]

    # Expected sample counts for one-second batches
    expected_rates = {
        "ecg": ECG_RATE,
        "ppg": PPG_RATE,
        "bioimpedance": BIOIMPEDANCE_RATE,
        "imu": IMU_RATE,
    }

    # Check that each sensor exists and has the expected number of samples
    for sensor, expected_count in expected_rates.items():

        if sensor not in sensor_data:
            errors.append(f"Missing sensor: {sensor}")
            continue

        samples = sensor_data[sensor].get("samples")

        if not isinstance(samples, list):
            errors.append(f"{sensor}: samples must be a list")
            continue

        if len(samples) != expected_count:
            errors.append(
                f"{sensor}: expected {expected_count} samples, "
                f"received {len(samples)}"
            )

    # Check temperature
    if "temperature" not in sensor_data:
        errors.append("Missing sensor: temperature")

    elif "value" not in sensor_data["temperature"]:
        errors.append("Temperature reading is missing")

    return errors



if __name__ == "__main__":
    from backend.simulator import generate_batch

    batch = generate_batch(1)

    errors = validate_batch(batch)

    if not errors:
        print("Batch is VALID")
    else:
        print("Batch is INVALID:")
        for error in errors:
            print("-", error)
