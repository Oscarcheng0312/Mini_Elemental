import asyncio
import logging

import boto3
from botocore.exceptions import ClientError

from app.exceptions import S3FileNotFoundError, S3AccessDeniedError

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self, region: str = "us-east-1"):
        self.region = region
        self.client = boto3.client("s3", region_name=region)

    def _parse_s3_uri(self, s3_uri: str) -> tuple[str, str]:
        # s3: //bucket-name/path/to/file.mp4 -> ("bucket-name", "path/to/file,mp4")
        without_prefix = s3_uri[5:]
        bucket, key = without_prefix.split("/", 1)
        return bucket, key
    
    async def download(self, s3_uri: str, local_path: str) -> None:
        bucket, key = self._parse_s3_uri(s3_uri)
        logger.info("Downloading s3://%s/%s to %s", bucket, key, local_path)

        def _download():
            try:
                self.client.download_file(bucket, key, local_path)
            except ClientError as e:
                code = e.response["Error"]["Code"]
                if code in ("NoSuchKey", "404"):
                    raise S3FileNotFoundError(f"File not found: s3://{bucket}/{key}")
                if code in ("AccessDenied", "403"):
                    raise S3AccessDeniedError(f"Access denied to s3://{bucket}/{key}")
                raise RuntimeError(f"S3 download failed: {e}")
        
        await asyncio.to_thread(_download)
        logger.info("Download complete: %s", local_path)

    async def upload(self, local_path: str, bucket: str, key: str) -> None:
        logger.info("Uploading %s to s3://%s/%s", local_path, bucket, key)
        def _upload():
            try:
                self.client.upload_file(local_path, bucket, key)
            except ClientError as e:
                raise RuntimeError(f"S3 upload failed: {e}")
        await asyncio.to_thread(_upload)
        logger.info("Upload complete: s3://%s/%s", bucket, key)

        
    def generate_presigned_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            logger.info("Presigned URL generated for s3://%s/%s", bucket, key)
            return url
        except ClientError as e:
            raise RuntimeError(f"Failed to gererate presigned URL: {e}")
