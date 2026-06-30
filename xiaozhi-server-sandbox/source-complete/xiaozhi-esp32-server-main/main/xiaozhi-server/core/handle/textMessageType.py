from enum import Enum


class TextMessageType(Enum):
    """消息类型枚举"""
    HELLO = "hello"
    ABORT = "abort"
    LISTEN = "listen"
    IOT = "iot"
    MCP = "mcp"
    SERVER = "server"
    PING = "ping"
    STUDY_ALERT = "study_alert"
    STUDY_STAGE_SETUP = "study_stage_setup"
