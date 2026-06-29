import pytest

from backend.study_modes import get_study_mode, normalize_stage


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("primary", "primary"),
        ("小学", "primary"),
        ("小学生", "primary"),
        ("middle", "middle"),
        ("初中", "middle"),
        ("初中生", "middle"),
        ("high", "high"),
        ("高中", "high"),
        ("高中生", "high"),
    ],
)
def test_stage_aliases_are_normalized(value, expected):
    assert normalize_stage(value) == expected


def test_unknown_stage_is_rejected():
    with pytest.raises(ValueError, match="invalid_study_stage"):
        normalize_stage("大学")


def test_mode_policy_matches_approved_design():
    primary = get_study_mode("primary")
    middle = get_study_mode("middle")
    high = get_study_mode("high")

    assert (
        primary.score_threshold,
        primary.persist_seconds,
        primary.cooldown_seconds,
        primary.max_per_10_minutes,
    ) == (55, 20, 180, 2)
    assert (
        middle.score_threshold,
        middle.persist_seconds,
        middle.cooldown_seconds,
        middle.max_per_10_minutes,
    ) == (65, 15, 120, 3)
    assert (
        high.score_threshold,
        high.persist_seconds,
        high.cooldown_seconds,
        high.max_per_10_minutes,
    ) == (70, 25, 240, 2)


def test_mode_serialization_uses_v2_policy_field_names():
    mode = get_study_mode("初中").as_dict()

    assert mode["key"] == "middle"
    assert mode["label"] == "初中"
    assert mode["score_threshold"] == 65
    assert mode["persist_seconds"] == 15
