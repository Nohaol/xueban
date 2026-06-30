from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER = (
    ROOT
    / "xiaozhi-server-sandbox"
    / "source-complete"
    / "xiaozhi-esp32-server-main"
    / "main"
    / "xiaozhi-server"
)


def test_local_windows_tts_is_available_and_selected() -> None:
    provider = SERVER / "core" / "providers" / "tts" / "windows_sapi.py"
    config = (SERVER / "config.yaml").read_text(encoding="utf-8")
    template = (
        ROOT / "xiaozhi-server-sandbox" / "source-server.config.template.yaml"
    ).read_text(encoding="utf-8")
    source = provider.read_text(encoding="utf-8")

    assert "TTS: WindowsSapiTTS" in config
    assert "WindowsSapiTTS:" in config
    assert "type: windows_sapi" in config
    assert "TTS: WindowsSapiTTS" in template
    assert "WindowsSapiTTS:" in template
    assert "type: windows_sapi" in template
    assert "SAPI.SpVoice" in source
    assert "SAPI.SpFileStream" in source
