
import statistics


def calculate_signal_statistics(samples):
    """
    Calculates basic descriptive statistics for a sensor signal.
    """

    return {
        "mean": statistics.mean(samples),
        "minimum": min(samples),
        "maximum": max(samples),
        "std_dev": statistics.pstdev(samples)
    }


def process_batch(batch):
    """
    Extracts basic features from a validated sensor batch.
    """

    sensor_data = batch["sensor_data"]

    features = {}

    # ECG features
    features["ecg"] = calculate_signal_statistics(
        sensor_data["ecg"]["samples"]
    )

    # PPG features
    features["ppg"] = calculate_signal_statistics(
        sensor_data["ppg"]["samples"]
    )

    # Bioimpedance features
    features["bioimpedance"] = calculate_signal_statistics(
        sensor_data["bioimpedance"]["samples"]
    )

    # IMU: calculate acceleration magnitude for each reading
    imu_samples = sensor_data["imu"]["samples"]

    magnitudes = [
        (sample["x"]**2 + sample["y"]**2 + sample["z"]**2)**0.5
        for sample in imu_samples
    ]

    features["imu"] = {
        "average_acceleration_magnitude": statistics.mean(magnitudes)
    }

    # Temperature
    features["temperature"] = sensor_data["temperature"]["value"]

    return features


if __name__ == "__main__":
    from backend.simulator import generate_batch

    batch = generate_batch(1)
    features = process_batch(batch)

    print("Processed sensor features:")
    for sensor, values in features.items():
        print(f"\n{sensor}: {values}")
