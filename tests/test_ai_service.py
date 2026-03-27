import pytest

from app.services.ai_service import MockTranscriptionService


@pytest.mark.asyncio
async def test_transcribe_returns_string():
    ai = MockTranscriptionService()
    result = await ai.transcribe("/tmp/test_audio.wav")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_transcribe_contains_filename():
    ai = MockTranscriptionService()
    result = await ai.transcribe("/tmp/my_video.mp4")
    assert "my_video.mp4" in result