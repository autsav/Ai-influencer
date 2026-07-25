"""Load and validate JSON pipeline configurations."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_CHARACTER_KEYS = {"name", "lora_url", "lora_scale", "visual_dna"}
REQUIRED_PIPELINE_KEYS = {"stages"}


@dataclass
class CharacterConfig:
    name: str = "Aeloria"
    lora_url: str = ""
    lora_scale: float = 0.7
    guidance_scale: float = 3.5
    num_inference_steps: int = 40
    image_model: str = "rundiffusion-fal/juggernaut-flux-lora"
    aspect_ratio: str = "4:5"
    visual_dna: dict[str, str] = field(default_factory=dict)
    skin_realism: str = ""
    identity_lock: str = ""
    negative_prompt: str = ""


@dataclass
class VoiceConfig:
    elevenlabs_api_key: str = ""
    voice_id: str = "EXAVITQu4vr4xnSDxMaL"
    stability: float = 0.5
    similarity_boost: float = 0.75
    synclabs_api_key: str = ""
    hedra_api_key: str = ""
    enable_lip_sync: bool = False


@dataclass
class QCConfig:
    min_width: int = 512
    min_height: int = 512
    max_file_size_mb: float = 20.0
    face_gate_enabled: bool = True
    face_gate_threshold: float = 0.35
    artifact_check_enabled: bool = True
    check_aspect_ratio: bool = True
    expected_aspect: str = "4:5"


@dataclass
class PipelineConfig:
    character: CharacterConfig = field(default_factory=CharacterConfig)
    voice: VoiceConfig = field(default_factory=VoiceConfig)
    qc: QCConfig = field(default_factory=QCConfig)
    dry_run: bool = False
    output_dir: str = "output/pipeline"
    log_file: str = "logs/pipeline.log"
    stages: list[str] = field(default_factory=lambda: ["image", "qc", "publish"])


def load_character_config(path: str) -> CharacterConfig:
    with open(path) as f:
        data = json.load(f)
    missing = REQUIRED_CHARACTER_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Character config missing keys: {missing}")
    return CharacterConfig(
        name=data["name"],
        lora_url=data["lora_url"],
        lora_scale=data.get("lora_scale", 0.7),
        guidance_scale=data.get("guidance_scale", 3.5),
        num_inference_steps=data.get("num_inference_steps", 40),
        image_model=data.get("image_model", "rundiffusion-fal/juggernaut-flux-lora"),
        aspect_ratio=data.get("aspect_ratio", "4:5"),
        visual_dna=data["visual_dna"],
        skin_realism=data.get("skin_realism", ""),
        identity_lock=data.get("identity_lock", ""),
        negative_prompt=data.get("negative_prompt", ""),
    )


def load_pipeline_config(path: str) -> PipelineConfig:
    with open(path) as f:
        data = json.load(f)
    char = CharacterConfig()
    voice = VoiceConfig()
    qc = QCConfig()
    if "character" in data:
        char = CharacterConfig(
            name=data["character"].get("name", "Aeloria"),
            lora_url=data["character"].get("lora_url", ""),
            lora_scale=data["character"].get("lora_scale", 0.7),
            guidance_scale=data["character"].get("guidance_scale", 3.5),
            num_inference_steps=data["character"].get("num_inference_steps", 40),
            image_model=data["character"].get("image_model", "rundiffusion-fal/juggernaut-flux-lora"),
            aspect_ratio=data["character"].get("aspect_ratio", "4:5"),
            visual_dna=data["character"].get("visual_dna", {}),
        )
    if "voice" in data:
        v = data["voice"]
        voice = VoiceConfig(
            elevenlabs_api_key=v.get("elevenlabs_api_key", ""),
            voice_id=v.get("voice_id", "EXAVITQu4vr4xnSDxMaL"),
            stability=v.get("stability", 0.5),
            similarity_boost=v.get("similarity_boost", 0.75),
            synclabs_api_key=v.get("synclabs_api_key", ""),
            hedra_api_key=v.get("hedra_api_key", ""),
            enable_lip_sync=v.get("enable_lip_sync", False),
        )
    if "qc" in data:
        q = data["qc"]
        qc = QCConfig(
            min_width=q.get("min_width", 512),
            min_height=q.get("min_height", 512),
            max_file_size_mb=q.get("max_file_size_mb", 20.0),
            face_gate_enabled=q.get("face_gate_enabled", True),
            face_gate_threshold=q.get("face_gate_threshold", 0.35),
            artifact_check_enabled=q.get("artifact_check_enabled", True),
            check_aspect_ratio=q.get("check_aspect_ratio", True),
            expected_aspect=q.get("expected_aspect", "4:5"),
        )
    return PipelineConfig(
        character=char,
        voice=voice,
        qc=qc,
        dry_run=data.get("dry_run", False),
        output_dir=data.get("output_dir", "output/pipeline"),
        log_file=data.get("log_file", "logs/pipeline.log"),
        stages=data.get("stages", ["image", "qc", "publish"]),
    )