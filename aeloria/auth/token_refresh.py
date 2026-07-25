"""Meta long-lived token auto-refresh. Called at the top of each publish cycle;
cheap no-op unless the token is within 10 days of expiry."""
import datetime
from datetime import timezone
import logging

import httpx

from aeloria.auth import token_store
from aeloria.redact import redact

log = logging.getLogger(__name__)


def refresh_if_needed(db, settings, tg) -> None:
    try:
        cred = db.get_credential("instagram")
    except Exception as e:
        log.error(f"[token_refresh] get_credential failed: {e}")
        if tg:
            tg.send_message(f"⚠️ token_refresh: get_credential failed: {redact(str(e))}")
        return

    if not cred:
        log.warning("[token_refresh] no instagram credential — publishing disabled")
        if tg:
            tg.send_message("⚠️ no Meta credentials — publishing disabled")
        return

    expires_at = cred.get("expires_at")
    if not expires_at:
        log.info("[token_refresh] token has no expiry (non-expiring) — skip")
        return

    exp = datetime.datetime.fromisoformat(expires_at)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    days_left = (exp - datetime.datetime.now(timezone.utc)).days
    log.info(f"[token_refresh] token expires in {days_left} days")
    if days_left > 10:
        return

    log.warning(f"[token_refresh] {days_left} days left — refreshing")
    try:
        with httpx.Client(timeout=30) as c:
            r = c.get(
                f"{settings.graph_base}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.meta_app_id,
                    "client_secret": settings.meta_app_secret,
                    "fb_exchange_token": cred["access_token"],
                },
            )
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        log.error(f"[token_refresh] refresh HTTP failed: {e}")
        if tg:
            tg.send_message(f"⚠️ Meta token refresh failed: {redact(str(e))}")
        return

    new_token = data["access_token"]
    ttl = data.get("expires_in", 60 * 24 * 3600)
    new_expiry = datetime.datetime.now(timezone.utc) + datetime.timedelta(seconds=ttl)

    try:
        token_store.update(new_token)
        db.update_credential_token("instagram", new_token, new_expiry.isoformat())
        log.info(f"[token_refresh] refreshed — valid until {new_expiry.date()}")
        if tg:
            tg.send_message(f"Meta token refreshed — valid until {new_expiry.date()}")
    except Exception as e:
        log.error(f"[token_refresh] persist failed: {redact(str(e))}")
        if tg:
            tg.send_message(f"⚠️ Meta token persist failed: {redact(str(e))}")
        return