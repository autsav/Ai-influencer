from unittest.mock import MagicMock

import pytest

from aeloria.budget import BudgetExceeded, check_budget


def _settings():
    s = MagicMock()
    s.fal_daily_usd_cap = 2.50
    s.higgsfield_daily_credits_cap = 15.0
    return s


def test_under_cap_passes():
    db = MagicMock()
    db.sum_media_cost_today.return_value = 1.00
    check_budget(db, _settings(), "fal", 0.035)   # no raise


def test_over_cap_raises():
    db = MagicMock()
    db.sum_media_cost_today.return_value = 2.49
    with pytest.raises(BudgetExceeded):
        check_budget(db, _settings(), "fal", 0.035)


def test_higgsfield_uses_credit_cap():
    db = MagicMock()
    db.sum_media_cost_today.return_value = 14.95
    with pytest.raises(BudgetExceeded):
        check_budget(db, _settings(), "higgsfield", 0.12)


def test_unknown_engine_raises_valueerror():
    with pytest.raises(ValueError):
        check_budget(MagicMock(), _settings(), "dalle", 1.0)
