from aeloria.distribution.slots import best_time


def test_reel_slot_time():
    assert best_time("instagram", "reel", "2026-07-20") == "2026-07-20T18:00:00+00:00"


def test_static_slot_time():
    assert best_time("instagram", "static", "2026-07-20") == "2026-07-20T17:00:00+00:00"


def test_story_slot_time():
    assert best_time("instagram", "story", "2026-07-20") == "2026-07-20T09:00:00+00:00"


def test_unknown_slot_type_defaults_to_noon():
    assert best_time("instagram", "weird", "2026-07-20") == "2026-07-20T12:00:00+00:00"