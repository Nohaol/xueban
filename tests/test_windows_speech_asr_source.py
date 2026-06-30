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
PROVIDER = SERVER / "core" / "providers" / "asr" / "windows_speech.py"
RECOGNIZER = (
    SERVER / "core" / "providers" / "asr" / "windows_speech_recognize.ps1"
)
TEMPLATE = ROOT / "xiaozhi-server-sandbox" / "source-server.config.template.yaml"


def test_windows_speech_asr_is_selected_and_uses_wav_files() -> None:
    provider = PROVIDER.read_text(encoding="utf-8")
    recognizer = RECOGNIZER.read_text(encoding="utf-8")
    template = TEMPLATE.read_text(encoding="utf-8")

    assert "ASR: WindowsSpeech" in template
    assert "WindowsSpeech:" in template
    assert "type: windows_speech" in template
    assert "def requires_file(self) -> bool:" in provider
    assert "def prefers_temp_file(self) -> bool:" in provider
    assert "artifacts.temp_path" in provider
    assert "SpeechRecognitionEngine" in recognizer
    assert "DictationGrammar" in recognizer
    assert "SetInputToWaveFile" in recognizer
