from html.parser import HTMLParser
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "backend" / "static"
HTML = (STATIC_DIR / "parent-console-v2.html").read_text(encoding="utf-8")
JAVASCRIPT = (STATIC_DIR / "parent-console-v2.js").read_text(encoding="utf-8")
CSS = (STATIC_DIR / "parent-console-v2.css").read_text(encoding="utf-8")


class _ElementCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.elements.append((tag, dict(attrs)))


def _elements() -> list[tuple[str, dict[str, str | None]]]:
    parser = _ElementCollector()
    parser.feed(HTML)
    return parser.elements


def _function_body(name: str) -> str:
    match = re.search(
        rf"function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{(?P<body>.*?)\n\}}",
        JAVASCRIPT,
        re.DOTALL,
    )
    assert match, f"missing JavaScript function: {name}"
    return match.group("body")


def test_stage_control_exposes_required_dom_contract() -> None:
    ids = {
        attrs["id"]
        for _, attrs in _elements()
        if attrs.get("id")
    }
    assert {
        "studyStageControl",
        "stageSyncStatus",
        "stageLabel",
        "stageSource",
        "policyScoreThreshold",
        "policyPersistSeconds",
        "policyCooldownSeconds",
        "policyMaxPer10Minutes",
    } <= ids

    stage_inputs = [
        attrs
        for tag, attrs in _elements()
        if tag == "input"
        and attrs.get("type") == "radio"
        and attrs.get("name") == "studyStage"
    ]
    assert {attrs.get("value") for attrs in stage_inputs} == {
        "primary",
        "middle",
        "high",
    }


def test_stage_changes_use_backend_endpoint_and_parent_source() -> None:
    assert 'fetchJson("/study-stage"' in JAVASCRIPT
    assert re.search(
        r"JSON\.stringify\(\s*\{\s*stage(?:\s*:\s*stage)?\s*,\s*"
        r"source\s*:\s*[\"']parent[\"']\s*\}\s*\)",
        JAVASCRIPT,
    )


def test_policy_is_rendered_without_frontend_offset_derivation() -> None:
    assert "score_threshold" in JAVASCRIPT
    assert "persist_seconds" in JAVASCRIPT
    assert "cooldown_seconds" in JAVASCRIPT
    assert "max_per_10_minutes" in JAVASCRIPT
    assert "scoreOffset" not in JAVASCRIPT
    assert "intervalOffset" not in JAVASCRIPT


def test_masked_mcp_token_is_not_persisted_and_uses_safe_preservation() -> None:
    local_save_body = _function_body("saveLocalSettings")
    masked_check_body = _function_body("isMaskedToken")
    assert "xiaozhiMcpToken" not in local_save_body
    assert re.search(r"/\\\*\{3,\}/\.test", masked_check_body)
    assert "tokenDirty" in JAVASCRIPT
    assert re.search(
        r"if\s*\(\s*state\.settings\.tokenDirty\s*\)"
        r"\s*\{[^}]*payload\.xiaozhiMcpToken",
        JAVASCRIPT,
        re.DOTALL,
    )
    assert "tokenPreservationValue" in JAVASCRIPT
    assert re.search(
        r"else\s+if\s*\(\s*state\.settings\.tokenPreservationValue\s*\)"
        r"\s*\{[^}]*payload\.xiaozhiMcpToken\s*="
        r"\s*state\.settings\.tokenPreservationValue",
        JAVASCRIPT,
        re.DOTALL,
    )


def test_managed_reminders_report_queue_and_mcp_runtime_state() -> None:
    assert 'fetchJson("/control"' in JAVASCRIPT
    assert 'fetchJson("/mcp/status"' in JAVASCRIPT
    assert "已入队" in JAVASCRIPT
    assert "MCP 未运行" in JAVASCRIPT


def test_stage_control_has_stable_responsive_styles() -> None:
    assert ".stage-segmented" in CSS
    assert "@media" in CSS
    assert "overflow" in CSS
