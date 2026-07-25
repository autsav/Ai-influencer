from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from aeloria.analytics.runner import run_analytics_pending


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


def _settings(meta=True):
    s = MagicMock()
    s.meta_app_id = "app" if meta else ""
    s.ig_user_id = "ig-1" if meta else ""
    return s


def _post(pid, brief_id, hours_ago, platform_post_id="mid-1"):
    pub = NOW - timedelta(hours=hours_ago)
    return {
        "id": pid, "brief_id": brief_id, "platform": "instagram",
        "platform_post_id": platform_post_id, "published_at": pub.isoformat(),
    }


def _db(posts, *, latest=(), nightly_today=False, follower_today=False,
        brief_rows=None, follower_count_inserts=None):
    db = MagicMock()
    db.select.side_effect = lambda table, filters=None, limit=100: (
        list(posts) if table == "posts"
        else list(brief_rows or []) if table == "briefs"
        else []
    )
    db.select_all.side_effect = lambda table, filters=None, order=None: (
        list(posts) if table == "posts" else []
    )
    db.latest_metric_snapshot.side_effect = lambda pid, snap: (pid, snap) in latest
    db.has_nightly_today.return_value = nightly_today
    db.has_follower_snapshot_today.return_value = follower_today
    db.insert.side_effect = lambda table, row: {**row, "id": f"{table}-id"}
    return db


@patch("aeloria.analytics.runner.fetch_insights")
@patch("aeloria.analytics.runner.fetch_followers")
@patch("aeloria.analytics.runner.refresh_if_needed")
@patch("aeloria.analytics.runner.datetime")
def test_plus3h_inserts_once(mock_dt, mock_refresh, mock_ff, mock_fi):
    mock_dt.now.return_value = NOW
    mock_dt.fromisoformat.side_effect = datetime.fromisoformat
    mock_ff.return_value = 1000
    mock_fi.return_value = {"views": 1, "likes": 2, "comments": 0, "shares": 0,
                            "sends": 0, "saves": 0, "watch_through": None,
                            "non_follower_reach": None}
    db = _db([_post("p1", "b1", hours_ago=4)],
             follower_today=False,
             brief_rows=[{"id": "b1", "slot_type": "reel"}])
    n = run_analytics_pending(db, _settings())
    assert n == 2  # +3h metrics row + follower snapshot row
    metrics_inserts = [c for c in db.insert.call_args_list if c.args[0] == "metrics"]
    assert len(metrics_inserts) == 1
    assert metrics_inserts[0].args[1]["snapshot"] == "+3h"
    assert metrics_inserts[0].args[1]["post_id"] == "p1"
    fs_inserts = [c for c in db.insert.call_args_list if c.args[0] == "follower_snapshots"]
    assert len(fs_inserts) == 1
    assert fs_inserts[0].args[1]["followers"] == 1000


@patch("aeloria.analytics.runner.fetch_insights")
@patch("aeloria.analytics.runner.fetch_followers")
@patch("aeloria.analytics.runner.refresh_if_needed")
@patch("aeloria.analytics.runner.datetime")
def test_plus3h_idempotent_when_row_exists(mock_dt, mock_refresh, mock_ff, mock_fi):
    mock_dt.now.return_value = NOW
    mock_dt.fromisoformat.side_effect = datetime.fromisoformat
    mock_ff.return_value = 100
    db = _db([_post("p1", "b1", hours_ago=4)],
             latest={("p1", "+3h")}, follower_today=True,
             brief_rows=[{"id": "b1", "slot_type": "reel"}])
    n = run_analytics_pending(db, _settings())
    assert n == 0
    mock_fi.assert_not_called()
    metrics_inserts = [c for c in db.insert.call_args_list if c.args[0] == "metrics"]
    assert len(metrics_inserts) == 0


@patch("aeloria.analytics.runner.fetch_insights")
@patch("aeloria.analytics.runner.fetch_followers")
@patch("aeloria.analytics.runner.refresh_if_needed")
@patch("aeloria.analytics.runner.datetime")
def test_plus48h_and_nightly_when_old(mock_dt, mock_refresh, mock_ff, mock_fi):
    mock_dt.now.return_value = NOW
    mock_dt.fromisoformat.side_effect = datetime.fromisoformat
    mock_ff.return_value = 100
    mock_fi.return_value = {"views": 1, "likes": 2, "comments": 0, "shares": 0,
                            "sends": 0, "saves": 0, "watch_through": None,
                            "non_follower_reach": None}
    # 50h old; +3h already captured; +48h and nightly due
    db = _db([_post("p1", "b1", hours_ago=50)],
             latest={("p1", "+3h")}, nightly_today=False, follower_today=True,
             brief_rows=[{"id": "b1", "slot_type": "reel"}])
    n = run_analytics_pending(db, _settings())
    snaps = [c.args[1]["snapshot"] for c in db.insert.call_args_list if c.args[0] == "metrics"]
    assert "+48h" in snaps and "nightly" in snaps
    assert "+3h" not in snaps
    assert n == 2


@patch("aeloria.analytics.runner.fetch_insights")
@patch("aeloria.analytics.runner.fetch_followers")
@patch("aeloria.analytics.runner.refresh_if_needed")
@patch("aeloria.analytics.runner.datetime")
def test_nightly_idempotent_per_day(mock_dt, mock_refresh, mock_ff, mock_fi):
    mock_dt.now.return_value = NOW
    mock_dt.fromisoformat.side_effect = datetime.fromisoformat
    mock_ff.return_value = 100
    mock_fi.return_value = {"views": 1, "likes": 0, "comments": 0, "shares": 0,
                            "sends": 0, "saves": 0, "watch_through": None,
                            "non_follower_reach": None}
    # 50h old; +3h and +48h present; nightly already today -> no nightly insert
    db = _db([_post("p1", "b1", hours_ago=50)],
             latest={("p1", "+3h"), ("p1", "+48h")}, nightly_today=True, follower_today=True,
             brief_rows=[{"id": "b1", "slot_type": "reel"}])
    n = run_analytics_pending(db, _settings())
    assert n == 0
    metrics_inserts = [c for c in db.insert.call_args_list if c.args[0] == "metrics"]
    assert len(metrics_inserts) == 0


@patch("aeloria.analytics.runner.fetch_insights")
@patch("aeloria.analytics.runner.fetch_followers")
@patch("aeloria.analytics.runner.refresh_if_needed")
@patch("aeloria.analytics.runner.datetime")
def test_dry_run_post_skipped(mock_dt, mock_refresh, mock_ff, mock_fi):
    mock_dt.now.return_value = NOW
    mock_dt.fromisoformat.side_effect = datetime.fromisoformat
    mock_ff.return_value = 100
    db = _db([_post("p1", "b1", hours_ago=4, platform_post_id="dry_run")],
             follower_today=True, brief_rows=[{"id": "b1", "slot_type": "static"}])
    n = run_analytics_pending(db, _settings())
    assert n == 0
    mock_fi.assert_not_called()


@patch("aeloria.analytics.runner.fetch_insights")
@patch("aeloria.analytics.runner.fetch_followers")
@patch("aeloria.analytics.runner.refresh_if_needed")
@patch("aeloria.analytics.runner.datetime")
def test_follower_snapshot_once_per_day(mock_dt, mock_refresh, mock_ff, mock_fi):
    mock_dt.now.return_value = NOW
    mock_dt.fromisoformat.side_effect = datetime.fromisoformat
    mock_ff.return_value = 555
    db = _db([_post("p1", "b1", hours_ago=4)],
             latest={("p1", "+3h")}, follower_today=True,
             brief_rows=[{"id": "b1", "slot_type": "reel"}])
    run_analytics_pending(db, _settings())
    mock_ff.assert_not_called()  # already snapshotted today
    fs_inserts = [c for c in db.insert.call_args_list if c.args[0] == "follower_snapshots"]
    assert len(fs_inserts) == 0


@patch("aeloria.analytics.runner.fetch_insights")
@patch("aeloria.analytics.runner.fetch_followers")
@patch("aeloria.analytics.runner.refresh_if_needed")
def test_no_meta_creds_returns_zero(mock_refresh, mock_ff, mock_fi):
    db = _db([_post("p1", "b1", hours_ago=4)], follower_today=False,
             brief_rows=[{"id": "b1", "slot_type": "reel"}])
    n = run_analytics_pending(db, _settings(meta=False))
    assert n == 0
    mock_ff.assert_not_called()
    mock_fi.assert_not_called()


@patch("aeloria.analytics.runner.fetch_insights")
@patch("aeloria.analytics.runner.fetch_followers")
@patch("aeloria.analytics.runner.refresh_if_needed")
@patch("aeloria.analytics.runner.datetime")
def test_per_post_failure_does_not_stop_round(mock_dt, mock_refresh, mock_ff, mock_fi):
    mock_dt.now.return_value = NOW
    mock_dt.fromisoformat.side_effect = datetime.fromisoformat
    mock_ff.return_value = 100
    mock_fi.side_effect = [RuntimeError("boom"), {"views": 1, "likes": 0, "comments": 0,
                            "shares": 0, "sends": 0, "saves": 0, "watch_through": None,
                            "non_follower_reach": None}]
    posts = [_post("p1", "b1", hours_ago=4), _post("p2", "b2", hours_ago=4)]
    db = _db(posts, follower_today=True,
             brief_rows=[{"id": "b1", "slot_type": "reel"}, {"id": "b2", "slot_type": "static"}])
    n = run_analytics_pending(db, _settings())
    assert n == 1  # p1 failed, p2 succeeded
    assert mock_fi.call_count == 2