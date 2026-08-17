"""End-to-end tests for the newsletter API endpoints.

Uses FastAPI's TestClient with a mock DB injected via the app's
`state.db`. We don't run the lifespan (so we don't need a real Settings
or a Telegram bot thread); instead we construct a minimal FastAPI app
that mirrors the production /api/v1 mount and attach a MagicMock db.
"""
from unittest.mock import MagicMock

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from aeloria.api.v1.endpoints import newsletter as nl_endpoint
from aeloria.schemas.newsletter import (
    GenericActionResponse, SubscribeResponse,
)


def _make_app(db: MagicMock, base_url: str = "https://aeloria.ai") -> FastAPI:
    """Build a minimal FastAPI app mirroring the production /api/v1 mount.

    The routes are attached directly to a parent APIRouter with the
    /api/v1 prefix — the same effect as nesting the inner router under
    it in production, but without the Starlette nested-router quirk
    where the parent prefix occasionally doesn't propagate through
    include_router in tests."""
    settings = MagicMock()
    settings.newsletter_base_url = base_url
    settings.newsletter_send_batch_cap = 500
    nl_endpoint.get_settings = lambda: settings  # type: ignore[assignment]

    app = FastAPI()
    parent = APIRouter(prefix="/api/v1")
    parent.post("/newsletter/subscribe", response_model=SubscribeResponse)(
        nl_endpoint.subscribe_endpoint
    )
    parent.get("/newsletter/confirm", response_model=GenericActionResponse)(
        nl_endpoint.confirm_endpoint
    )
    parent.get("/newsletter/unsubscribe", response_model=GenericActionResponse)(
        nl_endpoint.unsubscribe_endpoint
    )
    app.include_router(parent)
    app.state.db = db
    app.state.settings = settings
    return app


def _make_db(*, existing=None, insert_returns=None, update_returns=None):
    db = MagicMock()
    db.select.return_value = existing or []
    db.insert.return_value = insert_returns or {"id": "sub_1"}
    db.update.return_value = update_returns or {"id": "sub_1"}
    return db


# ── POST /api/v1/newsletter/subscribe ─────────────────────────────────────────

class TestSubscribeEndpoint:
    def test_new_email_returns_ok(self):
        db = _make_db(existing=[])
        app = _make_app(db)
        client = TestClient(app)
        r = client.post("/api/v1/newsletter/subscribe", json={
            "email": "Foo@Bar.com",
            "source": "instagram_bio",
            "referrer": "post_42",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["already_subscribed"] is False
        assert "token=" in body["confirm_url"]
        # Email normalized to lowercase before insert.
        inserted = db.insert.call_args[0][1]
        assert inserted["email"] == "foo@bar.com"
        assert inserted["source"] == "instagram_bio"
        assert inserted["referrer"] == "post_42"

    def test_existing_email_returns_already_subscribed(self):
        db = _make_db(existing=[{
            "id": "sub_1", "email": "a@b.com",
            "status": "pending", "confirm_token": "tok_existing",
        }])
        app = _make_app(db)
        client = TestClient(app)
        r = client.post("/api/v1/newsletter/subscribe", json={"email": "a@b.com"})
        assert r.status_code == 200
        body = r.json()
        assert body["already_subscribed"] is True
        assert "tok_existing" in body["confirm_url"]

    def test_invalid_email_returns_422(self):
        db = _make_db()
        app = _make_app(db)
        client = TestClient(app)
        r = client.post("/api/v1/newsletter/subscribe", json={"email": "not-an-email"})
        # Pydantic field_validator rejects it before our handler runs.
        assert r.status_code == 422

    def test_missing_email_returns_422(self):
        db = _make_db()
        app = _make_app(db)
        client = TestClient(app)
        r = client.post("/api/v1/newsletter/subscribe", json={"source": "direct"})
        assert r.status_code == 422

    def test_default_source_is_direct(self):
        db = _make_db(existing=[])
        app = _make_app(db)
        client = TestClient(app)
        r = client.post("/api/v1/newsletter/subscribe", json={"email": "a@b.com"})
        assert r.status_code == 200
        inserted = db.insert.call_args[0][1]
        assert inserted["source"] == "direct"

    def test_invalid_source_returns_422(self):
        db = _make_db()
        app = _make_app(db)
        client = TestClient(app)
        r = client.post("/api/v1/newsletter/subscribe", json={
            "email": "a@b.com", "source": "bogus_source",
        })
        assert r.status_code == 422


# ── GET /api/v1/newsletter/confirm ────────────────────────────────────────────

class TestConfirmEndpoint:
    def test_valid_token_returns_ok(self):
        db = _make_db(existing=[{
            "id": "sub_1", "email": "a@b.com", "status": "pending",
            "confirm_token": "tok_xyz",
        }])
        app = _make_app(db)
        client = TestClient(app)
        r = client.get("/api/v1/newsletter/confirm", params={"token": "tok_xyz"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["email"] == "a@b.com"

    def test_unknown_token_returns_error_not_404(self):
        """We must NEVER 404 on confirm — that would let a probe enumerate
        token values. The endpoint always returns 200 with status='error'."""
        db = _make_db(existing=[])
        app = _make_app(db)
        client = TestClient(app)
        r = client.get("/api/v1/newsletter/confirm", params={"token": "tok_bogus"})
        assert r.status_code == 200
        assert r.json()["status"] == "error"

    def test_missing_token_returns_422(self):
        db = _make_db()
        app = _make_app(db)
        client = TestClient(app)
        r = client.get("/api/v1/newsletter/confirm")
        # FastAPI Query(...) without a default requires the param.
        assert r.status_code == 422


# ── GET /api/v1/newsletter/unsubscribe ────────────────────────────────────────

class TestUnsubscribeEndpoint:
    def test_valid_token_returns_ok(self):
        db = _make_db(existing=[{
            "id": "sub_1", "email": "a@b.com", "status": "active",
            "confirm_token": "tok_unsub",
        }])
        app = _make_app(db)
        client = TestClient(app)
        r = client.get("/api/v1/newsletter/unsubscribe", params={"token": "tok_unsub"})
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        # RFC 8058 / CAN-SPAM: never echo the email on unsubscribe —
        # otherwise a probe could enumerate who's subscribed by trying
        # tokens until the email field appears.
        assert body["email"] is None

    def test_unknown_token_returns_200_anyway(self):
        """Per RFC 8058 + Gmail one-click unsubscribe rules, unsubscribe
        must always return 200 with a generic success message, regardless
        of token validity. A 404 here makes Gmail's unsubscribe checker
        report 'unsubscribe failed' and start offering 'Report spam'."""
        db = _make_db(existing=[])
        app = _make_app(db)
        client = TestClient(app)
        r = client.get("/api/v1/newsletter/unsubscribe", params={"token": "bogus"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_already_unsubscribed_returns_200(self):
        db = _make_db(existing=[{
            "id": "sub_1", "email": "a@b.com", "status": "unsubscribed",
            "confirm_token": "tok_already",
        }])
        app = _make_app(db)
        client = TestClient(app)
        r = client.get("/api/v1/newsletter/unsubscribe", params={"token": "tok_already"})
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
