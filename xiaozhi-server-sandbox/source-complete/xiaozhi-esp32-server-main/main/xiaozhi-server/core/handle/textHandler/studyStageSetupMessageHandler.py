import asyncio
import uuid
from typing import Any, Dict

from core.handle.intentHandler import speak_txt
from core.handle.sendAudioHandle import send_tts_message
from core.handle.textMessageHandler import TextMessageHandler
from core.handle.textMessageType import TextMessageType


TAG = __name__
STAGE_PROMPT = "你好，请选择小学、初中或高中模式。"


class StudyStageSetupTextMessageHandler(TextMessageHandler):
    @property
    def message_type(self) -> TextMessageType:
        return TextMessageType.STUDY_STAGE_SETUP

    async def handle(self, conn, msg_json: Dict[str, Any]) -> None:
        if msg_json.get("state") != "ready":
            return

        for _ in range(50):
            if conn.tts is not None:
                break
            await asyncio.sleep(0.1)
        if conn.tts is None:
            conn.logger.bind(tag=TAG).error("学段选择等待 TTS 初始化超时")
            await send_tts_message(conn, "stop")
            return

        conn.study_stage_selection_pending = True
        conn.study_stage_selection_attempts = 0
        conn.sentence_id = uuid.uuid4().hex
        conn.client_is_speaking = True
        await send_tts_message(conn, "start")
        speak_txt(conn, STAGE_PROMPT)
