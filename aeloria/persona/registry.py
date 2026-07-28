"""Multi-persona registry: manage multiple AI influencer characters.

Supports switching between personas at generation time — each persona has
its own LoRA URL, reference faces, visual DNA, and config. The pipeline
loads the active persona and routes generation through the correct LoRA.

Usage:
    from aeloria.persona.registry import PersonaRegistry, get_persona_config
    registry = PersonaRegistry()
    persona = registry.get("aeloria")
    settings_overrides = registry.get_settings_overrides("aeloria")
"""
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)


@dataclass
class PersonaConfig:
    """Configuration for a single persona/character."""
    name: str
    lora_url: str = ""
    lora_scale: float = 0.7
    reference_face_dir: str = ""
    persona_yaml: str = ""
    description: str = ""
    active: bool = False
    # Per-persona generation overrides
    guidance_scale: float = 3.5
    inference_steps: int = 40
    pulid_weight: float = 0.85
    face_gate_threshold: float = 0.35

    def __repr__(self):
        return f"PersonaConfig(name={self.name!r}, active={self.active}, lora={bool(self.lora_url)})"


class PersonaRegistry:
    """Registry of all available personas.

    Loads from a YAML file (default: `aeloria/persona/registry.yaml`) that
    defines multiple characters with their LoRA URLs, reference face dirs,
    and per-persona generation settings.
    """

    def __init__(self, registry_path: str = "aeloria/persona/registry.yaml"):
        self.registry_path = registry_path
        self._personas: dict[str, PersonaConfig] = {}
        self._load()

    def _load(self):
        """Load persona registry from YAML."""
        path = Path(self.registry_path)
        if not path.exists():
            log.info("Persona registry %s not found — using defaults", self.registry_path)
            # Create a default registry with Aeloria
            self._personas["aeloria"] = PersonaConfig(
                name="aeloria",
                lora_url="",  # Will use settings default
                reference_face_dir="aeloria/persona/reference_faces",
                persona_yaml="aeloria/persona/aeloria.yaml",
                description="Aeloria — 24yo female AI entrepreneur",
                active=True,
            )
            return

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        for name, cfg in data.get("personas", {}).items():
            self._personas[name] = PersonaConfig(
                name=name,
                lora_url=cfg.get("lora_url", ""),
                lora_scale=cfg.get("lora_scale", 0.7),
                reference_face_dir=cfg.get("reference_face_dir", ""),
                persona_yaml=cfg.get("persona_yaml", ""),
                description=cfg.get("description", ""),
                active=cfg.get("active", False),
                guidance_scale=cfg.get("guidance_scale", 3.5),
                inference_steps=cfg.get("inference_steps", 40),
                pulid_weight=cfg.get("pulid_weight", 0.85),
                face_gate_threshold=cfg.get("face_gate_threshold", 0.35),
            )

        log.info("Loaded %d personas from %s", len(self._personas), self.registry_path)

    def get(self, name: str) -> Optional[PersonaConfig]:
        """Get a persona by name. Returns None if not found."""
        return self._personas.get(name)

    def get_active(self) -> Optional[PersonaConfig]:
        """Get the currently active persona."""
        for p in self._personas.values():
            if p.active:
                return p
        # Fallback: return first persona
        if self._personas:
            return next(iter(self._personas.values()))
        return None

    def list_personas(self) -> list[str]:
        """List all registered persona names."""
        return list(self._personas.keys())

    def set_active(self, name: str) -> bool:
        """Set a persona as active (deactivates all others)."""
        if name not in self._personas:
            return False
        for p in self._personas.values():
            p.active = (p.name == name)
        log.info("Active persona set to: %s", name)
        return True

    def get_settings_overrides(self, name: str) -> dict:
        """Get settings overrides for a specific persona.

        Returns a dict of {field_name: value} that should override the
        global settings when generating for this persona.
        """
        persona = self.get(name)
        if not persona:
            return {}

        overrides = {}
        if persona.lora_url:
            overrides["aeloria_lora_url"] = persona.lora_url
        if persona.lora_scale:
            overrides["aeloria_lora_scale"] = persona.lora_scale
        if persona.reference_face_dir:
            overrides["face_ref_dir"] = persona.reference_face_dir
        if persona.guidance_scale:
            overrides["image_guidance_scale"] = persona.guidance_scale
        if persona.inference_steps:
            overrides["image_inference_steps"] = persona.inference_steps
        if persona.pulid_weight:
            overrides["pulid_weight"] = persona.pulid_weight
        if persona.face_gate_threshold:
            overrides["face_gate_threshold"] = persona.face_gate_threshold

        return overrides

    def save(self):
        """Save the current registry state back to YAML."""
        data = {"personas": {}}
        for name, p in self._personas.items():
            data["personas"][name] = {
                "lora_url": p.lora_url,
                "lora_scale": p.lora_scale,
                "reference_face_dir": p.reference_face_dir,
                "persona_yaml": p.persona_yaml,
                "description": p.description,
                "active": p.active,
                "guidance_scale": p.guidance_scale,
                "inference_steps": p.inference_steps,
                "pulid_weight": p.pulid_weight,
                "face_gate_threshold": p.face_gate_threshold,
            }

        with open(self.registry_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        log.info("Saved %d personas to %s", len(self._personas), self.registry_path)


# Module-level singleton
_registry: PersonaRegistry | None = None


def get_registry(registry_path: str = "aeloria/persona/registry.yaml") -> PersonaRegistry:
    """Get or create the singleton PersonaRegistry."""
    global _registry
    if _registry is None or _registry.registry_path != registry_path:
        _registry = PersonaRegistry(registry_path)
    return _registry