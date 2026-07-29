"""Look library loader — selects looks from the 100-look YAML by context.

Resolves jewelry, makeup, hairstyle references into concrete prompt strings
and returns a complete brief ready for generate_consistent().

Usage:
    from aeloria.persona.look_library import LookLibrary
    lib = LookLibrary()
    brief = lib.get_look(96)  # spring blossom look
    # Or by context:
    brief = lib.get_look_by_context("cafe working session")
"""
import logging
import random
from pathlib import Path
from typing import Optional

import yaml

log = logging.getLogger(__name__)


class LookLibrary:
    """Load and resolve looks from the 100-look YAML library.

    Each look references pools (jewelry, makeup, hairstyles) which are
    resolved into concrete description strings for the FLUX prompt.
    """

    def __init__(self, library_path: str = "aeloria/persona/look_library.yaml"):
        self.library_path = library_path
        self._data: dict = {}
        self._pose_pool: list = []
        self._load()

    def _load(self):
        path = Path(self.library_path)
        if not path.exists():
            log.warning("Look library %s not found", self.library_path)
            return
        with open(path) as f:
            self._data = yaml.safe_load(f) or {}
        log.info("Loaded look library: %d looks", len(self._data.get("looks", {})))
        # Companion swimsuit pose pool — same directory, optional.
        # Loaded here so consumers (get_look) can populate brief['pose_override']
        # without separate wiring. If absent, pose_override is an empty dict and
        # prompt_builder falls back to its deterministic hash-pick path.
        pose_path = path.parent / "swimsuit_poses.yaml"
        if pose_path.exists():
            with open(pose_path) as f:
                self._pose_pool = (yaml.safe_load(f) or {}).get("poses", []) or []
            log.info("Loaded pose pool: %d poses", len(self._pose_pool))
        else:
            log.info("Pose pool %s not found — pose_override will be empty", pose_path)

    @property
    def looks(self) -> dict:
        return self._data.get("looks", {})

    @property
    def jewelry_pools(self) -> dict:
        return self._data.get("jewelry", {})

    @property
    def makeup_pools(self) -> dict:
        return self._data.get("makeup", {})

    @property
    def hairstyle_pools(self) -> dict:
        return self._data.get("hairstyles", {})

    @property
    def pose_pool(self) -> list:
        """Loaded list of swimsuit poses (aeloria/persona/swimsuit_poses.yaml).
        Empty list if the file is missing.
        """
        return self._pose_pool

    def _resolve_jewelry(self, ref: str) -> str:
        """Resolve a jewelry reference ('pearl', 'minimal_gold', 'statement[2]')
        to a concrete description string. Bracket-index form returns one item;
        plain pool name returns the first two joined for variety.
        """
        if not ref:
            return ref
        # Bracket-index form: pool[idx] → single concrete item
        if "[" in ref and "]" in ref:
            pool_name = ref.split("[")[0]
            try:
                idx = int(ref.split("[")[1].split("]")[0])
            except ValueError:
                return ref
            pool = self.jewelry_pools.get(pool_name, [])
            if 0 <= idx < len(pool):
                return pool[idx]
            return pool[0] if pool else ref
        # Plain pool-name form: join first two items
        if ref in self.jewelry_pools:
            items = self.jewelry_pools[ref]
            if isinstance(items, list):
                return ", ".join(items[:2])  # pick first 2 for variety
            return str(items)
        return ref  # unknown pool name — leak through as a literal marker

    def _resolve_makeup(self, ref: str) -> str:
        """Resolve makeup reference to a description string."""
        if ref in self.makeup_pools:
            m = self.makeup_pools[ref]
            return m.get("details", m.get("description", ref))
        return ref

    def _resolve_hairstyle(self, ref: str) -> str:
        """Resolve hairstyle reference (e.g. 'loose[0]', 'updo[3]') to a string."""
        if "[" in ref and "]" in ref:
            pool_name = ref.split("[")[0]
            idx = int(ref.split("[")[1].split("]")[0])
            pool = self.hairstyle_pools.get(pool_name, [])
            if 0 <= idx < len(pool):
                return pool[idx]
            return pool[0] if pool else ref
        return ref

    def _resolve_pose(self, look_id: int) -> dict:
        """Build the pose_override dict prompt_builder.py:341-346 expects.

        Picks a pose deterministically (look_id → pool index). Only carries
        `description` for now — the swimsuit_poses.yaml schema doesn't expose
        body/arm/leg fields yet. Missing keys fall through to prompt_builder's
        cinematic-neutral defaults.
        """
        if not self._pose_pool:
            return {}
        pose = self._pose_pool[(look_id - 1) % len(self._pose_pool)]
        return {
            "name": pose.get("name", ""),
            "description": pose.get("description", ""),
        }

    def get_look(self, look_id: int) -> dict:
        """Get a fully resolved look by ID (1-100).

        Returns a brief dict with all fields resolved to strings,
        ready for generate_consistent().
        """
        look = self.looks.get(str(look_id)) or self.looks.get(look_id)
        if not look:
            raise KeyError(f"Look {look_id} not found in library")

        jewelry_desc = self._resolve_jewelry(look.get("jewelry", ""))
        makeup_desc = self._resolve_makeup(look.get("makeup", ""))
        hair_desc = self._resolve_hairstyle(look.get("hair", ""))

        # Build the full prompt_seed with all style elements
        scene = look.get("scene", "")
        wardrobe = look.get("wardrobe", "")

        prompt_seed = (
            f"Aeloria {scene}, "
            f"wearing {wardrobe}, "
            f"{jewelry_desc}, "
            f"{hair_desc}, "
            f"makeup: {makeup_desc}, "
            f"green eyes, fair skin with freckles, "
            f"shot on 85mm f/1.4, Kodak Portra 400"
        )

        brief = {
            "pillar": "founder_lifestyle",  # default — can be overridden
            "wardrobe": f"{wardrobe}, {jewelry_desc}",
            "mood": "natural, confident, authentic",
            "style_override": "film_editorial",
            "aspect_ratio": "4:5",
            "cta_kind": "save",
            "hashtags": ["#FounderLife", "#Aeloria"],
            "seed": look_id,
            "prompt_seed": prompt_seed,
            "look_id": look_id,
            "pose_override": self._resolve_pose(look_id),
            "context": look.get("context", ""),
        }

        log.info("Resolved look %d: context=%s", look_id, look.get("context", ""))
        return brief

    def get_look_by_context(self, context: str) -> dict:
        """Find a look matching the given context and return the resolved brief."""
        for lid, look in self.looks.items():
            if context.lower() in look.get("context", "").lower():
                return self.get_look(int(lid))
        # Fallback: random look
        return self.get_look(random.choice(list(self.looks.keys())))

    def get_random_look(self) -> dict:
        """Get a random look from the library."""
        if not self.looks:
            raise KeyError("No looks in library")
        return self.get_look(random.choice(list(self.looks.keys())))

    def list_contexts(self) -> list[str]:
        """List all available contexts."""
        return [v.get("context", "") for v in self.looks.values()]

    def count(self) -> int:
        """Total number of looks."""
        return len(self.looks)