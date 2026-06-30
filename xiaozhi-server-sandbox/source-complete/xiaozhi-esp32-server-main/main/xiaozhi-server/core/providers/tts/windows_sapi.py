import os

import pythoncom
import win32com.client

from core.providers.tts.base import TTSProviderBase


class TTSProvider(TTSProviderBase):
    def __init__(self, config, delete_audio_file):
        super().__init__(config, delete_audio_file)
        self.audio_file_type = "wav"
        self.voice_name = config.get("voice", "Microsoft Huihui Desktop")
        self.rate = int(config.get("rate", 0))
        self.volume = int(config.get("volume", 100))

    async def text_to_speak(self, text, output_file):
        temporary_file = output_file or self.generate_filename(".wav")
        os.makedirs(os.path.dirname(temporary_file), exist_ok=True)

        pythoncom.CoInitialize()
        try:
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            stream = win32com.client.Dispatch("SAPI.SpFileStream")
            for candidate in voice.GetVoices():
                if candidate.GetDescription() == self.voice_name:
                    voice.Voice = candidate
                    break
            voice.Rate = max(-10, min(10, self.rate))
            voice.Volume = max(0, min(100, self.volume))
            stream.Open(os.path.abspath(temporary_file), 3, False)
            voice.AudioOutputStream = stream
            voice.Speak(text)
            stream.Close()
            voice.AudioOutputStream = None

            if output_file:
                return None
            with open(temporary_file, "rb") as audio:
                return audio.read()
        finally:
            if not output_file and os.path.exists(temporary_file):
                os.remove(temporary_file)
            pythoncom.CoUninitialize()
