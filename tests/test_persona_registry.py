"""Tests for multi-persona registry."""
import pytest
import yaml
import tempfile
from pathlib import Path

from aeloria.persona.registry import (
    PersonaRegistry,
    PersonaConfig,
    get_registry,
)


def _write_registry_yaml(tmp_path, personas_data):
    """Helper: write a registry YAML file."""
    registry_path = tmp_path / "registry.yaml"
    with open(registry_path, "w") as f:
        yaml.dump({"personas": personas_data}, f, default_flow_style=False)
    return str(registry_path)


class TestPersonaConfig:
    def test_defaults(self):
        p = PersonaConfig(name="test")
        assert p.name == "test"
        assert p.lora_url == ""
        assert p.lora_scale == 0.7
        assert p.active is False

    def test_repr(self):
        p = PersonaConfig(name="aeloria", active=True, lora_url="https://example.com/lora.safetensors")
        r = repr(p)
        assert "aeloria" in r
        assert "active=True" in r


class TestPersonaRegistry:
    def test_load_from_yaml(self, tmp_path):
        personas = {
            "aeloria": {
                "lora_url": "https://example.com/aeloria.safetensors",
                "lora_scale": 0.7,
                "reference_face_dir": "faces/aeloria",
                "persona_yaml": "persona/aeloria.yaml",
                "description": "AI entrepreneur",
                "active": True,
            },
            "socrates": {
                "lora_url": "https://example.com/socrates.safetensors",
                "lora_scale": 0.65,
                "reference_face_dir": "faces/socrates",
                "persona_yaml": "persona/socrates.yaml",
                "description": "Stoic philosopher",
                "active": False,
            },
        }
        path = _write_registry_yaml(tmp_path, personas)
        registry = PersonaRegistry(path)

        assert len(registry.list_personas()) == 2
        assert "aeloria" in registry.list_personas()
        assert "socrates" in registry.list_personas()

    def test_get_persona(self, tmp_path):
        personas = {
            "aeloria": {"lora_url": "https://example.com/a.safetensors", "active": True},
        }
        path = _write_registry_yaml(tmp_path, personas)
        registry = PersonaRegistry(path)

        p = registry.get("aeloria")
        assert p is not None
        assert p.name == "aeloria"
        assert p.lora_url == "https://example.com/a.safetensors"

    def test_get_nonexistent_returns_none(self, tmp_path):
        path = _write_registry_yaml(tmp_path, {})
        registry = PersonaRegistry(path)
        assert registry.get("nonexistent") is None

    def test_get_active(self, tmp_path):
        personas = {
            "aeloria": {"active": True, "lora_url": "https://a.com/l.safetensors"},
            "socrates": {"active": False, "lora_url": "https://s.com/l.safetensors"},
        }
        path = _write_registry_yaml(tmp_path, personas)
        registry = PersonaRegistry(path)

        active = registry.get_active()
        assert active is not None
        assert active.name == "aeloria"

    def test_get_active_fallback_first(self, tmp_path):
        """If no persona is active, return the first one."""
        personas = {
            "alpha": {"active": False},
            "beta": {"active": False},
        }
        path = _write_registry_yaml(tmp_path, personas)
        registry = PersonaRegistry(path)

        active = registry.get_active()
        assert active is not None
        assert active.name == "alpha"  # first registered

    def test_set_active(self, tmp_path):
        personas = {
            "aeloria": {"active": True},
            "socrates": {"active": False},
        }
        path = _write_registry_yaml(tmp_path, personas)
        registry = PersonaRegistry(path)

        assert registry.get_active().name == "aeloria"
        assert registry.set_active("socrates") is True
        assert registry.get_active().name == "socrates"
        assert registry.get("aeloria").active is False

    def test_set_active_nonexistent(self, tmp_path):
        path = _write_registry_yaml(tmp_path, {"aeloria": {"active": True}})
        registry = PersonaRegistry(path)
        assert registry.set_active("nonexistent") is False

    def test_get_settings_overrides(self, tmp_path):
        personas = {
            "aeloria": {
                "lora_url": "https://example.com/lora.safetensors",
                "lora_scale": 0.65,
                "reference_face_dir": "faces/aeloria",
                "guidance_scale": 2.0,
                "inference_steps": 35,
                "pulid_weight": 0.90,
                "face_gate_threshold": 0.40,
                "active": True,
            },
        }
        path = _write_registry_yaml(tmp_path, personas)
        registry = PersonaRegistry(path)

        overrides = registry.get_settings_overrides("aeloria")
        assert overrides["aeloria_lora_url"] == "https://example.com/lora.safetensors"
        assert overrides["aeloria_lora_scale"] == 0.65
        assert overrides["face_ref_dir"] == "faces/aeloria"
        assert overrides["image_guidance_scale"] == 2.0
        assert overrides["image_inference_steps"] == 35
        assert overrides["pulid_weight"] == 0.90
        assert overrides["face_gate_threshold"] == 0.40

    def test_get_settings_overrides_nonexistent(self, tmp_path):
        path = _write_registry_yaml(tmp_path, {})
        registry = PersonaRegistry(path)
        assert registry.get_settings_overrides("nonexistent") == {}

    def test_save_registry(self, tmp_path):
        path = str(tmp_path / "registry.yaml")
        registry = PersonaRegistry(path)
        registry._personas["test"] = PersonaConfig(
            name="test",
            lora_url="https://example.com/test.safetensors",
            active=True,
        )
        registry.save()

        # Reload and verify
        registry2 = PersonaRegistry(path)
        p = registry2.get("test")
        assert p is not None
        assert p.lora_url == "https://example.com/test.safetensors"
        assert p.active is True

    def test_default_registry_when_no_file(self, tmp_path):
        """When registry YAML doesn't exist, creates default with Aeloria."""
        path = str(tmp_path / "nonexistent.yaml")
        registry = PersonaRegistry(path)

        assert "aeloria" in registry.list_personas()
        aeloria = registry.get("aeloria")
        assert aeloria.active is True
        assert aeloria.reference_face_dir == "aeloria/persona/reference_faces"

    def test_list_personas(self, tmp_path):
        personas = {
            "alpha": {"active": True},
            "beta": {"active": False},
            "gamma": {"active": False},
        }
        path = _write_registry_yaml(tmp_path, personas)
        registry = PersonaRegistry(path)

        names = registry.list_personas()
        assert len(names) == 3
        assert set(names) == {"alpha", "beta", "gamma"}


class TestGetRegistry:
    def test_singleton(self, tmp_path):
        """get_registry returns the same instance for the same path."""
        path = str(tmp_path / "registry.yaml")
        r1 = get_registry(path)
        r2 = get_registry(path)
        assert r1 is r2

    def test_different_paths_different_instances(self, tmp_path):
        p1 = str(tmp_path / "r1.yaml")
        p2 = str(tmp_path / "r2.yaml")
        r1 = get_registry(p1)
        r2 = get_registry(p2)
        assert r1 is not r2