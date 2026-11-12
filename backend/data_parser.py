
import re
from datetime import datetime, timezone
from typing import Any


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"

TEMPERATURE_RE = re.compile(
    rf"Temperature\s+({NUMBER})",
    re.IGNORECASE,
)

ACCEL_RE = re.compile(
    rf"Accel\s+X:\s*({NUMBER})\s+Y:\s*({NUMBER})\s+Z:\s*({NUMBER})",
    re.IGNORECASE,
)

MAG_RE = re.compile(
    rf"Mag\s+X:\s*({NUMBER})\s+Y:\s*({NUMBER})\s+Z:\s*({NUMBER})",
    re.IGNORECASE,
)

GYRO_RE = re.compile(
    rf"Gyro\s+X:\s*({NUMBER})\s+Y:\s*({NUMBER})\s+Z:\s*({NUMBER})",
    re.IGNORECASE,
)


class SensorTextParser:
    def __init__(self, device_id: str = "CANARY_001"):
        self.device_id = device_id
        self.sequence_number = 0
        self._current_values: dict[str, float] = {}

    def parse_line(self, line: str) -> dict[str, Any] | None:
        line = line.strip()

        if not line:
            return None

        temperature = TEMPERATURE_RE.search(line)

        if temperature:
            self._current_values = {
                "temperature": float(temperature.group(1))
            }
            return None

        accel = ACCEL_RE.search(line)

        if accel:
            self._current_values.update({
                "accel_x": float(accel.group(1)),
                "accel_y": float(accel.group(2)),
                "accel_z": float(accel.group(3)),
            })
            return None

        mag = MAG_RE.search(line)

        if mag:
            self._current_values.update({
                "mag_x": float(mag.group(1)),
                "mag_y": float(mag.group(2)),
                "mag_z": float(mag.group(3)),
            })
            return None

        gyro = GYRO_RE.search(line)

        if gyro:
            self._current_values.update({
                "gyro_x": float(gyro.group(1)),
                "gyro_y": float(gyro.group(2)),
                "gyro_z": float(gyro.group(3)),
            })

            required_keys = {
                "temperature",
                "accel_x", "accel_y", "accel_z",
                "mag_x", "mag_y", "mag_z",
                "gyro_x", "gyro_y", "gyro_z",
            }

            if not required_keys.issubset(self._current_values):
                self._current_values = {}
                return None

            self.sequence_number += 1

            record = {
                "device_id": self.device_id,
                "sequence_number": self.sequence_number,
                "received_at": datetime.now(timezone.utc).isoformat(),
                "source_timestamp": None,
                "values": self._current_values.copy(),
            }

            self._current_values = {}
            return record

        return None

    def parse_text(self, text: str) -> list[dict[str, Any]]:
        records = []

        for line in text.splitlines():
            record = self.parse_line(line)

            if record is not None:
                records.append(record)

        return records


def parse_text(
    text: str,
    device_id: str = "CANARY_001",
) -> list[dict[str, Any]]:
    parser = SensorTextParser(device_id=device_id)
    return parser.parse_text(text)


if __name__ == "__main__":
    sample_text = """
    Temperature 26.18 deg C
    Accel X: -0.88  Y: 2.02  Z: 9.91 m/s^2
    Mag X: -20.85  Y: 22.95  Z: 92.85 uT
    Gyro X: 0.03  Y: -0.02  Z: 0.01 radians/s

    Temperature 26.13 deg C
    Accel X: -0.81  Y: 2.02  Z: 10.01 m/s^2
    Mag X: -22.20  Y: 23.70  Z: 93.60 uT
    Gyro X: 0.03  Y: -0.02  Z: 0.02 radians/s
    """

    parser = SensorTextParser()

    for record in parser.parse_text(sample_text):
        print(record)
