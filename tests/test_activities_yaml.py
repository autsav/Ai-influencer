from aeloria.showrunner.activities import load_activities

_CATS = {"get_ready","style","food","fitness","work","home","errands",
         "social","travel","wellness","pet","hobby"}
_STYLES = {"selfie","film","flash","paparazzi","any"}
_LOCS = {"anywhere","home_only","city_only","travel_only"}


def test_activities_library_shape_and_coverage():
    acts = load_activities()
    assert len(acts) >= 36                          # ~40, at least 3 per category
    cats = {a["category"] for a in acts}
    assert _CATS <= cats                            # every category represented
    ids = [a["id"] for a in acts]
    assert len(ids) == len(set(ids))                # unique ids
    for a in acts:
        assert a["category"] in _CATS
        assert a["subjects"] and all(isinstance(s, str) and s for s in a["subjects"])
        assert a["setting"]
        assert a["style_hint"] in _STYLES
        assert a["fits_locations"] in _LOCS
        assert isinstance(a["signal"], bool)
        for f in (a.get("format_affinity") or []):
            assert f in {"reel","carousel","static"}


def test_signal_and_travel_activities_exist():
    acts = load_activities()
    assert sum(1 for a in acts if a["signal"]) >= 6        # enough influencer-meta shots
    assert any(a["fits_locations"] == "travel_only" for a in acts)
    assert any(a["fits_locations"] == "home_only" for a in acts)
    # a pet activity hooks the dog; a café activity exists
    assert any(a["category"] == "pet" for a in acts)
