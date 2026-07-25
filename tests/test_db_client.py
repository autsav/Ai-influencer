from unittest.mock import MagicMock

from aeloria.db.client import Db


def _db_with_mock():
    db = Db.__new__(Db)          # skip __init__, inject mock
    db._client = MagicMock()
    return db, db._client


def test_insert_returns_row():
    db, client = _db_with_mock()
    client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "1"}]
    row = db.insert("arcs", {"name": "trip"})
    assert row == {"id": "1"}
    client.table.assert_called_with("arcs")


def test_select_applies_filters():
    db, client = _db_with_mock()
    q = client.table.return_value.select.return_value
    q.eq.return_value = q
    q.limit.return_value.execute.return_value.data = [{"id": "1"}]
    rows = db.select("briefs", {"status": "planned"}, limit=5)
    assert rows == [{"id": "1"}]
    q.eq.assert_called_with("status", "planned")


def test_sum_media_cost_today():
    db, client = _db_with_mock()
    q = client.table.return_value.select.return_value
    q.eq.return_value = q
    q.gte.return_value.execute.return_value.data = [{"cost": 0.5}, {"cost": 1.25}]
    assert db.sum_media_cost_today("fal") == 1.75


def test_update_returns_row():
    db, client = _db_with_mock()
    q = client.table.return_value.update.return_value
    q.eq.return_value.execute.return_value.data = [{"id": "1", "approval": "approved"}]
    row = db.update("queue", "1", {"approval": "approved"})
    assert row["approval"] == "approved"
    q.eq.assert_called_with("id", "1")


def test_update_empty_result_returns_empty_dict():
    db, client = _db_with_mock()
    q = client.table.return_value.update.return_value
    q.eq.return_value.execute.return_value.data = []
    assert db.update("queue", "missing", {"approval": "approved"}) == {}


def _chained_query(client):
    """One query mock where every builder method returns the query itself."""
    q = client.table.return_value.select.return_value
    for m in ("eq", "gte", "order", "in_", "range", "limit"):
        getattr(q, m).return_value = q
    return q


def test_select_all_pages_past_the_row_cap():
    db, client = _db_with_mock()
    q = _chained_query(client)
    page1 = [{"id": str(i)} for i in range(2)]
    page2 = [{"id": "2"}]
    q.execute.side_effect = [
        MagicMock(data=page1), MagicMock(data=page2),
    ]
    rows = db.select_all("briefs", order="slot_day", page_size=2)
    assert rows == page1 + page2
    q.order.assert_called_with("slot_day")
    assert q.range.call_args_list == [((0, 1),), ((2, 3),)]


def test_select_all_applies_filters():
    db, client = _db_with_mock()
    q = _chained_query(client)
    q.execute.return_value = MagicMock(data=[{"id": "1"}])
    rows = db.select_all("briefs", {"status": "planned"})
    assert rows == [{"id": "1"}]
    q.eq.assert_called_with("status", "planned")


def test_select_posts_published_since_filters_and_orders():
    db, client = _db_with_mock()
    q = _chained_query(client)
    q.execute.return_value = MagicMock(data=[{"id": "p1"}])
    rows = db.select_posts_published_since("2026-07-01T00:00:00+00:00")
    assert rows == [{"id": "p1"}]
    client.table.assert_called_with("posts")
    q.gte.assert_called_with("published_at", "2026-07-01T00:00:00+00:00")
    q.order.assert_called_with("published_at")


def test_select_metrics_for_posts_uses_in_filter():
    db, client = _db_with_mock()
    q = _chained_query(client)
    q.execute.return_value = MagicMock(data=[{"post_id": "p1"}])
    rows = db.select_metrics_for_posts(["p1", "p2"])
    assert rows == [{"post_id": "p1"}]
    client.table.assert_called_with("metrics")
    q.in_.assert_called_with("post_id", ["p1", "p2"])


def test_select_metrics_for_posts_empty_ids_no_query():
    db, client = _db_with_mock()
    assert db.select_metrics_for_posts([]) == []
    client.table.assert_not_called()


def test_latest_metric_for_post_orders_desc_limit_one():
    db, client = _db_with_mock()
    q = _chained_query(client)
    q.execute.return_value = MagicMock(data=[{"id": "m9", "captured_at": "2026-07-18"}])
    row = db.latest_metric_for_post("p1")
    assert row == {"id": "m9", "captured_at": "2026-07-18"}
    q.eq.assert_called_with("post_id", "p1")
    q.order.assert_called_with("captured_at", desc=True)
    q.limit.assert_called_with(1)


def test_latest_metric_for_post_none_when_no_rows():
    db, client = _db_with_mock()
    q = _chained_query(client)
    q.execute.return_value = MagicMock(data=[])
    assert db.latest_metric_for_post("p1") is None
