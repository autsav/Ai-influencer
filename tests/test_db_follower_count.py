from unittest.mock import MagicMock

from aeloria.db.client import Db


def _db_with_mock():
    db = Db.__new__(Db)
    db._client = MagicMock()
    return db, db._client


def _chain(client, table, data):
    """Return the query chain for `table` pre-seeded to resolve `.execute().data` = data."""
    q = client.table.return_value.select.return_value
    q.eq.return_value = q
    q.order.return_value = q
    q.gte.return_value = q
    q.limit.return_value.execute.return_value.data = data
    return q


def test_current_follower_count_returns_latest_snapshot():
    db, client = _db_with_mock()
    _chain(client, "follower_snapshots", [{"followers": 1337}])
    assert db.current_follower_count() == 1337
    client.table.assert_called_with("follower_snapshots")


def test_current_follower_count_zero_when_no_snapshot():
    db, client = _db_with_mock()
    _chain(client, "follower_snapshots", [])
    assert db.current_follower_count() == 0


def test_latest_metric_snapshot_true_when_row_exists():
    db, client = _db_with_mock()
    _chain(client, "metrics", [{"id": "m1"}])
    assert db.latest_metric_snapshot("post-1", "+3h") is True


def test_latest_metric_snapshot_false_when_absent():
    db, client = _db_with_mock()
    _chain(client, "metrics", [])
    assert db.latest_metric_snapshot("post-1", "+3h") is False


def test_has_nightly_today_true_when_row_today():
    db, client = _db_with_mock()
    _chain(client, "metrics", [{"id": "mn"}])
    assert db.has_nightly_today("post-1") is True


def test_has_nightly_today_false_when_absent():
    db, client = _db_with_mock()
    _chain(client, "metrics", [])
    assert db.has_nightly_today("post-1") is False


def test_has_follower_snapshot_today_true():
    db, client = _db_with_mock()
    _chain(client, "follower_snapshots", [{"id": "fs1"}])
    assert db.has_follower_snapshot_today() is True


def test_has_follower_snapshot_today_false():
    db, client = _db_with_mock()
    _chain(client, "follower_snapshots", [])
    assert db.has_follower_snapshot_today() is False