import logging
import os
import tempfile
from uuid import uuid4

from fastapi import APIRouter, HTTPException

from app.exceptions import S3FileNotFoundError, S3AccessDeniedError
from app.models.schemas import ProcessRequest, ProcessResponse
from app.services.ai_service import OpenAITranscriptionService
from app.services.ffmpeg_service import FFmpegService
from app.services.s3_service import S3Service

router = APIRouter()
logger = logging.getLogger(__name__)

_ffmpeg_service = FFmpegService()
_ai_service = OpenAITranscriptionService()
_s3_service = S3Service(region="us-east-1")

PRESIGNED_URL_EXPIRES = 3600 #1 hour

@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/process", response_model=ProcessResponse)
async def process_video(request: ProcessRequest) -> ProcessResponse:
    logger.info("Received process request for: %s", request.s3_uri)

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # 1. Download video from s3
            video_filename = request.s3_uri.split("/")[-1]
            local_video = os.path.join(tmp_dir, video_filename)
            await _s3_service.download(request.s3_uri, local_video)

            #2. Extract audio with FFmpeg
            wav_path =await _ffmpeg_service.extract_audio(local_video, tmp_dir)

            #3.Transcribe with AI
            transcript = await _ai_service.transcribe(wav_path)

            # 4. Save transcript Locally then upload to s3
            transcript_key = f"transcripts/{uuid4()}.txt"
            local_transcript = os.path.join(tmp_dir, "transcript.txt")
            with open(local_transcript, "w", encoding="utf-8") as f:
                f.write(transcript)
            await _s3_service.upload(local_transcript, request.output_bucket, transcript_key)

            # 5. Generate presigned URL
            presigned_url = _s3_service.generate_presigned_url (
                request.output_bucket, transcript_key, PRESIGNED_URL_EXPIRES
            )
    except S3FileNotFoundError as e:
        logger.warning("S3 file not found: %s", repr(e))
        raise HTTPException(status_code=404, detail=str(e))
    except S3AccessDeniedError as e:
        logger.warning("S3 access denied: %s", repr(e))
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error("Processing failed: type=%s | %s", type(e).__name__, repr(e))
        raise HTTPException(status_code=500, detail=repr(e))
    

    return ProcessResponse(
        status="success",
        presigned_url=presigned_url,
        transcript=transcript,
        expires_in=PRESIGNED_URL_EXPIRES,
    )