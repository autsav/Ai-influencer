"""Tests for aeloria.engagement.reengagement_cron."""
from unittest.mock import MagicMock, patch

import pytest

from aeloria.engagement.reengagement_cron import ReengagementCron


class TestReengagementCron:
    def test_run_noop_when_no_fanvue_key(self, monkeypatch):
        """No fanvue key → _fanvue_send returns False, counted as error (not crash)."""
        monkeypatch.setenv("FANVUE_API_KEY", "")

        mock_fan = {"id": "f1", "username": "alice", "preferred_topics": ["wellness"]}
        with patch.object(ReengagementCron, "_find_inactive_fans", return_value=[mock_fan]):
            with patch.object(ReengagementCron, "_get_last_conversation", return_value=None):
                cron = ReengagementCron()
                result = cron.run()

        assert result["errors"] == 1
        assert result["nudged"] == 0

    def test_run_respects_daily_cap(self, monkeypatch):
        """Only daily_cap fans are processed."""
        monkeypatch.setenv("FANVUE_API_KEY", "fake-key")
        mock_fans = [
            {"id": f"f{i}", "username": f"user{i}", "preferred_topics": []}
            for i in range(3)
        ]
        with patch.object(ReengagementCron, "_find_inactive_fans", return_value=mock_fans):
            with patch.object(ReengagementCron, "_get_last_conversation", return_value=None):
                with patch.object(ReengagementCron, "_fanvue_send", return_value=True):
                    cron = ReengagementCron()
                    result = cron.run()

        assert result["nudged"] == 3

    def test_run_result_shape(self, monkeypatch):
        """run() returns dict with nudged/skipped/errors keys."""
        monkeypatch.setenv("FANVUE_API_KEY", "")
        with patch.object(ReengagementCron, "_find_inactive_fans", return_value=[]):
            cron = ReengagementCron()
            result = cron.run()

        assert "nudged" in result
        assert "skipped" in result
        assert "errors" in result

    def test_build_nudge_with_last_convo(self):
        """_build_nudge includes conversation fragment when last_convo is present."""
        cron = ReengagementCron.__new__(ReengagementCron)
        fan = {"username": "alice", "preferred_topics": ["yoga"]}
        last_convo = {"content": "I love your yoga tips!"}
        nudge = cron._build_nudge(fan, last_convo)
        assert "alice" in nudge
        assert "yoga" in nudge

    def test_build_nudge_no_convo(self):
        """_build_nudge falls back to generic nudge when no prior conversation."""
        cron = ReengagementCron.__new__(ReengagementCron)
        fan = {"username": "bob", "preferred_topics": []}
        nudge = cron._build_nudge(fan, None)
        assert "bob" in nudge
        assert "wellness" in nudge  # default topic

    def test_fanvue_send_noop_without_key(self, monkeypatch):
        """_fanvue_send returns False when key is empty."""
        monkeypatch.setenv("FANVUE_API_KEY", "")
        cron = ReengagementCron()
        result = cron._fanvue_send("f1", "hello")
        assert result is False
