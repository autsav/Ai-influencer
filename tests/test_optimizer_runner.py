from datetime import date
from unittest.mock import MagicMock, patch

from aeloria.optimizer.runner import run_optimizer_pending


def _settings():
    s = MagicMock()
    s.optimizer_min_posts = 10
    s.optimizer_max_weight_delta = 0.20
    s.optimizer_analyst_enabled = False
    return s


def _db():
    db = MagicMock()
    db.current_follower_count.return_value = 0
    return db


@patch("aeloria.optimizer.runner.score_recent")
def test_cold_start_holds_defaults(mock_score):
    mock_score.return_value = {"n_posts": 4, "dimensions": {}}
    db = _db()
    n = run_optimizer_pending(db, _settings(), MagicMock(), tg=None, now=date(2026, 9, 7))
    assert n == 0
    db.save_strategy_weights.assert_not_called()


@patch("aeloria.optimizer.runner.write_memo")
@patch("aeloria.optimizer.runner.update_weights", return_value={"format_mix": {"reel": 6}})
@patch("aeloria.optimizer.runner.score_recent")
def test_updates_weights_when_enough_data(mock_score, mock_update, mock_memo):
    mock_score.return_value = {"n_posts": 20, "dimensions": {"content_format": {}}}
    db = _db()
    db.current_strategy_weights.return_value = None
    # Tuesday -> no memo
    n = run_optimizer_pending(db, _settings(), MagicMock(), tg=MagicMock(), now=date(2026, 9, 8))
    assert n == 1
    db.save_strategy_weights.assert_called_once()
    mock_memo.assert_not_called()


@patch("aeloria.optimizer.runner.write_memo")
@patch("aeloria.optimizer.runner.update_weights", return_value={"format_mix": {"reel": 6}})
@patch("aeloria.optimizer.runner.score_recent")
def test_sunday_writes_memo(mock_score, mock_update, mock_memo):
    mock_score.return_value = {"n_posts": 20, "dimensions": {}}
    db = _db()
    db.current_strategy_weights.return_value = None
    # 2026-09-06 is a Sunday
    n = run_optimizer_pending(db, _settings(), MagicMock(), tg=MagicMock(), now=date(2026, 9, 6))
    assert n == 1
    mock_memo.assert_called_once()


@patch("aeloria.optimizer.runner.write_memo", side_effect=Exception("claude down"))
@patch("aeloria.optimizer.runner.update_weights", return_value={"format_mix": {"reel": 6}})
@patch("aeloria.optimizer.runner.score_recent")
def test_memo_failure_does_not_block_weight_update(mock_score, mock_update, mock_memo):
    mock_score.return_value = {"n_posts": 20, "dimensions": {}}
    db = _db()
    db.current_strategy_weights.return_value = None
    n = run_optimizer_pending(db, _settings(), MagicMock(), tg=MagicMock(), now=date(2026, 9, 6))
    assert n == 1  # weights still saved despite memo crash
    db.save_strategy_weights.assert_called_once()


@patch("aeloria.optimizer.runner.write_memo")
@patch("aeloria.optimizer.runner.update_weights", return_value={"format_mix": {"reel": 6}})
@patch("aeloria.optimizer.runner.score_recent")
def test_score_recent_called_with_current_followers(mock_score, mock_update, mock_memo):
    mock_score.return_value = {"n_posts": 20, "dimensions": {}}
    db = _db()
    db.current_follower_count.return_value = 1234
    db.current_strategy_weights.return_value = None
    run_optimizer_pending(db, _settings(), MagicMock(), tg=MagicMock(), now=date(2026, 9, 8))
    mock_score.assert_called_once()
    assert mock_score.call_args.args[-1] == 1234


@patch("aeloria.optimizer.runner.write_memo")
@patch("aeloria.optimizer.runner.update_weights", return_value={"format_mix": {"reel": 6}})
@patch("aeloria.optimizer.runner.score_recent")
def test_analyst_disabled_sends_no_telegram_report(mock_score, mock_update, mock_memo):
    # optimizer_analyst_enabled=False (from _settings()) -> analyze() short-circuits to ""
    # before touching anthropic at all; no report is sent to Telegram.
    mock_score.return_value = {"n_posts": 20, "dimensions": {}}
    db = _db()
    db.current_strategy_weights.return_value = None
    tg = MagicMock()
    n = run_optimizer_pending(db, _settings(), MagicMock(), tg=tg, now=date(2026, 9, 8))
    assert n == 1
    tg.send_message.assert_not_called()
