import asyncio
import logging
import os
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class MockTranscriptionService:
    async def transcribe(self, wav_path: str) -> str:
        logger.info("AI model processing: %s", wav_path)
        await asyncio.sleep(0.5)
        file_name = os.path.basename(wav_path)
        transcript = f"[Mock Transcript] Processed audio file '{file_name}' successfully."
        logger.info("Transcription complete for: %s", wav_path)
        return transcript

class OpenAITranscriptionService:
    def __init__(self):
        self.client = AsyncOpenAI()

    async def transcribe(self, wav_path: str) -> str:
        logger.info("OpenAI Whisper processing: %s", wav_path)
        with open(wav_path, "rb") as audio_file:
            result = await self.client.audio.transcriptions.create(
                model = "whisper-1",
                file=audio_file,
            )
        logger.info("Transcription complete for: %s", wav_path)
        return result.text