from aeloria.showrunner.activities import load_activities

_CATS = {"founder_lifestyle","style","food","fitness","work","social","personal_growth"}
_STYLES = {"selfie","film","flash","paparazzi","any"}
_LOCS = {"anywhere","home_office","coworking","city_only","travel_only"}


def test_activities_library_shape_and_coverage():
    acts = load_activities()
    assert len(acts) >= 15                          # ~20 activities
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


def test_signal_and_home_activities_exist():
    acts = load_activities()
    assert sum(1 for a in acts if a["signal"]) >= 5        # enough influencer-meta shots
    assert any(a["fits_locations"] == "home_office" for a in acts)
    assert any(a["fits_locations"] == "coworking" for a in acts)
    # a work activity exists
    assert any(a["category"] == "work" for a in acts)