import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_process_success(client):
    mock_wav = "/tmp/test_audio.wav"
    mock_transcript = "Hello world"

    with patch("app.api.routes._ffmpeg_service.extract_audio", new=AsyncMock(return_value=mock_wav)), \
         patch("app.api.routes._ai_service.transcribe", new=AsyncMock(return_value=mock_transcript)), \
         patch("app.models.schemas.os.path.isfile", return_value=True):

        response = await client.post("/api/v1/process", json={"file_path": "/tmp/test.mp4"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["wav_output_path"] == mock_wav
    assert data["transcript"] == mock_transcript


@pytest.mark.asyncio
async def test_process_file_not_found(client):
    response = await client.post("/api/v1/process", json={"file_path": "/nonexistent/file.mp4"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_process_unsupported_type(client):
    with patch("app.models.schemas.os.path.isfile", return_value=True):
        response = await client.post("/api/v1/process", json={"file_path": "/tmp/file.txt"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_process_ffmpeg_failure(client):
    with patch("app.api.routes._ffmpeg_service.extract_audio", new=AsyncMock(side_effect=RuntimeError("FFmpeg failed"))), \
         patch("app.models.schemas.os.path.isfile", return_value=True):

        response = await client.post("/api/v1/process", json={"file_path": "/tmp/test.mp4"})

    assert response.status_code == 500
    assert "FFmpeg failed" in response.json()["detail"]