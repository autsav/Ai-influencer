from unittest.mock import MagicMock

from aeloria.db.client import Db


def _db_with_client(client):
    db = Db.__new__(Db)
    db._client = client
    return db


def test_current_strategy_weights_returns_weights_or_none():
    client = MagicMock()
    chain = client.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value
    chain.execute.return_value.data = [{"weights": {"format_mix": {"reel": 5}}}]
    db = _db_with_client(client)
    assert db.current_strategy_weights() == {"format_mix": {"reel": 5}}
    chain.execute.return_value.data = []
    assert db.current_strategy_weights() is None


def test_save_strategy_weights_inserts_new_then_demotes_others():
    client = MagicMock()
    client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "w1", "current": True, "weights": {"format_mix": {"reel": 4}}}]
    db = _db_with_client(client)
    out = db.save_strategy_weights({"format_mix": {"reel": 4}}, note="n")
    assert out["id"] == "w1"
    # demote existing current rows EXCEPT the newly-inserted one (no zero-current window)
    client.table.return_value.update.assert_called_with({"current": False})
    update_chain = client.table.return_value.update.return_value
    update_chain.eq.assert_called_with("current", True)
    update_chain.eq.return_value.neq.assert_called_with("id", "w1")
