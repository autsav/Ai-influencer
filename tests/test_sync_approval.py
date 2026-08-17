"""Smoke tests for sync_approval.

Verifies:
- import
- is_telegram_configured() runs without raising
- send_for_approval is callable (does NOT actually send — only validates wiring)
"""

from aeloria.approval.sync_approval import (
    send_for_approval,
    is_telegram_configured,
)


def test_sync_approval_imports():
    assert callable(send_for_approval)
    assert callable(is_telegram_configured)


def test_is_telegram_configured_returns_bool():
    result = is_telegram_configured()
    assert isinstance(result, bool)


def test_send_for_approval_signature():
    import inspect
    sig = inspect.signature(send_for_approval)
    params = list(sig.parameters.keys())
    # Required bits: tg bot, chat_id, image_bytes, caption
    assert "chat_id" in params
    assert "image_bytes" in params
    assert "caption" in params