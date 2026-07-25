from pathlib import Path

import yaml
from pydantic import BaseModel


class PersonaError(Exception):
    pass


class Wedge(BaseModel):
    world: str = ""
    reel_format: str = ""
    voice_pov: str = ""


class Niches(BaseModel):
    core: str
    secondary: str
    arcs: list[str] = []
    experiments: list[str] = []


class Persona(BaseModel):
    version: int = 1
    identity: dict
    wedge: Wedge = Wedge()
    visual_dna: dict
    voice: dict
    niches: Niches
    hard_rules: list[str]
    character: dict = {}
    mannerisms: list[str] = []
    expression_repertoire: list[str] = []


DEFAULT_PATH = Path(__file__).parent / "aeloria.yaml"
BACKSTORY_PATH = Path(__file__).parent / "backstory.yaml"


def _load_backstory() -> dict:
    """Load backstory.yaml for human-reference data (not used by generation pipeline)."""
    try:
        return yaml.safe_load(BACKSTORY_PATH.read_text()) or {}
    except (OSError, yaml.YAMLError):
        return {}


def load_persona(path: str | None = None) -> Persona:
    p = Path(path) if path else DEFAULT_PATH
    try:
        data = yaml.safe_load(p.read_text())
    except (OSError, yaml.YAMLError) as e:
        raise PersonaError(f"cannot read persona bible: {e}") from e

    # Ensure voice.catchphrases is populated from backstory.yaml (if present)
    # This keeps captions working while lore stays out of generation prompts.
    if "voice" not in data:
        data["voice"] = {}
    if "catchphrases" not in data["voice"]:
        bs = _load_backstory()
        if "catchphrases" in bs:
            data["voice"]["catchphrases"] = bs["catchphrases"]

    try:
        return Persona(**data)
    except Exception as e:
        raise PersonaError(f"persona bible invalid: {e}") from e
