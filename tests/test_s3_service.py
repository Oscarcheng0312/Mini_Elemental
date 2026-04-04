import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError

from app.services.s3_service import S3Service
from app.exceptions import S3FileNotFoundError, S3AccessDeniedError


def _make_client_error(code: str = "NoSuchKey", operation: str = "GetObject") -> ClientError:
    """Helper: build a botocore ClientError for testing."""
    return ClientError(
        {"Error": {"Code": code, "Message": "simulated error"}},
        operation,
    )


@pytest.fixture
def service():
    """S3Service with a fully mocked boto3 client — no real AWS calls."""
    with patch("app.services.s3_service.boto3.client") as mock_boto3_client:
        mock_s3 = MagicMock()
        mock_boto3_client.return_value = mock_s3
        svc = S3Service(region="us-east-1")
        yield svc


# ---------------------------------------------------------------------------
# _parse_s3_uri
# ---------------------------------------------------------------------------

class TestParseS3Uri:
    def test_simple_key(self, service):
        bucket, key = service._parse_s3_uri("s3://my-bucket/video.mp4")
        assert bucket == "my-bucket"
        assert key == "video.mp4"

    def test_nested_key(self, service):
        bucket, key = service._parse_s3_uri("s3://my-bucket/a/b/c/file.mp4")
        assert bucket == "my-bucket"
        assert key == "a/b/c/file.mp4"

    def test_key_with_prefix(self, service):
        bucket, key = service._parse_s3_uri("s3://mini-aws-elemental-bucket/videos/test.mp4")
        assert bucket == "mini-aws-elemental-bucket"
        assert key == "videos/test.mp4"


# ---------------------------------------------------------------------------
# download
# ---------------------------------------------------------------------------

class TestDownload:
    @pytest.mark.asyncio
    async def test_download_success(self, service):
        service.client.download_file.return_value = None

        await service.download("s3://my-bucket/video.mp4", "/tmp/video.mp4")

        service.client.download_file.assert_called_once_with(
            "my-bucket", "video.mp4", "/tmp/video.mp4"
        )

    @pytest.mark.asyncio
    async def test_download_calls_correct_bucket_and_key(self, service):
        """Verify URI parsing feeds the right args to boto3."""
        service.client.download_file.return_value = None

        await service.download(
            "s3://mini-aws-elemental-bucket/videos/lecture.mp4",
            "/tmp/lecture.mp4",
        )

        service.client.download_file.assert_called_once_with(
            "mini-aws-elemental-bucket", "videos/lecture.mp4", "/tmp/lecture.mp4"
        )

    @pytest.mark.asyncio
    async def test_download_raises_file_not_found_on_no_such_key(self, service):
        service.client.download_file.side_effect = _make_client_error("NoSuchKey")

        with pytest.raises(S3FileNotFoundError, match="File not found"):
            await service.download("s3://my-bucket/missing.mp4", "/tmp/missing.mp4")

    @pytest.mark.asyncio
    async def test_download_raises_access_denied(self, service):
        service.client.download_file.side_effect = _make_client_error(
            "AccessDenied", "GetObject"
        )

        with pytest.raises(S3AccessDeniedError, match="Access denied"):
            await service.download("s3://my-bucket/secret.mp4", "/tmp/secret.mp4")

    @pytest.mark.asyncio
    async def test_download_raises_runtime_error_on_other_client_error(self, service):
        service.client.download_file.side_effect = _make_client_error("InternalError")

        with pytest.raises(RuntimeError, match="S3 download failed"):
            await service.download("s3://my-bucket/video.mp4", "/tmp/video.mp4")


# ---------------------------------------------------------------------------
# upload
# ---------------------------------------------------------------------------

class TestUpload:
    @pytest.mark.asyncio
    async def test_upload_success(self, service):
        service.client.upload_file.return_value = None

        await service.upload("/tmp/transcript.txt", "my-bucket", "transcripts/abc.txt")

        service.client.upload_file.assert_called_once_with(
            "/tmp/transcript.txt", "my-bucket", "transcripts/abc.txt"
        )

    @pytest.mark.asyncio
    async def test_upload_raises_runtime_error_on_client_error(self, service):
        service.client.upload_file.side_effect = _make_client_error(
            "NoSuchBucket", "PutObject"
        )

        with pytest.raises(RuntimeError, match="S3 upload failed"):
            await service.upload("/tmp/file.txt", "nonexistent-bucket", "key.txt")


# ---------------------------------------------------------------------------
# generate_presigned_url
# ---------------------------------------------------------------------------

class TestGeneratePresignedUrl:
    def test_returns_url_string(self, service):
        expected = "https://my-bucket.s3.amazonaws.com/transcripts/abc.txt?X-Amz-Signature=xxx"
        service.client.generate_presigned_url.return_value = expected

        result = service.generate_presigned_url("my-bucket", "transcripts/abc.txt", 3600)

        assert result == expected

    def test_passes_correct_params_to_boto3(self, service):
        service.client.generate_presigned_url.return_value = "https://example.com/url"

        service.generate_presigned_url("my-bucket", "transcripts/abc.txt", 7200)

        service.client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={"Bucket": "my-bucket", "Key": "transcripts/abc.txt"},
            ExpiresIn=7200,
        )

    def test_default_expiry_is_3600(self, service):
        service.client.generate_presigned_url.return_value = "https://example.com/url"

        service.generate_presigned_url("my-bucket", "transcripts/abc.txt")

        _, kwargs = service.client.generate_presigned_url.call_args
        assert kwargs["ExpiresIn"] == 3600

    def test_raises_runtime_error_on_client_error(self, service):
        service.client.generate_presigned_url.side_effect = _make_client_error(
            "NoSuchKey", "GeneratePresignedUrl"
        )

        with pytest.raises(RuntimeError, match="Failed to gererate presigned URL"):
            service.generate_presigned_url("my-bucket", "missing.txt")
