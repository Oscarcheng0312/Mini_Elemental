from unittest.mock import MagicMock, patch

import pytest

from app.services.ffmpeg_service import FFmpegService


@pytest.mark.asyncio
async def test_extract_audio_success(tmp_path):
    service = FFmpegService()
    fake_video_path = tmp_path / "test.mp4"
    fake_video_path.touch()

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stderr = b""

    with patch("app.services.ffmpeg_service.subprocess.run", return_value=mock_result):
        result = await service.extract_audio(str(fake_video_path), str(tmp_path))

    assert result.endswith("audio.wav")


@pytest.mark.asyncio
async def test_extra_audio_not_found(tmp_path):
    service = FFmpegService()
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    with patch("app.services.ffmpeg_service.subprocess.run", side_effect=FileNotFoundError):
        with pytest.raises(RuntimeError, match="FFmpeg executable not found"):
            await service.extract_audio(str(fake_video))


@pytest.mark.asyncio
async def test_extra_audio_error(tmp_path):
    service = FFmpegService()
    fake_video = tmp_path / "test.mp4"
    fake_video.touch()

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = b"Invalid data"

    with patch("app.services.ffmpeg_service.subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="FFmpeg processing failed"):
            await service.extract_audio(str(fake_video))
            