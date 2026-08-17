"""Existing slots tests updated for U2: live posting-time optimizer.

`best_time()` now applies the anti-batch minute offset (0/13/17/23/27/33/37/43/47)
on every call, so hour assertions are exact but minute assertions are grid-only.
"""
from datetime import datetime

from aeloria.distribution.slots import ANTI_BATCH_MINUTES, best_time


def test_reel_slot_time():
    iso = best_time("instagram", "reel", "2026-07-20")
    dt = datetime.fromisoformat(iso)
    assert dt.hour == 18
    assert dt.minute in ANTI_BATCH_MINUTES


def test_static_slot_time():
    iso = best_time("instagram", "static", "2026-07-20")
    dt = datetime.fromisoformat(iso)
    assert dt.hour == 17
    assert dt.minute in ANTI_BATCH_MINUTES


def test_story_slot_time():
    iso = best_time("instagram", "story", "2026-07-20")
    dt = datetime.fromisoformat(iso)
    assert dt.hour == 9
    assert dt.minute in ANTI_BATCH_MINUTES


def test_unknown_slot_type_defaults_to_noon():
    iso = best_time("instagram", "weird", "2026-07-20")
    dt = datetime.fromisoformat(iso)
    assert dt.hour == 12
    assert dt.minute in ANTI_BATCH_MINUTES
