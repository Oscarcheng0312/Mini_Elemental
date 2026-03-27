from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.services.ffmpeg_service import FFmpegService


@pytest.mark.asyncio
async def test_extract_audio_success(tmp_path):
    service = FFmpegService()
    fake_video_path = tmp_path / "test.mp4"
    fake_video_path.touch()

    mock_process = MagicMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b"",b""))

    with patch("asyncio.create_subprocess_exec", new=AsyncMock(return_value=mock_process)):
        result = await service.extract_audio(str(fake_video_path), str(tmp_path))


    assert result.endswith("audio.wav")


@pytest.mark.asyncio
async def test_extra_audio_not_found(tmp_path):
    service = FFmpegService()
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match = "FFmpeg executable not found"):
            await service.extract_audio(str(fake_video))



@pytest.mark.asyncio
async def test_extra_audio_error(tmp_path):
    service = FFmpegService()
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    mock_process = MagicMock()
    mock_process.returncode = 1
    mock_process.communicate = AsyncMock(return_value=(b"", b"Invalid data"))

    with patch("asyncio.create_subprocess_exec", new = AsyncMock(return_value= mock_process)):
        with pytest.raises(RuntimeError, match = "FFmpeg processing failed"):
            await service.extract_audio(str(fake_video))
            