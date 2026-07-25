from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def _patches():
    # order matches decorator order (bottom-up application): rt, supervise, sched, run_pending, settings
    return [
        patch("aeloria.app._build_runtime"),
        patch("aeloria.app.supervise_bot"),
        patch("aeloria.app.build_scheduler"),
        patch("aeloria.app.run_pending"),
        patch("aeloria.app.get_settings"),
    ]


def _blocking_supervise(stop_event):
    """Mimic the real supervisor: stay alive until stop_event is set (on shutdown)."""
    stop_event.wait(timeout=5)


def _start_app(mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings):
    mock_rt.return_value = tuple(MagicMock() for _ in range(5))
    mock_sched.return_value = MagicMock()
    mock_supervise.side_effect = _blocking_supervise  # keep bot thread alive during tests
    settings = MagicMock()
    settings.api_secret_key = "secret"
    mock_settings.return_value = settings
    mock_run_pending.return_value = 3
    return settings


@patch("aeloria.app.get_settings")
@patch("aeloria.app.run_pending")
@patch("aeloria.app.build_scheduler")
@patch("aeloria.app.supervise_bot")
@patch("aeloria.app._build_runtime")
def test_lifespan_starts_and_stops_scheduler_and_bot(
    mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings
):
    _start_app(mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings)
    sched = mock_sched.return_value
    from aeloria.app import app
    with TestClient(app):
        mock_supervise.assert_called_once()  # bot thread started
        sched.start.assert_called_once()
    sched.shutdown.assert_called_once_with(wait=False)


@patch("aeloria.app.get_settings")
@patch("aeloria.app.run_pending")
@patch("aeloria.app.build_scheduler")
@patch("aeloria.app.supervise_bot")
@patch("aeloria.app._build_runtime")
def test_health_reports_state(
    mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings
):
    _start_app(mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings)
    from aeloria.app import app
    with TestClient(app) as client:
        r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["scheduler_running"] is True
    assert body["bot_running"] is True


@patch("aeloria.app.get_settings")
@patch("aeloria.app.run_pending")
@patch("aeloria.app.build_scheduler")
@patch("aeloria.app.supervise_bot")
@patch("aeloria.app._build_runtime")
def test_trigger_run_pending_auth_and_dispatch(
    mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings
):
    _start_app(mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings)
    from aeloria.app import app
    with TestClient(app) as client:
        no_token = client.post("/trigger/run-pending")
        wrong = client.post("/trigger/run-pending", headers={"Authorization": "Bearer wrong"})
        ok = client.post("/trigger/run-pending", headers={"Authorization": "Bearer secret"})
    assert no_token.status_code == 401
    assert wrong.status_code == 401
    assert ok.status_code == 200
    assert ok.json() == {"processed": 3}
    mock_run_pending.assert_called_once()


@patch("aeloria.app.get_settings")
@patch("aeloria.app.run_pending")
@patch("aeloria.app.build_scheduler")
@patch("aeloria.app.supervise_bot")
@patch("aeloria.app._build_runtime")
def test_trigger_disabled_when_api_secret_key_empty(
    mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings
):
    mock_rt.return_value = tuple(MagicMock() for _ in range(5))
    mock_sched.return_value = MagicMock()
    settings = MagicMock()
    settings.api_secret_key = ""  # disabled
    mock_settings.return_value = settings
    from aeloria.app import app
    with TestClient(app) as client:
        r = client.post("/trigger/run-pending", headers={"Authorization": "Bearer secret"})
    assert r.status_code == 401
    mock_run_pending.assert_not_called()


@patch("aeloria.app.run_engagement_pending")
@patch("aeloria.app.get_settings")
@patch("aeloria.app.build_scheduler")
@patch("aeloria.app.supervise_bot")
@patch("aeloria.app._build_runtime")
def test_trigger_engagement_auth_and_dispatch(mock_rt, mock_sup, mock_sched, mock_settings, mock_eng):
    mock_rt.return_value = tuple(MagicMock() for _ in range(5))
    mock_sched.return_value = MagicMock()
    mock_sup.side_effect = lambda stop_event: stop_event.wait(timeout=5)
    s = MagicMock(); s.api_secret_key = "secret"; mock_settings.return_value = s
    mock_eng.return_value = 4
    from aeloria.app import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        assert client.post("/trigger/engagement").status_code == 401
        ok = client.post("/trigger/engagement", headers={"Authorization": "Bearer secret"})
        assert ok.status_code == 200 and ok.json() == {"processed": 4}


@patch("aeloria.app.run_optimizer_pending")
@patch("aeloria.app.get_settings")
@patch("aeloria.app.build_scheduler")
@patch("aeloria.app.supervise_bot")
@patch("aeloria.app._build_runtime")
def test_trigger_optimizer_auth_and_dispatch(mock_rt, mock_sup, mock_sched, mock_settings, mock_opt):
    mock_rt.return_value = tuple(MagicMock() for _ in range(5))
    mock_sched.return_value = MagicMock()
    mock_sup.side_effect = lambda stop_event: stop_event.wait(timeout=5)
    s = MagicMock(); s.api_secret_key = "secret"; mock_settings.return_value = s
    mock_opt.return_value = 1
    from aeloria.app import app
    from fastapi.testclient import TestClient
    with TestClient(app) as client:
        assert client.post("/trigger/optimizer").status_code == 401
        ok = client.post("/trigger/optimizer", headers={"Authorization": "Bearer secret"})
        assert ok.status_code == 200 and ok.json() == {"processed": 1}


def test_build_runtime_resilient_when_face_ref_missing():
    """_build_runtime must not crash when face_ref.json is absent (fresh deploy)."""
    from pathlib import Path
    import aeloria.app as appmod
    with patch("aeloria.app.Db") as MockDb, \
         patch("aeloria.app.R2") as MockR2, \
         patch("aeloria.app.load_persona", return_value=MagicMock()), \
         patch("aeloria.app.load_reference", side_effect=FileNotFoundError("no ref")):
        settings = MagicMock()
        settings.telegram_bot_token = ""
        settings.telegram_chat_id = ""
        db, r2, persona, ref, tg = appmod._build_runtime(settings)
        assert ref is None          # graceful: face gate disabled, app still boots
        assert tg is None           # telegram not configured
        MockDb.assert_called_once_with(settings)
        MockR2.assert_called_once_with(settings)


@patch("aeloria.app.get_settings")
@patch("aeloria.app.run_pending")
@patch("aeloria.app.build_scheduler")
@patch("aeloria.app.supervise_bot")
@patch("aeloria.app._build_runtime")
def test_lifespan_inits_token_store_when_credential_exists(
    mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings
):
    from aeloria.auth import token_store
    token_store._token = ""
    rt = tuple(MagicMock() for _ in range(5))
    db = rt[0]
    db.get_credential.return_value = {"access_token": "LIVE_TOKEN"}
    mock_rt.return_value = rt
    mock_sched.return_value = MagicMock()
    mock_supervise.side_effect = _blocking_supervise
    settings = MagicMock(); settings.api_secret_key = "secret"
    mock_settings.return_value = settings
    from aeloria.app import app
    with TestClient(app):
        assert token_store.get() == "LIVE_TOKEN"


@patch("aeloria.app.get_settings")
@patch("aeloria.app.run_pending")
@patch("aeloria.app.build_scheduler")
@patch("aeloria.app.supervise_bot")
@patch("aeloria.app._build_runtime")
def test_lifespan_boots_when_no_credential(
    mock_rt, mock_supervise, mock_sched, mock_run_pending, mock_settings
):
    from aeloria.auth import token_store
    token_store._token = ""
    rt = tuple(MagicMock() for _ in range(5))
    rt[0].get_credential.return_value = None  # no creds
    mock_rt.return_value = rt
    mock_sched.return_value = MagicMock()
    mock_supervise.side_effect = _blocking_supervise
    settings = MagicMock(); settings.api_secret_key = "secret"
    mock_settings.return_value = settings
    from aeloria.app import app
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200  # app boots, publishing will no-op
