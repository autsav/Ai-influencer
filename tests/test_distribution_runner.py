from unittest.mock import MagicMock, patch

from aeloria.distribution.runner import run_distribution_pending


def _brief(bid, plan=None):
    return {"id": bid, "distribution_plan": plan, "status": "planned"}


@patch("aeloria.distribution.runner.plan")
def test_runner_plans_null_plan_briefs(mock_plan):
    mock_plan.return_value = {"slot_time": "x"}
    db = MagicMock()
    db.select.return_value = [_brief("b1"), _brief("b2", plan={"old": True})]
    n = run_distribution_pending(db, MagicMock(), MagicMock())
    # only the null-plan brief should be passed to plan()
    assert mock_plan.call_count == 1
    assert mock_plan.call_args.args[0]["id"] == "b1"
    assert n == 1


@patch("aeloria.distribution.runner.plan")
def test_runner_skips_when_plan_returns_none(mock_plan):
    mock_plan.return_value = None  # planner skipped (e.g. bad hook)
    db = MagicMock()
    db.select.return_value = [_brief("b1")]
    n = run_distribution_pending(db, MagicMock(), MagicMock())
    assert n == 0


@patch("aeloria.distribution.runner.plan")
def test_runner_one_bad_brief_doesnt_stop_others(mock_plan):
    mock_plan.side_effect = [RuntimeError("boom"), {"slot_time": "x"}]
    db = MagicMock()
    db.select.return_value = [_brief("b1"), _brief("b2")]
    n = run_distribution_pending(db, MagicMock(), MagicMock())
    assert mock_plan.call_count == 2
    assert n == 1