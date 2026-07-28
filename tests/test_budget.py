"""Tests for cost guardrails — budget checks and fal.ai balance."""
import pytest
from unittest.mock import MagicMock, patch
from aeloria.budget import check_budget, check_fal_balance, BudgetExceeded


def test_check_budget_daily_cap_exceeded():
    db = MagicMock()
    db.sum_media_cost_today.return_value = 9.0
    db.sum_media_cost_week.return_value = 20.0
    settings = MagicMock()
    setattr(settings, "fal_daily_usd_cap", 10.0)
    setattr(settings, "fal_weekly_usd_cap", 50.0)

    with pytest.raises(BudgetExceeded, match="daily"):
        check_budget(db, settings, "fal", 2.0)


def test_check_budget_weekly_cap_exceeded():
    db = MagicMock()
    db.sum_media_cost_today.return_value = 5.0
    db.sum_media_cost_week.return_value = 48.0
    settings = MagicMock()
    setattr(settings, "fal_daily_usd_cap", 10.0)
    setattr(settings, "fal_weekly_usd_cap", 50.0)

    with pytest.raises(BudgetExceeded, match="weekly"):
        check_budget(db, settings, "fal", 3.0)


def test_check_budget_within_caps():
    db = MagicMock()
    db.sum_media_cost_today.return_value = 5.0
    db.sum_media_cost_week.return_value = 20.0
    settings = MagicMock()
    setattr(settings, "fal_daily_usd_cap", 10.0)
    setattr(settings, "fal_weekly_usd_cap", 50.0)
    check_budget(db, settings, "fal", 3.0)


def test_check_budget_unknown_engine():
    db = MagicMock()
    settings = MagicMock()
    with pytest.raises(ValueError, match="unknown engine"):
        check_budget(db, settings, "unknown", 1.0)


@patch("httpx.get")
def test_check_fal_balance_returns_float(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"balance": 12.50},
        raise_for_status=lambda: None,
    )
    settings = MagicMock()
    settings.fal_key = "fake-key"
    balance = check_fal_balance(settings, min_balance=0.01)
    assert balance == 12.50


@patch("httpx.get")
def test_check_fal_balance_low_raises(mock_get):
    mock_get.return_value = MagicMock(
        status_code=200,
        json=lambda: {"balance": 0.05},
        raise_for_status=lambda: None,
    )
    settings = MagicMock()
    settings.fal_key = "fake-key"
    with pytest.raises(BudgetExceeded, match="balance"):
        check_fal_balance(settings, min_balance=0.50)


@patch("httpx.get")
def test_check_fal_balance_network_error_returns_inf(mock_get):
    mock_get.side_effect = Exception("network error")
    settings = MagicMock()
    settings.fal_key = "fake-key"
    balance = check_fal_balance(settings, min_balance=1.0)
    assert balance == float("inf")
