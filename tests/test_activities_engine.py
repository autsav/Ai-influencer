from aeloria.showrunner.activities import (
    load_activities, load_cast, eligible, choose_activity, CATEGORY_PILLAR,
    _signal_gate,
)

ACTS = [
    {"id": "a_home", "category": "home", "subjects": ["s1"], "setting": "kitchen",
     "mood": "relaxed", "style_hint": "film", "signal": False,
     "fits_locations": "home_only", "fits_seasons": [], "format_affinity": ["static"]},
    {"id": "a_any", "category": "food", "subjects": ["s2", "s3"], "setting": "café",
     "mood": "joyful", "style_hint": "film", "signal": False,
     "fits_locations": "anywhere", "fits_seasons": []},
    {"id": "a_travel", "category": "travel", "subjects": ["s4"], "setting": "airport",
     "mood": "cool", "style_hint": "flash", "signal": False,
     "fits_locations": "travel_only", "fits_seasons": []},
    {"id": "a_signal", "category": "get_ready", "subjects": ["s5"], "setting": "vanity",
     "mood": "focused_playful", "style_hint": "selfie", "signal": True,
     "fits_locations": "anywhere", "fits_seasons": []},
]
HOME = {"location": "forest_house", "season": "autumn", "category_weights": {}}
TOKYO = {"location": "tokyo", "season": "early_spring", "category_weights": {}}


def test_category_pillar_covers_all_categories():
    for cat in ("get_ready","style","food","fitness","work","home","errands",
                "social","travel","wellness","pet","hobby"):
        assert CATEGORY_PILLAR[cat] in ("slow_living","self_healing","fitness","travel")


def test_eligible_filters_by_location():
    home = {a["id"] for a in eligible(ACTS, HOME, [])}
    assert "a_home" in home and "a_travel" not in home  # home_only in, travel_only out
    tok = {a["id"] for a in eligible(ACTS, TOKYO, [])}
    assert "a_travel" in tok and "a_home" not in tok


def test_no_repeat_window_excludes_recent_then_relaxes():
    recent = [{"activity": "a_any", "activity_category": "food"}]
    out = {a["id"] for a in eligible(ACTS, HOME, recent)}
    assert "a_any" not in out          # recently used activity excluded
    # if everything eligible was recently used, it relaxes rather than returning empty
    recent2 = [{"activity": "a_home", "activity_category": "home"},
               {"activity": "a_any", "activity_category": "food"},
               {"activity": "a_signal", "activity_category": "get_ready"}]
    assert eligible(ACTS, HOME, recent2)  # non-empty after relax


def test_choose_activity_stamps_full_plan():
    plan = choose_activity(ACTS, [], HOME, [], "static", 12345)
    assert plan["activity"] in {"a_home", "a_any", "a_signal"}
    assert plan["subject"] and plan["setting"] and plan["style_hint"]
    assert plan["pillar"] in ("slow_living","self_healing","fitness","travel")
    assert plan["time_of_day"]
    assert plan["cast_element"] is None  # no cast passed


def test_choose_activity_cast_element_when_hooked():
    cast = [{"id": "juniper", "type": "pet",
             "appearance": "her golden retriever Juniper",
             "hooks": ["a_home"], "frequency": 1.0}]
    # force a_home by making it the only eligible (home chapter, others filtered/relaxed)
    plan = choose_activity([ACTS[0]], cast, HOME, [], "static", 7)
    assert plan["activity"] == "a_home"
    assert "Juniper" in (plan["cast_element"] or "")


def test_signal_balance_drops_signal_when_recent_high():
    # recent 8 all signal -> signal fraction 1.0 >= 0.25 -> a_signal dropped
    recent = [{"activity": "a_signal", "activity_category": "get_ready"} for _ in range(8)]
    # eligible relaxes the no-repeat, but signal gate should still drop signal acts
    picks = {choose_activity(ACTS, [], TOKYO, recent, "static", h)["activity"] for h in range(50)}
    assert "a_signal" not in picks


# --- direct _signal_gate coverage (each branch isolated) ---------------------
_SG_ACTS = [
    {"id": "sig1", "signal": True},
    {"id": "sig2", "signal": True},
    {"id": "plain1", "signal": False},
    {"id": "plain2", "signal": False},
]


def test_signal_gate_drops_signal_when_fraction_high():
    # 10/10 recent are signal -> frac 1.0 >= 0.30 -> DROP: pool has no signal acts.
    recent = [{"activity": "sig1"} for _ in range(10)]
    pool = _signal_gate(_SG_ACTS, _SG_ACTS, recent)
    assert pool and all(not a.get("signal") for a in pool)
    assert {a["id"] for a in pool} == {"plain1", "plain2"}


def test_signal_gate_forces_signal_when_fraction_low():
    # 0/10 recent are signal -> frac 0.0 <= 0.10 -> FORCE: only signal acts remain.
    recent = [{"activity": "plain1"} for _ in range(10)]
    pool = _signal_gate(_SG_ACTS, _SG_ACTS, recent)
    assert pool and all(a.get("signal") for a in pool)
    assert {a["id"] for a in pool} == {"sig1", "sig2"}


def test_signal_gate_neutral_leaves_pool_unchanged():
    # 2/10 recent are signal -> frac 0.2, inside (0.10, 0.30) -> NEUTRAL: no change.
    recent = ([{"activity": "sig1"}, {"activity": "sig2"}]
              + [{"activity": "plain1"} for _ in range(8)])
    pool = _signal_gate(_SG_ACTS, _SG_ACTS, recent)
    assert pool == _SG_ACTS  # returned unchanged (both signal and plain present)
