from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SANDBOX = ROOT / "xiaozhi-server-sandbox"
FIRMWARE = ROOT / "xiaozhi-esp32"


def test_windows_autostart_launches_all_local_services() -> None:
    start_all = (SANDBOX / "START_ALL.ps1").read_text(encoding="utf-8")
    installer = (SANDBOX / "INSTALL_AUTOSTART.ps1").read_text(encoding="utf-8")

    assert "START_SOURCE.ps1" in start_all
    assert "START_MQTT_GATEWAY.ps1" in start_all
    assert "START_PARENT_ACTIVE.ps1" in start_all
    for port in (8000, 18000, 18003, 18007, 1883):
        assert str(port) in start_all
    assert 'SpecialFolders("Startup")' in installer
    assert "START_ALL.ps1" in installer


def test_cached_device_configuration_skips_blocking_ota_retries() -> None:
    application = (FIRMWARE / "main" / "application.cc").read_text(encoding="utf-8")
    mqtt_header = (
        FIRMWARE / "main" / "protocols" / "mqtt_protocol.h"
    ).read_text(encoding="utf-8")

    assert "OTA unavailable, continuing with cached MQTT configuration" in application
    assert 'Settings mqtt_settings("mqtt", false);' in application
    assert "MQTT_RECONNECT_INTERVAL_MS 5000" in mqtt_header
