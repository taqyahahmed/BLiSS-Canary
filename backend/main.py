
import time

from backend.config import DEFAULT_TIER
from backend.simulator import generate_batch
from backend.validation import validate_batch
from backend.processing import process_batch
from backend.database import create_client, write_batch
from backend.tier_logic import (
    get_reporting_interval,
    is_report_due,
)


def main():
    sequence_number = 1
    current_tier = DEFAULT_TIER

    # Track when the last report was sent
    last_report_time = time.monotonic()

    reporting_interval = get_reporting_interval(current_tier)

    print("Starting CANARY monitoring system...")
    print(f"Current tier: {current_tier}")
    print(f"Reporting interval: {reporting_interval} seconds")
    print("Press Ctrl+C to stop.\n")

    client = create_client()

    try:
        while True:
            start_time = time.monotonic()

            # 1. Generate a sensor batch
            batch = generate_batch(sequence_number)

            # 2. Validate the batch
            errors = validate_batch(batch)

            if errors:
                print(f"Batch {sequence_number} | INVALID")
                for error in errors:
                    print("-", error)

            else:
                print(f"Batch {sequence_number} | VALID")

                # 3. Process the validated sensor data
                features = process_batch(batch)
                print(f"Processed features: {features}")

                # 4. Save processed data to InfluxDB
                write_batch(client, batch, features)
                print("Batch saved to InfluxDB!")

                # 5. Check whether a report is due
                elapsed = time.monotonic() - last_report_time

                if is_report_due(current_tier, elapsed):
                    print("\n--- CANARY REPORT ---")
                    print(f"Device: {batch['device_id']}")
                    print(f"Timestamp: {batch['timestamp']}")
                    print(f"Sequence: {sequence_number}")
                    print(f"Current tier: {current_tier}")
                    print("---------------------\n")

                    last_report_time = time.monotonic()

            sequence_number += 1

            # 6. Maintain approximately one-second collection cycles
            elapsed = time.monotonic() - start_time
            remaining = 1.0 - elapsed

            if remaining > 0:
                time.sleep(remaining)

    except KeyboardInterrupt:
        print("\nStopping CANARY monitoring system...")

    finally:
        client.close()
        print("Database connection closed.")


if __name__ == "__main__":
    main()
