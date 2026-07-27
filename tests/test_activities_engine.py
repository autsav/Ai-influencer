from aeloria.showrunner.activities import (
    load_activities, load_cast, eligible, choose_activity, CATEGORY_PILLAR,
    _signal_gate,
)

ACTS = [
    {"id": "a_home", "category": "founder_lifestyle", "subjects": ["s1"], "setting": "home office",
     "mood": "focused", "style_hint": "film", "signal": False,
     "fits_locations": "home_office", "fits_seasons": [], "format_affinity": ["static"]},
    {"id": "a_any", "category": "food", "subjects": ["s2", "s3"], "setting": "café",
     "mood": "joyful", "style_hint": "film", "signal": False,
     "fits_locations": "anywhere", "fits_seasons": []},
    {"id": "a_travel", "category": "personal_growth", "subjects": ["s4"], "setting": "airport",
     "mood": "cool", "style_hint": "flash", "signal": False,
     "fits_locations": "travel_only", "fits_seasons": []},
    {"id": "a_signal", "category": "work", "subjects": ["s5"], "setting": "desk",
     "mood": "focused_playful", "style_hint": "selfie", "signal": True,
     "fits_locations": "anywhere", "fits_seasons": []},
]
HOME = {"location": "london_home", "season": "autumn", "category_weights": {}}
TRAVEL = {"location": "remote_travel", "season": "early_spring", "category_weights": {}}


def test_category_pillar_covers_all_categories():
    for cat in ("founder_lifestyle","style","food","fitness","work","social","personal_growth"):
        assert CATEGORY_PILLAR[cat] in ("ai_workflows","founder_lifestyle")


def test_eligible_filters_by_location():
    home = {a["id"] for a in eligible(ACTS, HOME, [])}
    assert "a_home" in home and "a_travel" not in home  # home_office in, travel_only out
    travel = {a["id"] for a in eligible(ACTS, TRAVEL, [])}
    assert "a_travel" in travel and "a_home" not in travel


def test_no_repeat_window_excludes_recent_then_relaxes():
    recent = [{"activity": "a_any", "activity_category": "food"}]
    out = {a["id"] for a in eligible(ACTS, HOME, recent)}
    assert "a_any" not in out          # recently used activity excluded
    # if everything eligible was recently used, it relaxes rather than returning empty
    recent2 = [{"activity": "a_home", "activity_category": "founder_lifestyle"},
               {"activity": "a_any", "activity_category": "food"},
               {"activity": "a_signal", "activity_category": "work"}]
    assert eligible(ACTS, HOME, recent2)  # non-empty after relax


def test_choose_activity_stamps_full_plan():
    plan = choose_activity(ACTS, [], HOME, [], "static", 12345)
    assert plan["activity"] in {"a_home", "a_any", "a_signal"}
    assert plan["subject"] and plan["setting"] and plan["style_hint"]
    assert plan["pillar"] in ("ai_workflows","founder_lifestyle")
    assert plan["time_of_day"]
    assert plan["cast_element"] is None  # no cast passed


def test_choose_activity_cast_element_when_hooked():
    cast = [{"id": "macbook", "type": "object",
             "appearance": "her MacBook Pro, silver",
             "hooks": ["a_home"], "frequency": 1.0}]
    # force a_home by making it the only eligible (home chapter, others filtered/relaxed)
    plan = choose_activity([ACTS[0]], cast, HOME, [], "static", 7)
    assert plan["activity"] == "a_home"
    assert "MacBook" in (plan["cast_element"] or "")


def test_signal_balance_drops_signal_when_recent_high():
    # recent 8 all signal -> signal fraction 1.0 >= 0.30 -> a_signal dropped
    recent = [{"activity": "a_signal", "activity_category": "work"} for _ in range(8)]
    picks = {choose_activity(ACTS, [], TRAVEL, recent, "static", h)["activity"] for h in range(50)}
    assert "a_signal" not in picks


# --- direct _signal_gate coverage (each branch isolated) ---------------------
_SG_ACTS = [
    {"id": "sig1", "signal": True},
    {"id": "sig2", "signal": True},
    {"id": "plain1", "signal": False},
    {"id": "plain2", "signal": False},
]


def test_signal_gate_drops_signal_when_fraction_high():
    recent = [{"activity": "sig1"} for _ in range(10)]
    pool = _signal_gate(_SG_ACTS, _SG_ACTS, recent)
    assert pool and all(not a.get("signal") for a in pool)
    assert {a["id"] for a in pool} == {"plain1", "plain2"}


def test_signal_gate_forces_signal_when_fraction_low():
    recent = [{"activity": "plain1"} for _ in range(10)]
    pool = _signal_gate(_SG_ACTS, _SG_ACTS, recent)
    assert pool and all(a.get("signal") for a in pool)
    assert {a["id"] for a in pool} == {"sig1", "sig2"}


def test_signal_gate_neutral_leaves_pool_unchanged():
    recent = ([{"activity": "sig1"}, {"activity": "sig2"}]
              + [{"activity": "plain1"} for _ in range(8)])
    pool = _signal_gate(_SG_ACTS, _SG_ACTS, recent)
    assert pool == _SG_ACTS