"""Tests for aeloria.publishing.meta._get_token() helper.

Added 2026-08-17: covers the IG_ACCESS_TOKEN / META_LONG_LIVED_TOKEN env-var
fallback chain when Supabase token_store is unreachable.
"""
import os
from unittest.mock import patch

import pytest

from aeloria.publishing import meta


@pytest.fixture
def clean_env(monkeypatch):
    """Strip any pre-existing IG token env vars so tests are deterministic."""
    for var in ("IG_ACCESS_TOKEN", "META_LONG_LIVED_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_get_token_raises_when_no_token_available(clean_env):
    """No token_store + no env vars = RuntimeError with helpful message."""
    with patch("aeloria.publishing.meta.token_store") as mock_store:
        # token_store.get raises RuntimeError when uninitialized
        mock_store.get.side_effect = RuntimeError("token_store not initialized")
        with pytest.raises(RuntimeError) as exc_info:
            meta._get_token()
    msg = str(exc_info.value)
    assert "IG_ACCESS_TOKEN" in msg
    assert "token_store" in msg


def test_get_token_falls_back_to_ig_access_token_env(clean_env):
    """IG_ACCESS_TOKEN env var used when token_store raises."""
    clean_env.setenv("IG_ACCESS_TOKEN", "test_token_abc")
    with patch("aeloria.publishing.meta.token_store") as mock_store:
        mock_store.get.side_effect = RuntimeError("not initialized")
        tok = meta._get_token()
    assert tok == "test_token_abc"


def test_get_token_falls_back_to_meta_long_lived_token(clean_env):
    """META_LONG_LIVED_TOKEN env var used when IG_ACCESS_TOKEN unset."""
    clean_env.setenv("META_LONG_LIVED_TOKEN", "legacy_token_xyz")
    with patch("aeloria.publishing.meta.token_store") as mock_store:
        mock_store.get.side_effect = RuntimeError("not initialized")
        tok = meta._get_token()
    assert tok == "legacy_token_xyz"


def test_get_token_prefers_ig_access_token_over_meta_long_lived(clean_env):
    """Both env vars set → IG_ACCESS_TOKEN wins (more specific)."""
    clean_env.setenv("IG_ACCESS_TOKEN", "primary_token")
    clean_env.setenv("META_LONG_LIVED_TOKEN", "legacy_token")
    with patch("aeloria.publishing.meta.token_store") as mock_store:
        mock_store.get.side_effect = RuntimeError("not initialized")
        tok = meta._get_token()
    assert tok == "primary_token"


def test_get_token_uses_token_store_first_when_available(clean_env):
    """token_store path takes priority over env vars."""
    clean_env.setenv("IG_ACCESS_TOKEN", "env_token")
    with patch("aeloria.publishing.meta.token_store") as mock_store:
        mock_store.get.return_value = "store_token"
        tok = meta._get_token()
    assert tok == "store_token"


def test_get_token_skips_empty_env_var(clean_env):
    """Empty/whitespace env var should fall through to next option."""
    clean_env.setenv("IG_ACCESS_TOKEN", "   ")
    clean_env.setenv("META_LONG_LIVED_TOKEN", "real_token")
    with patch("aeloria.publishing.meta.token_store") as mock_store:
        mock_store.get.side_effect = RuntimeError("not initialized")
        tok = meta._get_token()
    assert tok == "real_token"


def test_get_token_does_not_swallow_token_store_value_when_truthy(clean_env):
    """If token_store returns empty string, fall back to env."""
    clean_env.setenv("META_LONG_LIVED_TOKEN", "env_token")
    with patch("aeloria.publishing.meta.token_store") as mock_store:
        mock_store.get.return_value = ""  # empty string is falsy
        tok = meta._get_token()
    assert tok == "env_token"