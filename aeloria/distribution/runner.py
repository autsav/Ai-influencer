"""Scheduled job: enrich planned briefs that have no distribution_plan yet."""
import logging

from aeloria.distribution.planner import plan
from aeloria.persona.loader import Persona

log = logging.getLogger(__name__)


def run_distribution_pending(db, settings, persona: Persona, limit: int = 10) -> int:
    rows = db.select("briefs", {"status": "planned"}, limit=limit)
    done = 0
    for b in rows:
        if b.get("distribution_plan"):
            continue
        try:
            result = plan(b, db, settings, persona)
        except Exception as e:
            log.error("distribution plan failed for brief %s: %s", b["id"], e)
            continue
        if result:
            done += 1
    return done