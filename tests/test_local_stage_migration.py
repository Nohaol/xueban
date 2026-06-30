from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SERVER = (
    ROOT
    / "xiaozhi-server-sandbox"
    / "source-complete"
    / "xiaozhi-esp32-server-main"
    / "main"
    / "xiaozhi-server"
)
STUDY_STAGE_MODULE = SERVER / "core" / "utils" / "study_stage.py"
MESSAGE_TYPES = SERVER / "core" / "handle" / "textMessageType.py"
REGISTRY = SERVER / "core" / "handle" / "textMessageHandlerRegistry.py"
SETUP_HANDLER = (
    SERVER
    / "core"
    / "handle"
    / "textHandler"
    / "studyStageSetupMessageHandler.py"
)
RECEIVE_AUDIO = SERVER / "core" / "handle" / "receiveAudioHandle.py"
FIRMWARE = ROOT / "xiaozhi-esp32" / "main"
PROTOCOL_HEADER = FIRMWARE / "protocols" / "protocol.h"
PROTOCOL_SOURCE = FIRMWARE / "protocols" / "protocol.cc"
APPLICATION_HEADER = FIRMWARE / "application.h"
APPLICATION_SOURCE = FIRMWARE / "application.cc"
LOCAL_KNOWLEDGE = ROOT / "knowledge_base" / "本地轻量伴学知识库.md"
SOURCE_TEMPLATE = (
    ROOT / "xiaozhi-server-sandbox" / "source-server.config.template.yaml"
)
START_SOURCE = ROOT / "xiaozhi-server-sandbox" / "START_SOURCE.ps1"
PING_HANDLER = SERVER / "core" / "handle" / "textHandler" / "pingMessageHandler.py"
FUN_LOCAL = SERVER / "core" / "providers" / "asr" / "fun_local.py"


def load_study_stage_module():
    spec = importlib.util.spec_from_file_location(
        "local_study_stage",
        STUDY_STAGE_MODULE,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("我是小学生", "primary"),
        ("五年级", "primary"),
        ("我上初二", "middle"),
        ("八年级学生", "middle"),
        ("高三", "high"),
        ("高中生", "high"),
    ],
)
def test_detect_study_stage(text: str, expected: str) -> None:
    module = load_study_stage_module()
    assert module.detect_study_stage(text) == expected


def test_rejects_ambiguous_stage_answer() -> None:
    module = load_study_stage_module()
    assert module.detect_study_stage("小学还是初中") is None


def test_study_stage_setup_message_is_registered() -> None:
    message_types = MESSAGE_TYPES.read_text(encoding="utf-8")
    registry = REGISTRY.read_text(encoding="utf-8")
    handler = SETUP_HANDLER.read_text(encoding="utf-8")

    assert 'STUDY_STAGE_SETUP = "study_stage_setup"' in message_types
    assert "StudyStageSetupTextMessageHandler()" in registry
    assert "conn.study_stage_selection_pending = True" in handler
    assert "请选择小学、初中或高中模式" in handler


def test_stage_confirmation_and_parent_sync_contract() -> None:
    module = load_study_stage_module()
    receive_audio = RECEIVE_AUDIO.read_text(encoding="utf-8")
    study_stage_source = STUDY_STAGE_MODULE.read_text(encoding="utf-8")

    assert module.build_stage_confirmation("primary") == "已进入小学模式。"
    assert module.build_stage_confirmation("middle") == "已进入初中模式。"
    assert module.build_stage_confirmation("high") == "已进入高中模式。"
    assert "study_stage_selection_pending" in receive_audio
    assert "handle_pending_stage_selection" in receive_audio
    assert "http://127.0.0.1:8000/study-stage" in study_stage_source


def test_firmware_starts_stage_selection_once_and_listens_after_prompt() -> None:
    protocol_header = PROTOCOL_HEADER.read_text(encoding="utf-8")
    protocol_source = PROTOCOL_SOURCE.read_text(encoding="utf-8")
    application_header = APPLICATION_HEADER.read_text(encoding="utf-8")
    application_source = APPLICATION_SOURCE.read_text(encoding="utf-8")

    assert "SendStudyStageSetup" in protocol_header
    assert '"type", "study_stage_setup"' in protocol_source
    assert "study_stage_setup_sent_" in application_header
    assert "study_stage_listen_timer_" in application_header
    assert "kListeningModeAutoStop" in application_source
    assert "SendStudyStageSetup" in application_source


def test_lightweight_knowledge_is_injected_into_local_prompt() -> None:
    knowledge = LOCAL_KNOWLEDGE.read_text(encoding="utf-8")
    template = SOURCE_TEMPLATE.read_text(encoding="utf-8")
    startup = START_SOURCE.read_text(encoding="utf-8")

    assert "三阶校验口令" in knowledge
    assert "星芽、知桥、远帆" in knowledge
    assert "__LOCAL_KNOWLEDGE__" in template
    assert 'Replace("__LOCAL_KNOWLEDGE__"' in startup


def test_registry_uses_the_ping_handler_class_defined_by_the_server() -> None:
    registry = REGISTRY.read_text(encoding="utf-8")
    ping_handler = PING_HANDLER.read_text(encoding="utf-8")

    assert "class PingMessageHandler(" in ping_handler
    assert "from core.handle.textHandler.pingMessageHandler import PingMessageHandler" in registry
    assert "PingMessageHandler()" in registry


def test_local_asr_accepts_plain_text_results() -> None:
    source = FUN_LOCAL.read_text(encoding="utf-8")
    assert 'text.get("content", "") if isinstance(text, dict) else text' in source


def test_stage_speech_imports_tts_message_sender() -> None:
    source = RECEIVE_AUDIO.read_text(encoding="utf-8")
    assert (
        "from core.handle.sendAudioHandle import "
        "send_stt_message, send_tts_message, SentenceType"
    ) in source


def test_source_startup_reads_template_as_utf8() -> None:
    source = START_SOURCE.read_text(encoding="utf-8")
    assert "Get-Content -Raw -Encoding UTF8 -LiteralPath $template" in source


def test_funasr_uses_standard_wav_input() -> None:
    source = FUN_LOCAL.read_text(encoding="utf-8")
    assert "def requires_file(self) -> bool:" in source
    assert "def prefers_temp_file(self) -> bool:" in source
    assert "input=artifacts.temp_path" in source


def test_asr_json_is_reduced_to_content_before_chat() -> None:
    source = RECEIVE_AUDIO.read_text(encoding="utf-8")
    json_branch = source.split(
        'actual_text = str(data.get("content") or "").strip()',
        1,
    )[1].split("except (json.JSONDecodeError, KeyError):", 1)[0]
    assert "actual_text = text" not in json_branch
