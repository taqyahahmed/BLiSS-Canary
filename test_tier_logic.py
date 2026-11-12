
from backend.tier_logic import TierManager


def test_default_tier():
    manager = TierManager()
    assert manager.current_tier == 1
    assert manager.get_reporting_interval() == 600


def test_escalation_to_tier_3():
    manager = TierManager()

    manager.set_alert("ecg_alert", active=True, required_tier=3)

    assert manager.current_tier == 3
    assert manager.get_reporting_interval() == 1


def test_escalation_to_tier_2():
    manager = TierManager()

    manager.set_alert("sensor_alert", active=True, required_tier=2)

    assert manager.current_tier == 2
    assert manager.get_reporting_interval() == 10


def test_highest_active_alert_wins():
    manager = TierManager()

    manager.set_alert("alert_1", active=True, required_tier=2)
    manager.set_alert("alert_2", active=True, required_tier=3)

    assert manager.current_tier == 3

    # Removing the Tier 3 alert leaves the Tier 2 alert active.
    manager.set_alert("alert_2", active=False)

    assert manager.current_tier == 2


def test_recovery_delay():
    manager = TierManager(recovery_delay_seconds=0)

    manager.set_alert("ecg_alert", active=True, required_tier=3)
    manager.set_alert("ecg_alert", active=False)

    # With zero recovery delay, the next update returns to Tier 1.
    manager.update()

    assert manager.current_tier == 1


def test_manual_tier_request():
    manager = TierManager()

    manager.request_tier(2)
    assert manager.current_tier == 2

    manager.request_tier(1)
    assert manager.current_tier == 1


def test_alert_overrides_manual_request():
    manager = TierManager()

    manager.set_alert("critical_alert", active=True, required_tier=3)
    manager.request_tier(1)

    assert manager.current_tier == 3


def test_invalid_tier_rejected():
    manager = TierManager()

    try:
        manager.request_tier(4)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid tier should raise ValueError")


def test_reset():
    manager = TierManager()

    manager.set_alert("ecg_alert", active=True, required_tier=3)
    manager.reset()

    assert manager.current_tier == 1
    assert manager.active_alerts == {}


if __name__ == "__main__":
    tests = [
        test_default_tier,
        test_escalation_to_tier_3,
        test_escalation_to_tier_2,
        test_highest_active_alert_wins,
        test_recovery_delay,
        test_manual_tier_request,
        test_alert_overrides_manual_request,
        test_invalid_tier_rejected,
        test_reset,
    ]

    for test in tests:
        test()
        print(f"PASSED: {test.__name__}")

    print("\nALL TIER LOGIC TESTS PASSED!")
