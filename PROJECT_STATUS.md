# mini_elemental — Project Status & Architecture Notes

> This document is intended as a handoff reference for continuing this project in a new chat session.
> It captures architecture decisions, implementation details, async design rationale, known issues, and next steps.

---

## Project Goal

Build a production-grade Python microservice that mirrors AWS Elemental's video preprocessing patterns:

- Accepts an S3 URI pointing to a video file
- Extracts audio via FFmpeg
- Transcribes audio via OpenAI Whisper
- Uploads the transcript back to S3
- Returns a time-limited presigned download URL to the client

---

## Current Status: FULLY WORKING ✓

All five pipeline steps have been verified end-to-end:

| Step | Implementation | Status |
|------|---------------|--------|
| S3 download | boto3 via `asyncio.to_thread` | ✓ |
| Audio extraction | FFmpeg via `asyncio.to_thread` + `subprocess.run` | ✓ |
| AI transcription | OpenAI Whisper API (`AsyncOpenAI`) | ✓ |
| S3 upload | boto3 via `asyncio.to_thread` | ✓ |
| Presigned URL | boto3 `generate_presigned_url` | ✓ |

Tested with: `s3://mini-aws-elemental-bucket/leetcode_twoSum.mp4` (us-east-1)

---

## Project Structure

```
mini_elemental/
├── app/
│   ├── core/
│   │   └── logging_config.py       # Global logging setup — called once in main.py
│   ├── models/
│   │   └── schemas.py              # Pydantic v2 request/response models
│   ├── services/
│   │   ├── s3_service.py           # boto3 S3 download / upload / presigned URL
│   │   ├── ffmpeg_service.py       # FFmpeg audio extraction
│   │   └── ai_service.py           # MockTranscriptionService + OpenAITranscriptionService
│   ├── api/
│   │   └── routes.py               # POST /api/v1/process — orchestrates 5-step pipeline
│   └── main.py                     # FastAPI app, lifespan, global exception handler
├── tests/
│   ├── conftest.py                 # AsyncClient fixture + dummy OPENAI_API_KEY
│   ├── test_routes.py
│   ├── test_ffmpeg_service.py
│   └── test_ai_service.py
├── docs/
│   └── architecture.png
├── pytest.ini                      # asyncio_mode = auto
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Layer Architecture & Responsibilities

```
Entry Layer     main.py
                  ├── WindowsProactorEventLoopPolicy (Windows fix for asyncio subprocess)
                  ├── setup_logging() — called at module level, before anything else
                  ├── lifespan context manager — startup/shutdown logs
                  ├── @app.exception_handler(RequestValidationError)
                  │     uses jsonable_encoder(exc.errors()) — required for Pydantic v2
                  │     because exc.errors() ctx field contains actual ValueError objects
                  │     which are not JSON-serializable by default
                  └── app.include_router(router, prefix="/api/v1")

API Layer       routes.py
                  ├── Instantiates services at module load (singleton pattern)
                  ├── Receives ProcessRequest (validated by Pydantic before reaching here)
                  ├── Runs 5-step pipeline inside tempfile.TemporaryDirectory()
                  ├── except Exception (not RuntimeError) — catches boto3 ClientError etc.
                  └── Returns ProcessResponse

Data Layer      schemas.py
                  ├── ProcessRequest
                  │     s3_uri: str  — validated by regex ^s3://bucket/key$
                  │     output_bucket: str = "mini-aws-elemental-bucket"
                  └── ProcessResponse
                        presigned_url, transcript, expires_in, status

Service Layer   s3_service.py
                  ├── boto3.client("s3") reads AWS credentials from env vars automatically
                  ├── download() / upload() — wrapped in asyncio.to_thread (boto3 is sync)
                  └── generate_presigned_url() — sync, fast, no thread needed

                ffmpeg_service.py
                  ├── Uses subprocess.run (sync) wrapped in asyncio.to_thread
                  ├── Reason: asyncio.create_subprocess_exec NOT used
                  │     uvicorn on Windows overrides the event loop policy at startup,
                  │     causing NotImplementedError. asyncio.to_thread + subprocess.run
                  │     is the reliable cross-platform solution.
                  └── Checks returncode != 0 and decodes stderr for error messages

                ai_service.py
                  ├── MockTranscriptionService — asyncio.sleep(0.5) + hardcoded string
                  │     for development/testing without API key
                  └── OpenAITranscriptionService — AsyncOpenAI().audio.transcriptions.create
                        model="whisper-1", reads OPENAI_API_KEY from env

Infrastructure  core/logging_config.py
                  └── logging.basicConfig with %(asctime)s | %(levelname)-8s | %(name)s | %(message)s
                        all modules use logging.getLogger(__name__)
                        never use print()
```

---

## Async Design — Key Decisions

### Why asyncio.to_thread instead of asyncio.create_subprocess_exec

**Problem encountered:** `NotImplementedError` on Windows when calling
`asyncio.create_subprocess_exec` through uvicorn.

**Root cause:** uvicorn resets the asyncio event loop policy at startup.
On Windows, `asyncio.create_subprocess_exec` requires `WindowsProactorEventLoop`,
but uvicorn was installing `WindowsSelectorEventLoop` after our `main.py` policy setting.

**Solution:** Use `asyncio.to_thread(subprocess.run, ...)` — runs the synchronous
`subprocess.run` in a thread pool. The event loop is never involved in the actual
subprocess execution, making it fully cross-platform.

### How async concurrency works in this service

Async does NOT mean the 5 steps within one request run in parallel.
The steps are sequential because each step depends on the previous output:

```
download → extract → transcribe → upload → presign
```

Async means that **across multiple concurrent requests**, while Request A is
waiting for its boto3 download (IO-bound), the event loop can start processing
Request B. Each `await` is a yield point where the event loop can switch.

```
Timeline with 2 concurrent requests:
[A: S3 download - waiting for network...]
  → event loop switches to B
  [B: S3 download - waiting for network...]
    → OS signals A's download done
[A: FFmpeg - thread running...]
  → event loop is free, can accept Request C
```

### Why tempfile.TemporaryDirectory() is critical

```python
with tempfile.TemporaryDirectory() as tmp_dir:
    # all 5 steps
# ← auto-deleted here, even if an exception was raised
```

The `with` block's `__exit__` always runs, guaranteeing cleanup of:
- downloaded video (.mp4)
- extracted audio (.wav)
- local transcript (.txt)

In container/cloud environments, disk space is limited.
Failing to clean up intermediate files causes disk exhaustion.

---

## Data Flow (End-to-End)

```
Client
  │  POST /api/v1/process
  │  {"s3_uri": "s3://mini-aws-elemental-bucket/video.mp4"}
  ▼
Pydantic validates S3 URI format (regex)
  │  invalid → 422 Unprocessable Entity
  ▼
tempfile.TemporaryDirectory created
  ▼
S3Service.download(s3_uri, tmp/video.mp4)
  └── boto3 → S3 private bucket → pulls file into tmp dir
  ▼
FFmpegService.extract_audio(tmp/video.mp4, tmp/)
  └── ffmpeg -y -i video.mp4 -vn -acodec pcm_s16le -ar 44100 -ac 2 video_audio.wav
  ▼
OpenAITranscriptionService.transcribe(tmp/video_audio.wav)
  └── POST https://api.openai.com/v1/audio/transcriptions (whisper-1)
  └── returns plain text transcript
  ▼
Write transcript to tmp/transcript.txt
S3Service.upload(tmp/transcript.txt, bucket, transcripts/uuid.txt)
  ▼
S3Service.generate_presigned_url(bucket, transcripts/uuid.txt, expires=3600)
  └── signed URL valid for 1 hour, no public bucket required
  ▼
tempfile.TemporaryDirectory deleted (all temp files gone)
  ▼
Client receives:
{
  "status": "success",
  "presigned_url": "https://bucket.s3.amazonaws.com/transcripts/uuid.txt?...",
  "transcript": "...",
  "expires_in": 3600
}
```

---

## Key Technical Decisions & Rationale

| Decision | Rationale |
|----------|-----------|
| FastAPI over Flask | Native async support, Pydantic integration, auto Swagger UI |
| Pydantic v2 `@field_validator` | Validates data at boundary before reaching service layer |
| `jsonable_encoder(exc.errors())` in exception handler | Pydantic v2 `exc.errors()` contains `ValueError` objects in `ctx` field — not JSON-serializable without encoding |
| Class-based services over functions | Enables dependency injection, `__init__` config, and test mocking |
| `MockTranscriptionService` kept alongside `OpenAITranscriptionService` | Interface-oriented programming — same method signature, swap in routes.py with zero other changes |
| `asyncio.to_thread` for boto3 and FFmpeg | Both libraries are synchronous; wrapping in thread pool keeps event loop free without requiring ProactorEventLoop |
| `except Exception` in routes (not `RuntimeError`) | boto3 raises `ClientError` (subclass of `Exception`, not `RuntimeError`) |
| S3 bucket stays private | Use IAM credentials + presigned URLs instead of public access — AWS security standard |
| `uuid4()` for transcript key | Prevents filename collisions across concurrent requests |

---

## AWS Configuration

- **Bucket:** `mini-aws-elemental-bucket`
- **Region:** `us-east-1`
- **IAM policy:** `AmazonS3FullAccess`
- **Input prefix:** `videos/` (or bucket root)
- **Output prefix:** `transcripts/`

Required environment variables (set before starting uvicorn):
```powershell
$env:OPENAI_API_KEY       = "sk-..."
$env:AWS_ACCESS_KEY_ID    = "AKIA..."
$env:AWS_SECRET_ACCESS_KEY = "..."
$env:AWS_DEFAULT_REGION   = "us-east-1"
```

---

## Known Issues & Minor TODOs

| Issue | Location | Severity |
|-------|----------|----------|
| `generate_presigned_url` error message has typo "gererate" | `s3_service.py` line 54 | Minor (string only) |
| `_parse_s3_uri` comment has comma instead of dot | `s3_service.py` line 15 | Cosmetic |
| `except RuntimeError` in routes was changed to `except Exception` but test `test_process_ffmpeg_failure` still asserts status 500 which still passes — tests not updated to reflect S3 flow | `tests/test_routes.py` | Low |
| Tests for `s3_service.py` not yet written | `tests/` | Medium |

---

## Tests

Run:
```bash
pytest tests/ -v
```

`conftest.py` sets `os.environ.setdefault("OPENAI_API_KEY", "test-dummy-key")` to
prevent `AsyncOpenAI()` instantiation failure when env var is not set during testing.

All service calls are mocked with `unittest.mock.AsyncMock` + `patch` — no real
FFmpeg, S3, or OpenAI calls during unit tests.

---

## Potential Next Steps

1. **Add `tests/test_s3_service.py`** — mock boto3 `download_file`, `upload_file`, `generate_presigned_url`
2. **Add job status tracking** — return a job ID immediately, poll for completion (async job pattern)
3. **Support URL input** — accept `http://` URLs in addition to `s3://` URIs, download via `httpx`
4. **Dockerize** — `Dockerfile` + `docker-compose.yml` for container deployment
5. **Deploy to AWS** — ECS Fargate or Lambda (note: Lambda has 512MB /tmp limit, relevant for large videos)
6. **Add `language` and `prompt` params to Whisper call** — improves transcription accuracy for technical content
