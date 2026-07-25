"""Per-platform best-slot timing. Static defaults now (matching worker.SLOT_HOUR_UTC);
the optimizer (5b) refines these later from metrics."""
from datetime import datetime, time as dtime, timezone

SLOT_HOUR_UTC = {"story": 9, "static": 17, "reel": 18}
DEFAULT_HOUR = 12


def best_time(platform: str, slot_type: str, slot_day: str) -> str:
    """Return an ISO-8601 UTC timestamp for the slot on slot_day (YYYY-MM-DD).
    platform is accepted for future per-platform refinement; ignored today."""
    day = datetime.strptime(slot_day, "%Y-%m-%d").date()
    hour = SLOT_HOUR_UTC.get(slot_type, DEFAULT_HOUR)
    return datetime.combine(day, dtime(hour=hour), tzinfo=timezone.utc).isoformat()