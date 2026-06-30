from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MQTT_PROTOCOL_SOURCE = (
    ROOT / "xiaozhi-esp32" / "main" / "protocols" / "mqtt_protocol.cc"
)


def test_mqtt_audio_channel_registers_udp_endpoint_after_connect() -> None:
    source = MQTT_PROTOCOL_SOURCE.read_text(encoding="utf-8")
    connect = source.index("udp_->Connect(udp_server_, udp_port_);")
    handshake = source.index("udp_->Send(aes_nonce_);")
    callback = source.index("if (on_audio_channel_opened_ != nullptr)")

    assert connect < handshake < callback
