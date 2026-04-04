import pytest
from unittest.mock import AsyncMock, MagicMock, patch

VALID_S3_URI = "s3://mini-aws-elemental-bucket/video.mp4"
MOCK_WAV = "/tmp/video_audio.wav"
MOCK_TRANSCRIPT = "Hello world"
MOCK_PRESIGNED_URL = "https://mini-aws-elemental-bucket.s3.amazonaws.com/transcripts/uuid.txt?sig=xxx"


@pytest.mark.asyncio
async def test_process_success(client):
    with patch("app.api.routes._s3_service.download", new=AsyncMock()), \
         patch("app.api.routes._ffmpeg_service.extract_audio", new=AsyncMock(return_value=MOCK_WAV)), \
         patch("app.api.routes._ai_service.transcribe", new=AsyncMock(return_value=MOCK_TRANSCRIPT)), \
         patch("app.api.routes._s3_service.upload", new=AsyncMock()), \
         patch("app.api.routes._s3_service.generate_presigned_url", return_value=MOCK_PRESIGNED_URL):

        response = await client.post("/api/v1/process", json={"s3_uri": VALID_S3_URI})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["presigned_url"] == MOCK_PRESIGNED_URL
    assert data["transcript"] == MOCK_TRANSCRIPT
    assert data["expires_in"] == 3600


@pytest.mark.asyncio
async def test_process_invalid_s3_uri(client):
    response = await client.post("/api/v1/process", json={"s3_uri": "not-a-valid-uri"})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_process_missing_s3_uri(client):
    response = await client.post("/api/v1/process", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_process_s3_download_failure(client):
    with patch("app.api.routes._s3_service.download",
               new=AsyncMock(side_effect=RuntimeError("S3 download failed"))):

        response = await client.post("/api/v1/process", json={"s3_uri": VALID_S3_URI})

    assert response.status_code == 500
    assert "S3 download failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_process_ffmpeg_failure(client):
    with patch("app.api.routes._s3_service.download", new=AsyncMock()), \
         patch("app.api.routes._ffmpeg_service.extract_audio",
               new=AsyncMock(side_effect=RuntimeError("FFmpeg failed"))):

        response = await client.post("/api/v1/process", json={"s3_uri": VALID_S3_URI})

    assert response.status_code == 500
    assert "FFmpeg failed" in response.json()["detail"]