from __future__ import annotations

from backend.engine import EngineConfig, FocusEngine
from backend.reminder_policy import ReminderPolicy
from backend.runtime_state import RuntimeStateStore
from backend.xiaozhi_bridge import ReminderStore


class Clock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


def make_engine(tmp_path, clock=None, active_speech=None):
    state = RuntimeStateStore(tmp_path / "state.json")
    reminders = ReminderStore(
        tmp_path / "reminders.json",
        state_store=state,
        clock=clock or Clock(),
    )
    policy = ReminderPolicy(clock=clock or Clock())
    engine = FocusEngine(
        EngineConfig(mock_mode=True),
        state_store=state,
        reminder_store=reminders,
        reminder_policy=policy,
        active_speech=active_speech,
    )
    return engine, state, reminders


def test_engine_payload_reads_current_persisted_stage(tmp_path):
    engine, state, _ = make_engine(tmp_path)

    assert engine.get_payload()["studyStage"] == "middle"
    state.set_stage("小学", "parent")
    payload = engine.get_payload()

    assert payload["studyStage"] == "primary"
    assert payload["stageLabel"] == "小学"


def test_engine_runs_automatic_reminder_after_analysis(tmp_path):
    clock = Clock()
    engine, _, reminders = make_engine(tmp_path, clock=clock)
    payload = {
        "status": "distracted",
        "focusScore": 40,
        "awaySeconds": 0,
        "metrics": {"gaze": 40, "posture": 70, "stability": 60, "presence": 100},
    }

    assert engine.process_automatic_reminder(payload) is None
    clock.now = 115.0
    reminder = engine.process_automatic_reminder(payload)

    assert reminder["studyStage"] == "middle"
    snapshot = reminders.snapshot()
    assert snapshot["pendingCount"] == 1
    assert snapshot["items"][0]["command"] == "managed_ai_reminder"


def test_engine_dispatches_automatic_reminder_to_active_speech(tmp_path):
    clock = Clock()

    class Dispatcher:
        def __init__(self):
            self.items = []

        def dispatch(self, item):
            self.items.append(item)
            return True

    dispatcher = Dispatcher()
    engine, _, _ = make_engine(
        tmp_path,
        clock=clock,
        active_speech=dispatcher,
    )
    payload = {
        "status": "distracted",
        "focusScore": 40,
        "awaySeconds": 0,
        "metrics": {},
    }

    engine.process_automatic_reminder(payload)
    clock.now = 115.0
    engine.process_automatic_reminder(payload)

    assert len(dispatcher.items) == 1
    assert dispatcher.items[0]["command"] == "managed_ai_reminder"


def test_engine_settings_update_away_timeout_and_legacy_age_mode(tmp_path):
    engine, state, _ = make_engine(tmp_path)

    result = engine.update_settings(
        {
            "awayTimeoutMinutes": 25,
            "ageMode": "high",
            "stageSource": "parent",
        }
    )

    assert engine.config.away_timeout_seconds == 25 * 60
    assert result["studyStage"] == "high"
    assert result["ageMode"] == "high"
    assert state.read()["stageSource"] == "parent"


def test_automatic_reminder_persists_the_policy_stage_snapshot(tmp_path):
    clock = Clock()
    state = RuntimeStateStore(tmp_path / "state.json")

    class SwitchingReminderStore(ReminderStore):
        def enqueue(
            self,
            command,
            text,
            focus_payload=None,
            reminder_metadata=None,
        ):
            state.set_stage("高中", "voice")
            if reminder_metadata is None:
                return super().enqueue(command, text, focus_payload)
            return super().enqueue(
                command,
                text,
                focus_payload,
                reminder_metadata=reminder_metadata,
            )

    reminders = SwitchingReminderStore(
        tmp_path / "reminders.json",
        state_store=state,
        clock=clock,
    )
    engine = FocusEngine(
        EngineConfig(mock_mode=True),
        state_store=state,
        reminder_store=reminders,
        reminder_policy=ReminderPolicy(clock=clock),
    )
    payload = {
        "status": "distracted",
        "focusScore": 40,
        "awaySeconds": 0,
        "metrics": {},
    }

    engine.process_automatic_reminder(payload)
    clock.now = 115.0
    reminder = engine.process_automatic_reminder(payload)
    queued = reminders.snapshot()["items"][0]

    assert state.read()["studyStage"] == "high"
    assert reminder["studyStage"] == "middle"
    assert queued["studyStage"] == "middle"
    assert queued["stageLabel"] == "初中"
    assert queued["text"] == reminder["text"]


def test_engine_settings_fully_mask_short_mcp_tokens(tmp_path):
    engine, state, _ = make_engine(tmp_path)
    state.update(
        {
            "xiaozhiMcpUrl": "wss://api.xiaozhi.me/mcp/",
            "xiaozhiMcpToken": "short",
        }
    )

    settings = engine.get_settings()

    assert settings["xiaozhiMcpToken"] == "*****"
    assert "short" not in repr(settings)


def test_automatic_reminder_recovers_after_state_read_error(
    tmp_path,
    monkeypatch,
):
    engine, state, _ = make_engine(tmp_path)
    original_read = state.read
    calls = 0

    def fail_once():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("disk unavailable")
        return original_read()

    monkeypatch.setattr(state, "read", fail_once)

    assert engine.process_automatic_reminder({"status": "normal"}) is None
    assert engine.last_reminder_error == "state_read:OSError"
    assert engine.process_automatic_reminder({"status": "normal"}) is None
    assert calls == 2


def test_automatic_reminder_recovers_after_policy_error(tmp_path):
    class FailOncePolicy:
        def __init__(self):
            self.calls = 0

        def observe(self, payload, stage):
            self.calls += 1
            if self.calls == 1:
                raise ValueError("bad policy state")
            return None

    engine, _, _ = make_engine(tmp_path)
    policy = FailOncePolicy()
    engine.reminder_policy = policy

    assert engine.process_automatic_reminder({"status": "normal"}) is None
    assert engine.last_reminder_error == "policy_observe:ValueError"
    assert engine.process_automatic_reminder({"status": "normal"}) is None
    assert policy.calls == 2


def test_automatic_reminder_recovers_after_enqueue_error(
    tmp_path,
    monkeypatch,
):
    engine, _, reminders = make_engine(tmp_path)
    reminder = {
        "text": "continue",
        "studyStage": "middle",
        "stageLabel": "鍒濅腑",
        "policyVersion": "stage-v1",
    }

    class AlwaysReminderPolicy:
        def observe(self, payload, stage):
            return dict(reminder)

    engine.reminder_policy = AlwaysReminderPolicy()
    original_enqueue = reminders.enqueue
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("queue unavailable")
        return original_enqueue(*args, **kwargs)

    monkeypatch.setattr(reminders, "enqueue", fail_once)

    assert engine.process_automatic_reminder({"status": "normal"}) is None
    assert engine.last_reminder_error == "enqueue:OSError"
    assert engine.process_automatic_reminder({"status": "normal"}) == reminder
    assert reminders.snapshot()["pendingCount"] == 1


def test_real_policy_retries_next_frame_after_enqueue_failure(
    tmp_path,
    monkeypatch,
):
    clock = Clock()
    engine, _, reminders = make_engine(tmp_path, clock=clock)
    policy_path = tmp_path / "reminder_policy.json"
    engine.reminder_policy = ReminderPolicy(clock=clock, state_path=policy_path)
    original_enqueue = reminders.enqueue
    enqueue_calls = 0
    payload = {
        "status": "distracted",
        "focusScore": 40,
        "awaySeconds": 0,
        "metrics": {},
    }

    def fail_once(*args, **kwargs):
        nonlocal enqueue_calls
        enqueue_calls += 1
        if enqueue_calls == 1:
            raise OSError("queue unavailable")
        return original_enqueue(*args, **kwargs)

    monkeypatch.setattr(reminders, "enqueue", fail_once)

    assert engine.process_automatic_reminder(payload) is None
    clock.now = 115.0
    assert engine.process_automatic_reminder(payload) is None
    clock.now = 116.0
    retried = engine.process_automatic_reminder(payload)

    assert retried["studyStage"] == "middle"
    assert reminders.snapshot()["pendingCount"] == 1

    clock.now = 117.0
    assert engine.process_automatic_reminder(payload) is None
    assert enqueue_calls == 2

    restarted = ReminderPolicy(clock=clock, state_path=policy_path)
    assert restarted.observe(payload, "middle") is None
    clock.now = 132.0
    assert restarted.observe(payload, "middle") is None


def test_automatic_reminder_caches_stage_for_at_most_one_second(
    tmp_path,
    monkeypatch,
):
    engine, state, _ = make_engine(tmp_path)
    original_read = state.read
    reads = 0

    def counted_read():
        nonlocal reads
        reads += 1
        return original_read()

    monkeypatch.setattr(state, "read", counted_read)
    payload = {"status": "normal"}

    engine.process_automatic_reminder(payload)
    engine.process_automatic_reminder(payload)
    assert reads == 1

    engine._reminder_stage_cache_at -= 1.01
    engine.process_automatic_reminder(payload)

    assert reads == 2
