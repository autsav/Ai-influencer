from aeloria.config import Settings
from aeloria.db.client import Db


class BudgetExceeded(Exception):
    pass


def check_budget(db: Db, settings: Settings, engine: str, planned_cost: float) -> None:
    if engine == "fal":
        cap = settings.fal_daily_usd_cap
    elif engine == "higgsfield":
        cap = settings.higgsfield_daily_credits_cap
    else:
        raise ValueError(f"unknown engine: {engine}")

    spent = db.sum_media_cost_today(engine)
    if spent is None:
        spent = 0.0
    if spent + planned_cost > cap:
        raise BudgetExceeded(
            f"{engine}: spent {spent} + planned {planned_cost} exceeds daily cap {cap}"
        )
