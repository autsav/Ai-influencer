"""Scheduled job: build the weekly beat sheet (arc + planned briefs) and run
the daily micro-pass (echo yesterday's winning beat into today's story).
Rule-based, $0 — no LLM calls. Idle run is a safe no-op once a week's briefs
already exist (idempotent via existing-days set in build_week)."""
from datetime import datetime, timezone

from aeloria.showrunner.beat_sheet import build_week
from aeloria.showrunner.micro_pass import micro_pass


def run_showrunner_pending(db, settings, persona, horizon_days: int | None = None) -> int:
    """Build briefs for the horizon (default settings.showrunner_horizon_days) and
    run the daily micro-pass. Returns the number of new briefs inserted this run."""
    today = datetime.now(timezone.utc).date()
    days = horizon_days if horizon_days is not None else settings.showrunner_horizon_days
    created = build_week(persona, db, today, days, settings=settings)
    micro_pass(db, persona, today)
    return len(created)