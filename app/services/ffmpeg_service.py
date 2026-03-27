import asyncio
import subprocess
import logging
import os

logger = logging.getLogger(__name__)


class FFmpegService:
    async def extract_audio(self, video_path: str, output_dir: str | None = None) -> str:
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(video_path))

        base_name = os.path.splitext(os.path.basename(video_path))[0]
        wav_path = os.path.join(output_dir, f"{base_name}_audio.wav")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            wav_path,
        ]

        logger.info("Starting audio extraction: %s -> %s", video_path, wav_path)

        def run_ffmpeg():
            try:
                return subprocess.run(cmd, capture_output=True)
            except FileNotFoundError:
                raise RuntimeError(
                    "FFmpeg executable not found. Please install FFmpeg and add it to PATH."
                )

        result = await asyncio.to_thread(run_ffmpeg)

        if result.returncode != 0:
            error_msg = result.stderr.decode(errors="replace").strip()
            logger.error("FFmpeg failed (exit code %d): %s", result.returncode, error_msg)
            raise RuntimeError(f"FFmpeg processing failed: {error_msg}")

        logger.info("Audio extraction complete successfully: %s", wav_path)
        return wav_path