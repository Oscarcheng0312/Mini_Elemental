import logging


from fastapi import APIRouter, HTTPException

from app.models.schemas import ProcessRequest, ProcessResponse
from app.services.ai_service import OpenAITranscriptionService
from app.services.ffmpeg_service import FFmpegService

router = APIRouter()
logger = logging.getLogger(__name__)

_ffmpeg_service = FFmpegService()
_ai_service = OpenAITranscriptionService()

@router.post("/process", response_model=ProcessResponse)
async def process_video(request: ProcessRequest) -> ProcessResponse:
    logger.info("Received process request for: %s", request.file_path)

    try:
        wav_path = await _ffmpeg_service.extract_audio(request.file_path)
        transcript = await _ai_service.transcribe(wav_path)
    except RuntimeError as e:
        logger.error("Processing failed: type=%s | %s", type(e).__name__, repr(e))
        raise HTTPException(status_code=500, detail=repr(e))

    return ProcessResponse(
        status="success",
        wav_output_path=wav_path,
        transcript=transcript
    )