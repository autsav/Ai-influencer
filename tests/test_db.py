
from unittest.mock import MagicMock, patch

from aeloria.db.client import Db


def _db():
    with patch("aeloria.db.client.create_client") as mock_cc:
        mock_cc.return_value = MagicMock()
        return Db(settings=MagicMock())


def test_get_credential_returns_row():
    db = _db()
    db._client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"platform": "instagram", "access_token": "tok"}
    ]
    cred = db.get_credential("instagram")
    assert cred["access_token"] == "tok"


def test_get_credential_returns_none_when_empty():
    db = _db()
    db._client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    assert db.get_credential("instagram") is None


def test_upsert_credential_inserts_when_absent():
    db = _db()
    db._client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    db.insert = MagicMock(return_value={"id": "new"})
    row = db.upsert_credential("instagram", "tok", "2099-01-01T00:00:00+00:00")
    db.insert.assert_called_once()
    assert row["id"] == "new"


def test_upsert_credential_updates_when_present():
    db = _db()
    db._client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"id": "cred-1", "platform": "instagram"}
    ]
    db.update = MagicMock(return_value={"id": "cred-1"})
    db.upsert_credential("instagram", "newtok", "2099-01-01T00:00:00+00:00")
    db.update.assert_called_once()
    args = db.update.call_args
    assert args.args[0] == "platform_credentials"
    assert args.args[1] == "cred-1"
    assert args.args[2]["access_token"] == "newtok"


def test_update_credential_token_noop_when_absent():
    db = _db()
    db._client.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
    assert db.update_credential_token("instagram", "t", "2099-01-01") == {}


def test_select_due_for_publish_filters_posted_rows():
    db = _db()
    queue_rows = [
        {"id": "q1", "asset_id": "a1", "brief_id": "b1", "caption": "c", "slot_time": "2026-01-01T00:00:00+00:00"},
        {"id": "q2", "asset_id": "a2", "brief_id": "b2", "caption": "c", "slot_time": "2026-01-01T00:00:00+00:00"},
    ]
    # supabase fluent chains: table("queue").select.eq.lte.contains.execute().data
    q_chain = db._client.table.return_value.select.return_value
    q_chain.eq.return_value.lte.return_value.contains.return_value.execute.return_value.data = queue_rows
    # posts lookup: table("posts").select.in_.execute().data  → q1 already posted
    p_chain = db._client.table.return_value.select.return_value
    p_chain.in_.return_value.execute.return_value.data = [{"queue_id": "q1"}]
    rows = db.select_due_for_publish("instagram")
    ids = [r["id"] for r in rows]
    assert "q1" not in ids
    assert "q2" in ids
