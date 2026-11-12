
"""
CANARY Signal Processing
------------------------
Calculates features from sliding-window snapshots.

Responsibilities:
1. Calculate numerical statistics for ECG, PPG, and bioimpedance.
2. Extract acceleration, magnetometer, and gyroscope features from IMU.
3. Calculate temperature statistics and trends.
4. Preserve window metadata.
5. Return structured feature results for database storage and API delivery.

This module does NOT modify or discard raw waveform samples.
"""

import math
import statistics


# ---------------------------------------------------------
# General numerical helpers
# ---------------------------------------------------------

def is_valid_number(value):
    """Check whether a value is a finite number."""

    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def extract_numeric_values(values):
    """
    Extract finite numerical values from a list.

    Supports:
        [1.0, 2.0, 3.0]

    Also supports:
        [{"value": 1.0}, {"value": 2.0}]
    """

    result = []

    for value in values:

        if isinstance(value, dict):
            value = value.get("value")

        if is_valid_number(value):
            result.append(float(value))

    return result


def calculate_statistics(values):
    """Calculate basic descriptive statistics."""

    values = extract_numeric_values(values)

    if not values:
        return {}

    result = {
        "mean": statistics.fmean(values),
        "minimum": min(values),
        "maximum": max(values),
        "standard_deviation": statistics.pstdev(values),
        "root_mean_square": math.sqrt(
            statistics.fmean([value ** 2 for value in values])
        ),
        "peak_to_peak": max(values) - min(values),
        "sample_count": len(values),
    }

    return result


def calculate_trend(values, timestamps):
    """
    Calculate the least-squares slope over time.

    The slope represents change in value per second.
    """

    if len(values) != len(timestamps):
        return None

    if len(values) < 2:
        return None

    if not all(is_valid_number(value) for value in values):
        return None

    if not all(is_valid_number(timestamp) for timestamp in timestamps):
        return None

    start_time = timestamps[0]

    x_values = [
        timestamp - start_time
        for timestamp in timestamps
    ]

    x_mean = statistics.fmean(x_values)
    y_mean = statistics.fmean(values)

    denominator = sum(
        (x - x_mean) ** 2
        for x in x_values
    )

    if denominator == 0:
        return None

    numerator = sum(
        (x - x_mean) * (y - y_mean)
        for x, y in zip(x_values, values)
    )

    return numerator / denominator


# ---------------------------------------------------------
# Window data helpers
# ---------------------------------------------------------

def get_window_values(window):
    """Extract sample values from a window snapshot."""

    return [
        sample.get("value")
        for sample in window.get("samples", [])
        if isinstance(sample, dict) and "value" in sample
    ]


def get_window_timestamps(window):
    """Extract sample timestamps from a window snapshot."""

    return [
        sample.get("timestamp")
        for sample in window.get("samples", [])
        if isinstance(sample, dict) and "timestamp" in sample
    ]


def build_result(sensor_name, window, features):
    """Attach common window metadata to calculated features."""

    return {
        "sensor": sensor_name,
        "sampling_rate_hz": window.get("sampling_rate_hz"),
        "window_duration_seconds": window.get("duration_seconds"),
        "sample_count": window.get("sample_count", 0),
        "expected_sample_count": window.get("expected_sample_count"),
        "is_full": window.get("is_full", False),
        "start_timestamp": window.get("start_timestamp"),
        "end_timestamp": window.get("end_timestamp"),
        "features": features,
    }


# ---------------------------------------------------------
# ECG processing
# ---------------------------------------------------------

def process_ecg(window):
    """
    Calculate basic ECG signal statistics.

    These are signal-description features, not clinical
    heart-rate or diagnostic measurements.
    """

    values = extract_numeric_values(get_window_values(window))

    features = calculate_statistics(values)

    features["valid_sample_count"] = len(values)

    return build_result("ecg", window, features)


# ---------------------------------------------------------
# PPG processing
# ---------------------------------------------------------

def process_ppg(window):
    """Calculate basic PPG signal statistics."""

    values = extract_numeric_values(get_window_values(window))

    features = calculate_statistics(values)

    features["valid_sample_count"] = len(values)

    return build_result("ppg", window, features)


# ---------------------------------------------------------
# Bioimpedance processing
# ---------------------------------------------------------

def process_bioimpedance(window):
    """Calculate basic bioimpedance signal statistics."""

    values = extract_numeric_values(get_window_values(window))

    features = calculate_statistics(values)

    features["valid_sample_count"] = len(values)

    return build_result("bioimpedance", window, features)


# ---------------------------------------------------------
# IMU processing
# ---------------------------------------------------------

def extract_xyz(values, component):
    """
    Extract X, Y, and Z values from nested IMU samples.

    Supports structures such as:
        {
            "acceleration": {"x": 1, "y": 2, "z": 3},
            "magnetometer": {"x": 4, "y": 5, "z": 6},
            "gyroscope": {"x": 7, "y": 8, "z": 9}
        }
    """

    axes = {
        "x": [],
        "y": [],
        "z": [],
    }

    for value in values:

        if not isinstance(value, dict):
            continue

        component_values = value.get(component, {})

        if not isinstance(component_values, dict):
            continue

        for axis in axes:

            axis_value = component_values.get(axis)

            if is_valid_number(axis_value):
                axes[axis].append(float(axis_value))

    return axes


def calculate_vector_magnitude(axes):
    """Calculate vector magnitude for matching XYZ samples."""

    count = min(
        len(axes["x"]),
        len(axes["y"]),
        len(axes["z"]),
    )

    magnitudes = []

    for index in range(count):

        x = axes["x"][index]
        y = axes["y"][index]
        z = axes["z"][index]

        magnitude = math.sqrt(
            x ** 2 + y ** 2 + z ** 2
        )

        magnitudes.append(magnitude)

    return magnitudes


def process_imu(window):
    """
    Calculate IMU features.

    Processes acceleration, magnetometer, and gyroscope
    separately when those components are available.
    """

    values = get_window_values(window)

    features = {}

    for component in (
        "acceleration",
        "magnetometer",
        "gyroscope",
    ):

        axes = extract_xyz(values, component)

        if not any(axes.values()):
            continue

        component_features = {}

        for axis in ("x", "y", "z"):

            if axes[axis]:
                component_features[axis] = calculate_statistics(
                    axes[axis]
                )

        magnitudes = calculate_vector_magnitude(axes)

        if magnitudes:
            component_features["magnitude"] = calculate_statistics(
                magnitudes
            )

        features[component] = component_features

    return build_result("imu", window, features)


# ---------------------------------------------------------
# Temperature processing
# ---------------------------------------------------------

def process_temperature(window):
    """Calculate temperature statistics and trend."""

    values = get_window_values(window)
    timestamps = get_window_timestamps(window)

    numeric_values = extract_numeric_values(values)

    features = calculate_statistics(numeric_values)

    features["trend_per_second"] = calculate_trend(
        numeric_values,
        timestamps,
    )

    features["valid_sample_count"] = len(numeric_values)

    # Preserve the unit when supplied by the incoming data.
    for value in values:

        if isinstance(value, dict) and value.get("unit"):
            features["unit"] = value["unit"]
            break

    return build_result("temperature", window, features)


# ---------------------------------------------------------
# Main processing interface
# ---------------------------------------------------------

PROCESSORS = {
    "ecg": process_ecg,
    "ppg": process_ppg,
    "bioimpedance": process_bioimpedance,
    "imu": process_imu,
    "temperature": process_temperature,
}


def process_window(sensor_name, window):
    """
    Process one sensor window.

    Returns a structured feature dictionary.
    """

    if sensor_name not in PROCESSORS:
        raise ValueError(
            f"No processor registered for sensor: {sensor_name}"
        )

    if not isinstance(window, dict):
        raise TypeError("Window must be a dictionary.")

    return PROCESSORS[sensor_name](window)


def process_ready_windows(windows):
    """
    Process a dictionary of ready sensor windows.

    Example:
        {
            "ecg": ecg_window,
            "ppg": ppg_window
        }

    Returns:
        {
            "ecg": ecg_features,
            "ppg": ppg_features
        }
    """

    results = {}

    for sensor_name, window in windows.items():

        results[sensor_name] = process_window(
            sensor_name,
            window,
        )

    return results


def process_all_windows(windows):
    """
    Process snapshots of all available sensor windows.

    Unlike process_ready_windows, this does not determine
    whether a window is ready. That decision belongs to
    WindowManager.
    """

    return process_ready_windows(windows)
