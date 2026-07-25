import boto3
from botocore.config import Config

from aeloria.config import Settings, get_settings


class R2:
    def __init__(self, settings: Settings | None = None):
        s = settings or get_settings()
        self._s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{s.r2_account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=s.r2_access_key_id,
            aws_secret_access_key=s.r2_secret_access_key,
            config=Config(region_name="auto", signature_version="s3v4"),
        )
        self._bucket = s.r2_bucket
        self._public_base = s.r2_public_base_url.rstrip("/")

    def upload(self, data: bytes, key: str, content_type: str) -> str:
        self._s3.put_object(
            Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
        )
        return f"{self._public_base}/{key}"
