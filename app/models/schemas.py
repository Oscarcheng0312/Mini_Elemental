from pydantic import BaseModel, field_validator
import re


class ProcessRequest(BaseModel):
    s3_uri: str
    output_bucket: str = "mini-aws-elemental-bucket"

    @field_validator("s3_uri")
    @classmethod
    def validate_s3_uri(cls, v: str) -> str:
        pattern = r"^s3://[a-z0-9][a-z0-9\-\.]{1,61}[a-z0-9]/(.+)$"
        if not re.match(pattern, v):
            raise ValueError(
                f"Invalid S3 URI: {v}. Expected format: s3://bucket-name/key"
            )

        return v
    

class ProcessResponse(BaseModel):
    status: str
    presigned_url: str
    transcript: str
    expires_in: int
            
