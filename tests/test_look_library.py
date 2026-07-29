"""Tests for the 100-look fashion library."""
import pytest
from aeloria.persona.look_library import LookLibrary


@pytest.fixture
def library():
    return LookLibrary()


class TestLookLibrary:
    def test_loads_100_looks(self, library):
        assert library.count() == 100

    def test_get_look_by_id(self, library):
        brief = library.get_look(1)
        assert brief["look_id"] == 1
        assert "Aeloria" in brief["prompt_seed"]
        assert "wardrobe" in brief
        assert "context" in brief

    def test_get_look_resolves_jewelry(self, library):
        brief = library.get_look(1)
        # Look 1 uses minimal_gold which resolves to specific jewelry items
        assert "gold" in brief["wardrobe"].lower()

    def test_get_look_resolves_makeup(self, library):
        brief = library.get_look(1)
        # Look 1 uses natural_glow makeup
        assert "bronzy" in brief["prompt_seed"].lower() or "glow" in brief["prompt_seed"].lower()

    def test_get_look_resolves_hairstyle(self, library):
        brief = library.get_look(1)
        # Look 1 uses loose[0] which resolves to "auburn hair loose and wavy..."
        assert "auburn hair" in brief["prompt_seed"].lower()

    def test_get_look_has_film_stock(self, library):
        brief = library.get_look(50)
        assert "Kodak Portra" in brief["prompt_seed"]

    def test_get_look_by_context(self, library):
        brief = library.get_look_by_context("cafe working")
        assert "cafe" in brief["context"].lower()

    def test_get_look_by_context_fuzzy_match(self, library):
        brief = library.get_look_by_context("airport")
        assert "airport" in brief["context"].lower()

    def test_get_random_look(self, library):
        brief = library.get_random_look()
        assert "look_id" in brief
        assert brief["look_id"] >= 1
        assert brief["look_id"] <= 100

    def test_list_contexts(self, library):
        contexts = library.list_contexts()
        assert len(contexts) == 100
        assert any("cafe" in c.lower() for c in contexts)

    def test_look_has_seed(self, library):
        brief = library.get_look(42)
        assert brief["seed"] == 42

    def test_invalid_look_id_raises(self, library):
        with pytest.raises(KeyError):
            library.get_look(999)

    def test_resolves_hairstyle_with_index(self, library):
        # loose[0] should resolve to first hairstyle in the loose pool
        brief = library.get_look(1)
        # Look 1 hair is loose[0]
        assert "wavy" in brief["prompt_seed"].lower() or "center-parted" in brief["prompt_seed"].lower()

    def test_makeup_details_in_prompt(self, library):
        # Look 5 uses soft_glam makeup
        brief = library.get_look(5)
        assert "smudged" in brief["prompt_seed"].lower() or "berry" in brief["prompt_seed"].lower() or "bronzy" in brief["prompt_seed"].lower()

    def test_all_looks_have_context(self, library):
        for lid, look in library.looks.items():
            assert look.get("context"), f"Look {lid} missing context"

    def test_all_looks_have_wardrobe(self, library):
        for lid, look in library.looks.items():
            assert look.get("wardrobe"), f"Look {lid} missing wardrobe"

    def test_all_looks_have_scene(self, library):
        for lid, look in library.looks.items():
            assert look.get("scene"), f"Look {lid} missing scene"

    def test_context_categories_covered(self, library):
        contexts = library.list_contexts()
        all_contexts = " ".join(contexts).lower()
        # Verify all major categories are represented
        assert "office" in all_contexts
        assert "cafe" in all_contexts
        assert "city" in all_contexts
        assert "travel" in all_contexts or "airport" in all_contexts
        assert "conference" in all_contexts or "event" in all_contexts
        assert "fitness" in all_contexts or "gym" in all_contexts or "yoga" in all_contexts
        assert "dinner" in all_contexts or "social" in all_contexts

    # ── Leak-detection regression tests (Bug 3 + Bug 4 fixes) ────────────

    def test_look_8_wardrobe_no_jewelry_bracket_leak(self, library):
        """Bug 3 — look 8 references jewelry 'statement[0]'. After the resolver
        fix this must resolve to a concrete item; the raw 'statement[' literal
        must NOT survive into the brief's wardrobe string.
        """
        brief = library.get_look(8)
        assert "statement[" not in brief["wardrobe"], (
            f"jewelry bracket leak: {brief['wardrobe']!r}"
        )

    def test_look_40_prompt_seed_no_golden_glow_literal(self, library):
        """Bug 4 — look 40 references makeup 'golden_glow'. With the pool
        entry added, the brief's prompt_seed must not contain the literal
        pool name after 'makeup: '.
        """
        brief = library.get_look(40)
        ps = brief["prompt_seed"].lower()
        assert "makeup: golden_glow" not in ps, (
            f"makeup pool leak in look 40: {ps[:200]!r}"
        )

    def test_all_looks_resolve_cleanly(self, library):
        """All 100 looks must resolve jewelry/makeup/hair without bracket
        leaks and without referencing unknown pool names. Catches both Bug 3
        (jewelry bracket form) and Bug 4 (unknown makeup pool) globally.
        """
        jewelry = set(library.jewelry_pools.keys())
        makeup = set(library.makeup_pools.keys())
        unresolved = []
        for lid, look in library.looks.items():
            j = look.get("jewelry", "")
            if not j:
                continue
            if "[" in j and "]" in j:
                # Bracket form — pool must exist and index must be in range
                pool_name = j.split("[")[0]
                idx_str = j.split("[")[1].split("]")[0]
                if pool_name not in jewelry:
                    unresolved.append(f"look {lid} jewelry={j!r}: unknown pool")
                else:
                    try:
                        idx = int(idx_str)
                    except ValueError:
                        unresolved.append(f"look {lid} jewelry={j!r}: bad index")
                        continue
                    if not (0 <= idx < len(library.jewelry_pools[pool_name])):
                        unresolved.append(
                            f"look {lid} jewelry={j!r}: index out of range"
                        )
            elif j not in jewelry:
                unresolved.append(f"look {lid} jewelry={j!r}: not a pool name")
            m = look.get("makeup", "")
            if m and m not in makeup:
                unresolved.append(f"look {lid} makeup={m!r}: not a pool name")
        assert not unresolved, "unresolved refs:\n  " + "\n  ".join(unresolved)

    def test_look_8_prompt_seed_resolves_jewelry(self, library):
        """Cross-check that look 8's resolved jewelry lands in prompt_seed
        (not just the wardrobe), and is a real jewelry string — not a bracket.
        """
        brief = library.get_look(8)
        ps = brief["prompt_seed"]
        assert "statement[" not in ps
        assert (
            "gold" in ps.lower()
            or "earring" in ps.lower()
            or "cuff" in ps.lower()
        ), f"no concrete jewelry landed in prompt_seed: {ps[:300]!r}"

    def test_look_40_makeup_details_resolved(self, library):
        """Cross-check that look 40's resolved makeup actually carries the
        golden_glow details string — proving the pool entry was wired right.
        """
        brief = library.get_look(40)
        ps = brief["prompt_seed"].lower()
        # Should describe golden glow / radiance — words from the pool details.
        assert (
            "golden hour" in ps
            or "radiance" in ps
            or "bronzy" in ps
        ), f"golden_glow details did not land in prompt_seed: {ps[:300]!r}"