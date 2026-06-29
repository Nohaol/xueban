from __future__ import annotations

from backend.reminder_policy import ReminderPolicy


class Clock:
    def __init__(self, now: float = 100.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def distracted_payload(score=40):
    return {
        "status": "distracted",
        "focusScore": score,
        "awaySeconds": 0,
        "metrics": {"posture": 80},
    }


def mark_sent(policy, reminder):
    assert reminder is not None
    policy.mark_sent(reminder)
    return reminder


def test_primary_waits_twenty_seconds_and_returns_stage_metadata():
    clock = Clock()
    policy = ReminderPolicy(clock=clock)

    assert policy.observe(distracted_payload(), "primary") is None
    clock.now = 119.0
    assert policy.observe(distracted_payload(), "primary") is None
    clock.now = 120.0
    reminder = policy.observe(distracted_payload(), "primary")

    assert reminder["studyStage"] == "primary"
    assert reminder["stageLabel"] == "小学"
    assert reminder["policyVersion"] == "stage-v1"


def test_score_at_threshold_does_not_start_or_continue_timer():
    clock = Clock()
    policy = ReminderPolicy(clock=clock)

    policy.observe(distracted_payload(score=64), "middle")
    clock.now = 114.0
    assert policy.observe(distracted_payload(score=65), "middle") is None
    clock.now = 115.0
    assert policy.observe(distracted_payload(score=64), "middle") is None
    clock.now = 130.0
    assert policy.observe(distracted_payload(score=64), "middle") is not None


def test_recovery_resets_persistence_timer():
    clock = Clock()
    policy = ReminderPolicy(clock=clock)

    policy.observe(distracted_payload(), "high")
    clock.now = 124.0
    assert policy.observe({"status": "normal", "focusScore": 90}, "high") is None
    clock.now = 125.0
    assert policy.observe(distracted_payload(), "high") is None
    clock.now = 149.0
    assert policy.observe(distracted_payload(), "high") is None
    clock.now = 150.0
    assert policy.observe(distracted_payload(), "high")["studyStage"] == "high"


def test_high_school_message_is_not_childish():
    clock = Clock()
    policy = ReminderPolicy(clock=clock)

    policy.observe(distracted_payload(), "high")
    clock.now = 125.0
    reminder = policy.observe(distracted_payload(), "high")

    assert "题组" in reminder["text"]
    assert "小朋友" not in reminder["text"]


def test_primary_cooldown_and_ten_minute_frequency_limit():
    clock = Clock()
    policy = ReminderPolicy(clock=clock)

    policy.observe(distracted_payload(), "primary")
    clock.now = 120.0
    mark_sent(policy, policy.observe(distracted_payload(), "primary"))
    clock.now = 299.0
    assert policy.observe(distracted_payload(), "primary") is None
    clock.now = 300.0
    mark_sent(policy, policy.observe(distracted_payload(), "primary"))
    clock.now = 480.0
    assert policy.observe(distracted_payload(), "primary") is None
    clock.now = 721.0
    mark_sent(policy, policy.observe(distracted_payload(), "primary"))


def test_stage_cooldowns_are_independent():
    clock = Clock()
    policy = ReminderPolicy(clock=clock)

    policy.observe(distracted_payload(), "middle")
    clock.now = 115.0
    mark_sent(policy, policy.observe(distracted_payload(), "middle"))
    assert policy.observe(distracted_payload(), "primary") is None
    clock.now = 135.0
    mark_sent(policy, policy.observe(distracted_payload(), "primary"))


def test_restart_preserves_stage_cooldown_and_frequency_window(tmp_path):
    clock = Clock()
    path = tmp_path / "reminder_policy.json"
    first = ReminderPolicy(clock=clock, state_path=path)
    first.observe(distracted_payload(), "primary")
    clock.now = 120.0
    mark_sent(first, first.observe(distracted_payload(), "primary"))

    restarted = ReminderPolicy(clock=clock, state_path=path)
    clock.now = 121.0
    assert restarted.observe(distracted_payload(), "primary") is None
    clock.now = 141.0
    assert restarted.observe(distracted_payload(), "primary") is None
    clock.now = 300.0
    assert restarted.observe(distracted_payload(), "primary") is not None
