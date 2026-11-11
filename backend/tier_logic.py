
from backend.config import REPORTING_INTERVALS, DEFAULT_TIER


def get_reporting_interval(current_tier):
    """
    Returns the reporting interval for the current tier.
    """

    if current_tier not in REPORTING_INTERVALS:
        raise ValueError(f"Invalid tier: {current_tier}")

    return REPORTING_INTERVALS[current_tier]


def is_report_due(current_tier, elapsed_seconds):
    """
    Determines whether it is time to send another report.
    """

    interval = get_reporting_interval(current_tier)

    return elapsed_seconds >= interval


def should_send_immediate_alert(previous_tier, current_tier):
    """
    Triggers an immediate alert when entering Tier 3.
    """

    return previous_tier != 3 and current_tier == 3


if __name__ == "__main__":

    for tier in REPORTING_INTERVALS:
        interval = get_reporting_interval(tier)

        print(f"Tier {tier}: report every {interval} seconds")

    print("\nTesting reporting schedule:")

    print("Tier 1, 300 seconds elapsed:",
          is_report_due(1, 300))

    print("Tier 1, 600 seconds elapsed:",
          is_report_due(1, 600))

    print("Tier 2, 10 seconds elapsed:",
          is_report_due(2, 10))

    print("\nTesting immediate alerts:")

    print("Tier 2 -> Tier 3:",
          should_send_immediate_alert(2, 3))
