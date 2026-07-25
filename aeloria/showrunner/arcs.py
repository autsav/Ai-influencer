"""Arc state machine: tease -> peak -> callback -> done. An arc spans 4 slots
(phase_for_slot) then completes; the beat sheet starts a new arc per niche."""
from aeloria.db.client import Db

PHASES = ("tease", "peak", "callback", "done")

# slots spent in each phase before the next transition (done = terminal).
# 7 slots per arc = one weekly beat sheet (tease 2, peak 3, callback 2).
PHASE_SLOTS = {"tease": 2, "peak": 3, "callback": 2}

_TRANSITIONS = {"tease": "peak", "peak": "callback", "callback": "done"}


def next_phase(phase: str) -> str | None:
    if phase == "done":
        return None
    if phase not in _TRANSITIONS:
        raise ValueError(f"unknown arc phase: {phase!r}")
    return _TRANSITIONS[phase]


def phase_for_slot(slot_index_in_arc: int) -> str:
    """Map a 0-based slot index within an arc to its phase. 0-1->tease,
    2-4->peak, 5-6->callback, >=7->done (arc is full)."""
    if slot_index_in_arc < PHASE_SLOTS["tease"]:
        return "tease"
    if slot_index_in_arc < PHASE_SLOTS["tease"] + PHASE_SLOTS["peak"]:
        return "peak"
    if slot_index_in_arc < PHASE_SLOTS["tease"] + PHASE_SLOTS["peak"] + PHASE_SLOTS["callback"]:
        return "callback"
    return "done"


def create_arc(db: Db, name: str, niche: str) -> dict:
    return db.insert("arcs", {"name": name, "niche": niche, "phase": "tease"})


def advance_arc(db: Db, arc_id: str, phase: str) -> dict:
    fields = {"phase": phase}
    if phase == "done":
        # ended_at is a timestamptz; ISO string is fine for Supabase.
        from datetime import datetime, timezone
        fields["ended_at"] = datetime.now(timezone.utc).isoformat()
    return db.update("arcs", arc_id, fields)