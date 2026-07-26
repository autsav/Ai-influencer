"""POST /api/v1/uploads/presign — get a presigned S3 URL for direct client upload."""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from aeloria.config import get_settings, Settings
from aeloria.schemas.v1 import PresignedUploadResponse
from aeloria.storage.r2 import R2

router = APIRouter()
log = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


def _auth(creds: HTTPAuthorizationCredentials | None = Security(_bearer),
          settings: Settings = Depends(get_settings)) -> bool:
    import secrets
    if not settings.api_secret_key:
        return True
    if creds is None:
        raise HTTPException(401, "unauthorized")
    if not secrets.compare_digest(creds.credentials, settings.api_secret_key):
        raise HTTPException(401, "unauthorized")
    return True


class PresignRequest(BaseModel):
    """Request a presigned upload URL."""
    content_type: str = "image/png"
    folder: str = "uploads"


@router.post("/uploads/presign", response_model=PresignedUploadResponse)
async def presign_upload(req: PresignRequest, _authed: bool = Depends(_auth)):
    """Return a presigned URL for the client to upload directly to S3/R2.
    The client PUTs the file to the returned URL — no binary passes through FastAPI.
    """
    settings = get_settings()
    ext = req.content_type.split("/")[-1] if "/" in req.content_type else "bin"
    object_key = f"{req.folder}/{uuid.uuid4()}.{ext}"
    r2 = R2(settings)
    url = r2.presigned_put(object_key, expires_in=3600)
    return PresignedUploadResponse(
        upload_url=url,
        object_key=object_key,
        expires_in=3600,
    )