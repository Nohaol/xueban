import asyncio
import os
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Tuple

from config.logger import setup_logging
from core.providers.asr.base import ASRProviderBase
from core.providers.asr.dto.dto import InterfaceType


TAG = __name__
logger = setup_logging()


class ASRProvider(ASRProviderBase):
    def __init__(self, config: dict, delete_audio_file: bool = True):
        super().__init__()
        self.interface_type = InterfaceType.LOCAL
        self.output_dir = config.get("output_dir", "tmp/")
        self.delete_audio_file = delete_audio_file
        self.recognizer_script = Path(__file__).with_name(
            "windows_speech_recognize.ps1"
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def requires_file(self) -> bool:
        return True

    def prefers_temp_file(self) -> bool:
        return True

    def _recognize_file(self, audio_path: str) -> str:
        command = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(self.recognizer_script),
            "-AudioPath",
            audio_path,
        ]
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            check=False,
        )
        if completed.returncode != 0:
            error = completed.stderr.decode("utf-8", errors="replace").strip()
            logger.bind(tag=TAG).error(
                f"Windows 中文语音识别失败: {error or completed.returncode}"
            )
            return ""
        return completed.stdout.decode("utf-8", errors="replace").strip()

    async def speech_to_text(
        self,
        opus_data: List[bytes],
        session_id: str,
        audio_format="opus",
        artifacts=None,
    ) -> Tuple[Optional[str], Optional[str]]:
        if artifacts is None or not artifacts.temp_path:
            return "", None

        started = time.monotonic()
        try:
            text = await asyncio.to_thread(
                self._recognize_file,
                artifacts.temp_path,
            )
        except (OSError, subprocess.SubprocessError) as error:
            logger.bind(tag=TAG).error(
                f"Windows 中文语音识别失败: {type(error).__name__}"
            )
            return "", None

        logger.bind(tag=TAG).info(
            f"Windows 中文语音识别耗时: {time.monotonic() - started:.3f}s"
        )
        return text, artifacts.file_path
