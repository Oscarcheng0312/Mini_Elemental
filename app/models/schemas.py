from pydantic import BaseModel, field_validator
import os


class ProcessRequest(BaseModel):
    file_path: str

    @field_validator("file_path")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        if not os.path.isfile(v):
            raise ValueError(f"File not found: {v}")
        if not v.lower().endswith((".mp4", ".mov", ".avi", ".mkv")):
            raise ValueError(f"Unsupported file type. Expected a video file.")

        return v
    

class ProcessResponse(BaseModel):
    status: str
    wav_output_path: str
    transcript: str
            
