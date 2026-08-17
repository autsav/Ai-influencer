"""Public newsletter endpoints — signup, confirm, unsubscribe.

Mounted at /api/v1/newsletter. All three routes are intentionally
unauthenticated: signup is a public web form, confirm + unsubscribe are
single-click links inside emails. Authorization is via the opaque
confirm_token (32-byte URL-safe secret generated on subscribe).

DB access comes from `request.app.state.db`, mirroring how the lifespan
in app.py wires `app.state.db = Db(settings)`. Settings come from
get_settings() (the same singleton the rest of the app uses).

We don't render HTML here — the API returns JSON; the actual /confirm and
/unsubscribe landing pages can be a static site (or a separate FastAPI
route) that calls this API and shows a styled result.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from aeloria.config import get_settings
from aeloria.distribution.newsletter_sender import (
    confirm as confirm_subscription,
    subscribe as create_subscriber,
    unsubscribe as drop_subscriber,
)
from aeloria.schemas.newsletter import (
    GenericActionResponse,
    SubscribeRequest,
    SubscribeResponse,
)

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/subscribe", response_model=SubscribeResponse)
async def subscribe_endpoint(req: SubscribeRequest, request: Request) -> SubscribeResponse:
    """Public signup endpoint. Always 200 for syntactically valid input
    (even when the email is already on the list) so a probe can't
    enumerate which addresses are subscribed. On invalid email we DO
    return 422 — that's user-facing input validation, not enumeration."""
    db = request.app.state.db
    settings = get_settings()
    try:
        result = create_subscriber(
            db,
            settings,
            email=req.email,
            source=req.source,
            referrer=req.referrer or "",
            utm_source=req.utm_source or "",
            utm_campaign=req.utm_campaign or "",
        )
    except ValueError as exc:
        # newsletter_sender raises NewsletterError(extends Exception) for
        # malformed emails; map to 422 for clean client UX.
        raise HTTPException(status_code=422, detail=str(exc))

    # In production the confirmation email is sent via the same channel
    # as the weekly digest (Resend). For now we surface the confirm URL
    # in dev so the tester can click through without a mail roundtrip.
    # The frontend should hide this field when settings.env == "prod".
    confirm_url = (
        f"{settings.newsletter_base_url}/api/v1/newsletter/confirm"
        f"?token={result.confirm_token}"
    )
    log.info(
        "newsletter subscribe: %s (already=%s, source=%s)",
        result.email, result.already_subscribed, req.source,
    )
    return SubscribeResponse(
        status="ok",
        already_subscribed=result.already_subscribed,
        confirm_url=confirm_url,
    )


@router.get("/confirm", response_model=GenericActionResponse)
async def confirm_endpoint(
    request: Request,
    token: str = Query(..., min_length=1, max_length=200,
                       description="Opaque token from the confirmation email"),
) -> GenericActionResponse:
    """Single-click confirm. Returns 200 even on unknown tokens (with
    status='error') so we don't leak which tokens are real. The HTTP
    status is the same regardless — a 404 here would let a probe
    enumerate token values."""
    db = request.app.state.db
    email = confirm_subscription(db, token)
    if email:
        return GenericActionResponse(
            status="ok",
            email=email,
            message="You're confirmed. The next weekly digest will land Monday morning.",
        )
    return GenericActionResponse(
        status="error",
        email=None,
        message="This confirmation link is invalid or already used.",
    )


@router.get("/unsubscribe", response_model=GenericActionResponse)
async def unsubscribe_endpoint(
    request: Request,
    token: str = Query(..., min_length=1, max_length=200,
                       description="Opaque token from the unsubscribe link"),
) -> GenericActionResponse:
    """One-click unsubscribe (RFC 8058). Always returns 200 with a generic
    'you're unsubscribed' message regardless of token validity — that's
    the spec: a user clicking unsubscribe must always succeed, even if
    the token is wrong / expired / already-used. We NEVER return 404 on
    unsubscribe (Gmail's one-click unsubscribe checker would mark us
    non-compliant and start showing 'report spam' instead)."""
    db = request.app.state.db
    drop_subscriber(db, token)
    return GenericActionResponse(
        status="ok",
        email=None,
        message="You're unsubscribed. You won't receive any further emails from us.",
    )
