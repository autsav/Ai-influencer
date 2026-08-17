from unittest.mock import MagicMock, patch

from aeloria.distribution.planner import plan, resolve_niche
from aeloria.persona.loader import load_persona

PERSONA = load_persona()


def _brief(**over):
    base = {
        "id": "b1", "slot_day": "2026-07-20", "slot_type": "reel",
        "audience": "discovery", "beat": "forest trail at dawn",
        "caption_brief": "slow ambient morning", "platforms": ["instagram"],
        "engine": "fal", "hook_spec": "still window golden hour then motion on a beat",
        "arc_id": None, "distribution_plan": None,
    }
    base.update(over)
    return base


def test_resolve_niche_uses_arc_when_present():
    db = MagicMock()
    db.select.return_value = [{"id": "a1", "niche": "travel"}]
    assert resolve_niche({"arc_id": "a1"}, db, PERSONA) == "travel"


def test_resolve_niche_falls_back_to_core():
    db = MagicMock()
    db.select.return_value = []
    assert resolve_niche({"arc_id": None}, db, PERSONA) == PERSONA.niches.core


@patch("aeloria.distribution.planner.trends")
@patch("aeloria.distribution.planner.collabs")
def test_plan_builds_full_dict_and_writes(wcols, wtrends):
    wtrends.load_active.return_value = [
        {"ref": "forest-ambient-123", "note": "forest ambient", "kind": "audio", "source": "yaml"}]
    wtrends.match.return_value = "forest-ambient-123"
    entry = [{"handle": "@forestmeditations", "niches": ["wellness"], "kind": "comment"}]
    wcols.load.return_value = entry
    wcols.match.return_value = entry
    db = MagicMock()
    db.select.return_value = []  # arc lookup empty → core niche
    plan_out = plan(_brief(), db, MagicMock(), PERSONA)
    assert plan_out is not None
    assert set(plan_out.keys()) == {"trending_audio", "hashtags", "on_screen_keywords", "collab_targets", "slot_time"}
    assert plan_out["trending_audio"] == "forest-ambient-123"
    assert 3 <= len(plan_out["hashtags"]) <= 5
    # U2: slot_time uses anti-batch minute offset grid (0/13/17/23/27/33/37/43/47);
    # assert hour + grid membership, not the exact pre-pivot ":00" minute.
    from datetime import datetime as _dt
    from aeloria.distribution.slots import ANTI_BATCH_MINUTES
    _slot_dt = _dt.fromisoformat(plan_out["slot_time"])
    assert _slot_dt.hour == 18
    assert _slot_dt.minute in ANTI_BATCH_MINUTES
    assert plan_out["collab_targets"][0]["handle"] == "@forestmeditations"
    db.update.assert_called_once()
    args = db.update.call_args.args
    assert args[0] == "briefs" and args[1] == "b1" and args[2]["distribution_plan"] == plan_out


def test_plan_skips_when_already_planned():
    db = MagicMock()
    assert plan(_brief(distribution_plan={"has": "already"}), db, MagicMock(), PERSONA) is None
    db.update.assert_not_called()


@patch("aeloria.distribution.planner.collabs")
def test_plan_force_replans(wcols):
    wcols.load.return_value = []
    db = MagicMock()
    db.select.return_value = []
    plan_out = plan(_brief(distribution_plan={"old": True}), db, MagicMock(), PERSONA, force=True)
    assert plan_out is not None
    db.update.assert_called_once()


def test_plan_skips_discovery_reel_with_bad_hook():
    db = MagicMock()
    db.select.return_value = []
    bad = _brief(hook_spec=None)
    assert plan(bad, db, MagicMock(), PERSONA) is None
    db.update.assert_not_called()


@patch("aeloria.distribution.planner.collabs")
def test_plan_handles_missing_collab_file(wcols):
    wcols.load.return_value = []
    wcols.match.return_value = []
    db = MagicMock()
    db.select.return_value = []
    plan_out = plan(_brief(), db, MagicMock(), PERSONA)
    assert plan_out is not None
    assert plan_out["collab_targets"] == []