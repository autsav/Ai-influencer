"""Tests for aeloria.engagement.dm_orchestrator."""
import pytest

from aeloria.engagement.dm_orchestrator import DMOrchestrator, FanProfile


class TestFanProfile:
    def test_fan_profile_defaults(self):
        fan = FanProfile(fan_id="uid-123", username="john_fan")
        assert fan.subscription_tier == "free"
        assert fan.purchased_ppvs == []
        assert fan.engagement_score == 0.5


class TestDMOrchestrator:
    def test_noop_when_no_api_keys(self, monkeypatch):
        """All API keys absent → process_inbound returns empty stats, no crash."""
        for key in ("ANTHROPIC_API_KEY", "FANVUE_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"):
            monkeypatch.delenv(key, raising=False)
        from aeloria.config import get_settings
        orch = DMOrchestrator(get_settings())
        result = orch.process_inbound()
        assert "processed" in result

    def test_fanvue_get_dms_no_key(self, monkeypatch):
        """No Fanvue key → returns empty list, no exception."""
        monkeypatch.setenv("FANVUE_API_KEY", "")
        from aeloria.config import get_settings
        orch = DMOrchestrator(get_settings())
        assert orch._fanvue_get_dms() == []

    def test_fanvue_send_no_key(self, monkeypatch):
        monkeypatch.setenv("FANVUE_API_KEY", "")
        from aeloria.config import get_settings
        orch = DMOrchestrator(get_settings())
        assert orch._fanvue_send("fan-uid", "hello") is False

    def test_supabase_query_no_creds(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
        from aeloria.config import get_settings
        orch = DMOrchestrator(get_settings())
        assert orch._supabase_query("fans") == []

    def test_fallback_response_when_no_anthropic_key(self, monkeypatch):
        """No Anthropic key → uses rule-based fallback."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("FANVUE_API_KEY", "")
        monkeypatch.setenv("SUPABASE_URL", "")
        monkeypatch.setenv("SUPABASE_SERVICE_KEY", "")
        from aeloria.config import get_settings
        orch = DMOrchestrator(get_settings())
        fan = FanProfile(fan_id="x", username="test")
        reply = orch._generate_response(fan, "hi aeloria!")
        assert isinstance(reply, str)
        assert len(reply) > 0
