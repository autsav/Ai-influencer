"""Orchestrator: build a distribution_plan for one brief and persist it.
Idempotent (skips briefs with a non-null plan unless force). $0 — rule-based."""
from pathlib import Path

from aeloria.distribution import collabs, hook_spec, seo, slots, trends
from aeloria.persona.loader import Persona


def resolve_niche(brief: dict, db, persona: Persona) -> str:
    arc_id = brief.get("arc_id")
    if arc_id:
        rows = db.select("arcs", {"id": arc_id}, limit=1)
        if rows and rows[0].get("niche"):
            return rows[0]["niche"]
    return persona.niches.core


def plan(brief: dict, db, settings, persona: Persona, force: bool = False) -> dict | None:
    if brief.get("distribution_plan") and not force:
        return None

    # The worker is the hard hook gate; planner still skips discovery reels
    # missing a hook so it doesn't write a plan for a brief that will fail.
    ok, _ = hook_spec.validate(brief)
    if not ok:
        return None

    niche = resolve_niche(brief, db, persona)

    active = trends.load_active(None, db)
    trending_audio = trends.match(active, brief)

    seo_plan = seo.build(persona, brief)

    collab_entries = collabs.load()
    collab_targets = collabs.match(collab_entries, niche)

    platform = (brief.get("platforms") or ["instagram"])[0]
    slot_time = slots.best_time(
        platform,
        brief.get("slot_type", "reel"),
        brief["slot_day"],
        niche=niche,
        audience=brief.get("audience"),
        learnings_path=Path("aeloria/distribution/learnings.json"),
    )

    plan_dict = {
        "trending_audio": trending_audio,
        "hashtags": seo_plan["hashtags"],
        "on_screen_keywords": seo_plan["on_screen_keywords"],
        "collab_targets": collab_targets,
        "slot_time": slot_time,
    }
    db.update("briefs", brief["id"], {"distribution_plan": plan_dict})
    return plan_dict