from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import httpx

from aeloria.auth import token_store
from aeloria.auth.token_refresh import refresh_if_needed


def _settings():
    s = MagicMock()
    s.graph_base = "https://graph.facebook.com/v23.0"
    s.meta_app_id = "APP"
    s.meta_app_secret = "SECRET"
    return s


def _cred(days_left):
    exp = datetime.now(timezone.utc) + timedelta(days=days_left)
    return {"access_token": "old", "expires_at": exp.isoformat()}


def test_noop_when_more_than_10_days_left():
    db = MagicMock(); db.get_credential.return_value = _cred(20)
    tg = MagicMock()
    with patch("aeloria.auth.token_refresh.httpx.Client") as MC:
        refresh_if_needed(db, _settings(), tg)
        MC.assert_not_called()
        db.update_credential_token.assert_not_called()


def test_refreshes_when_under_10_days():
    db = MagicMock(); db.get_credential.return_value = _cred(5)
    tg = MagicMock()
    token_store.init("old")
    resp = MagicMock(); resp.raise_for_status.return_value = None
    resp.json.return_value = {"access_token": "NEW", "expires_in": 60 * 24 * 3600}
    client = MagicMock(); client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.get.return_value = resp
    with patch("aeloria.auth.token_refresh.httpx.Client", return_value=client):
        refresh_if_needed(db, _settings(), tg)
    assert token_store.get() == "NEW"
    db.update_credential_token.assert_called_once()
    args = db.update_credential_token.call_args
    assert args.args[0] == "instagram"
    assert args.args[1] == "NEW"
    tg.send_message.assert_called()


def test_noop_when_expiry_null():
    db = MagicMock(); db.get_credential.return_value = {"access_token": "t", "expires_at": None}
    tg = MagicMock()
    with patch("aeloria.auth.token_refresh.httpx.Client") as MC:
        refresh_if_needed(db, _settings(), tg)
        MC.assert_not_called()


def test_missing_credential_alerts_no_crash():
    db = MagicMock(); db.get_credential.return_value = None
    tg = MagicMock()
    refresh_if_needed(db, _settings(), tg)  # must not raise
    tg.send_message.assert_called()


def test_refresh_http_failure_alerts_and_keeps_old_token():
    db = MagicMock(); db.get_credential.return_value = _cred(5)
    tg = MagicMock()
    token_store.init("old")
    client = MagicMock(); client.__enter__.return_value = client
    client.__exit__.return_value = None
    client.get.side_effect = httpx.ConnectError("down")
    with patch("aeloria.auth.token_refresh.httpx.Client", return_value=client):
        refresh_if_needed(db, _settings(), tg)
    assert token_store.get() == "old"  # untouched
    db.update_credential_token.assert_not_called()
    tg.send_message.assert_called()