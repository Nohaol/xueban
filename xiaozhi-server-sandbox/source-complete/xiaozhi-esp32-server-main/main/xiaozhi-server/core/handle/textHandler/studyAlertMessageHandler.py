import asyncio
import uuid
from typing import Any, Dict

from core.handle.intentHandler import speak_txt
from core.handle.sendAudioHandle import send_tts_message
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType

TAG = __name__


class StudyAlertTextMessageHandler(TextMessageHandler):
    """Speak a reminder after modified firmware reports its audio channel ready."""

    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.STUDY_ALERT

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        if msg_json.get("state") != "ready":
            return

        text = str(msg_json.get("text") or "").strip()
        if not text:
            conn.logger.bind(tag=TAG).warning("study_alert.ready is missing text")
            return

        request_id = str(msg_json.get("request_id") or "")
        conn.logger.bind(tag=TAG).info(
            f"开始主动学习提醒 request_id={request_id or '-'} text={text}"
        )

        for _ in range(50):
            if conn.tts is not None:
                break
            await asyncio.sleep(0.1)
        if conn.tts is None:
            conn.logger.bind(tag=TAG).error("主动学习提醒等待 TTS 初始化超时")
            await send_tts_message(conn, "stop")
            return

        await asyncio.sleep(0.2)
        conn.sentence_id = uuid.uuid4().hex
        conn.client_is_speaking = True
        await send_tts_message(conn, "start")
        speak_txt(conn, text)
