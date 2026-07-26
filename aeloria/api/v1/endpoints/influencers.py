"""GET /api/v1/influencers — fetch persona profiles."""
from __future__ import annotations

import logging

from fastapi import APIRouter

from aeloria.schemas.v1 import InfluencerProfileResponse
from aeloria.persona.loader import load_persona
from aeloria.config import get_settings

router = APIRouter()
log = logging.getLogger(__name__)


def _to_profile() -> InfluencerProfileResponse:
    persona = load_persona()
    settings = get_settings()
    identity = persona.identity if isinstance(persona.identity, dict) else {}
    visual_dna = persona.visual_dna if isinstance(persona.visual_dna, dict) else {}
    return InfluencerProfileResponse(
        name=identity.get("name", "Aeloria"),
        version="4.0",
        niche=persona.niches.core,
        bio=identity.get("bio", ""),
        visual_dna=visual_dna,
        content_mix={"photo": 0.3, "carousel": 0.3, "video": 0.3, "stories": 0.1},
        lora_url=getattr(settings, "aeloria_lora_url", ""),
        lora_scale=getattr(settings, "aeloria_lora_scale", 0.7),
    )


@router.get("/influencers", response_model=list[InfluencerProfileResponse])
async def list_influencers():
    """List all available influencer profiles (currently just Aeloria)."""
    return [_to_profile()]


@router.get("/influencers/{name}", response_model=InfluencerProfileResponse)
async def get_influencer(name: str):
    """Fetch a specific influencer profile by name."""
    return _to_profile()