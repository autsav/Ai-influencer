# tests/test_hook_spec.py
from aeloria.distribution.hook_spec import validate


def _brief(audience, slot_type="reel", hook_spec=None):
    return {"audience": audience, "slot_type": slot_type, "hook_spec": hook_spec}


def test_discovery_reel_with_valid_hook_passes():
    ok, reason = validate(_brief("discovery", "reel",
        "open on still cabin window at golden hour, text 'your 5am is a coping mechanism'"))
    assert ok and reason == ""


def test_discovery_reel_missing_hook_fails():
    ok, reason = validate(_brief("discovery", "reel", None))
    assert not ok
    assert "hook_spec" in reason


def test_discovery_reel_empty_hook_fails():
    ok, reason = validate(_brief("discovery", "reel", "   "))
    assert not ok


def test_discovery_reel_short_hook_fails():
    ok, reason = validate(_brief("discovery", "reel", "she looks up"))
    assert not ok
    assert "20" in reason or "longer" in reason


def test_retention_reel_no_hook_passes():
    ok, _ = validate(_brief("retention", "reel", None))
    assert ok


def test_discovery_static_no_hook_passes():
    ok, _ = validate(_brief("discovery", "static", None))
    assert ok


def test_missing_audience_field_passes():
    ok, _ = validate({"slot_type": "reel"})
    assert ok