"""Tests for newsletter sender + signup flow + scheduled runner."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from aeloria.distribution.newsletter_runner import (
    _issue_slug, _select_weekly_posts, run_newsletter_pending,
    has_newsletter_run_today,
)
from aeloria.distribution.newsletter_sender import (
    IssueContent, NewsletterError, ResendClient, confirm, queue_issue,
    send_due_with_issue, subscribe, unsubscribe,
)


# ── Subscribe / confirm / unsubscribe ─────────────────────────────────────────

class TestSubscribe:
    def _make_db(self, existing=None):
        db = MagicMock()
        db.select.return_value = existing or []
        db.insert.return_value = {"id": "sub_1", "email": "a@b.com"}
        db.update.return_value = {"id": "sub_1"}
        return db

    def _settings(self):
        s = MagicMock()
        s.newsletter_send_batch_cap = 500
        return s

    def test_new_email_inserts_pending(self):
        db = self._make_db()
        result = subscribe(db, self._settings(), email="  Foo@Bar.com  ")
        assert result.already_subscribed is False
        assert result.email == "foo@bar.com"
        # confirm_token is a 32-byte urlsafe token (~43 chars)
        assert len(result.confirm_token) > 30
        inserted = db.insert.call_args[0][1]
        assert inserted["status"] == "pending"
        assert inserted["email"] == "foo@bar.com"

    def test_invalid_email_raises(self):
        db = self._make_db()
        with pytest.raises(NewsletterError):
            subscribe(db, self._settings(), email="not-an-email")

    def test_existing_pending_returns_already_subscribed(self):
        db = self._make_db(existing=[{
            "id": "sub_1", "email": "a@b.com",
            "status": "pending", "confirm_token": "tok_pending",
        }])
        result = subscribe(db, self._settings(), email="a@b.com")
        assert result.already_subscribed is True
        assert result.confirm_token == "tok_pending"
        db.insert.assert_not_called()  # don't churn pending state

    def test_existing_active_returns_already_subscribed(self):
        db = self._make_db(existing=[{
            "id": "sub_1", "email": "a@b.com",
            "status": "active", "confirm_token": "tok_active",
        }])
        result = subscribe(db, self._settings(), email="a@b.com")
        assert result.already_subscribed is True
        db.insert.assert_not_called()

    def test_resubscribe_after_unsubscribe(self):
        db = self._make_db(existing=[{
            "id": "sub_1", "email": "a@b.com",
            "status": "unsubscribed", "confirm_token": "old_tok",
        }])
        result = subscribe(
            db, self._settings(),
            email="a@b.com", source="instagram_bio", referrer="post_42",
        )
        assert result.already_subscribed is False
        # db.update is called positionally as (table, row_id, fields_dict).
        fields = db.update.call_args[0][2]
        assert fields["status"] == "pending"
        assert fields["source"] == "instagram_bio"
        assert fields["referrer"] == "post_42"
        assert fields["unsubscribed_at"] is None


class TestConfirm:
    def _db(self, rows):
        db = MagicMock()
        db.select.return_value = rows
        return db

    def test_confirm_pending_to_active(self):
        db = self._db([{"id": "s1", "email": "a@b.com", "status": "pending"}])
        assert confirm(db, "tok") == "a@b.com"
        fields = db.update.call_args[0][2]
        assert fields["status"] == "active"
        assert "confirmed_at" in fields

    def test_confirm_active_idempotent(self):
        db = self._db([{"id": "s1", "email": "a@b.com", "status": "active"}])
        assert confirm(db, "tok") == "a@b.com"
        db.update.assert_not_called()

    def test_confirm_unknown_token_returns_none(self):
        db = self._db([])
        assert confirm(db, "tok") is None


class TestUnsubscribe:
    def _db(self, rows):
        db = MagicMock()
        db.select.return_value = rows
        return db

    def test_unsubscribe_pending(self):
        db = self._db([{"id": "s1", "status": "pending"}])
        assert unsubscribe(db, "tok") is True
        fields = db.update.call_args[0][2]
        assert fields["status"] == "unsubscribed"

    def test_unsubscribe_idempotent(self):
        db = self._db([{"id": "s1", "status": "unsubscribed"}])
        assert unsubscribe(db, "tok") is False
        db.update.assert_not_called()

    def test_unsubscribe_unknown_token(self):
        db = self._db([])
        assert unsubscribe(db, "tok") is False


# ── ResendClient + send_due_with_issue ────────────────────────────────────────

class TestResendClient:
    def test_disabled_without_token(self):
        c = ResendClient(token="")
        assert c.enabled is False

    def test_send_email_returns_message_id(self):
        c = ResendClient(token="re_fake")
        fake_response = MagicMock(status_code=200)
        fake_response.json.return_value = {"id": "msg_abc123"}
        with patch("aeloria.distribution.newsletter_sender.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = fake_response
            mid = c.send_email(
                from_addr="A <hello@x.com>", to=["a@b.com"],
                subject="hi", html="<p>hi</p>", text="hi",
            )
        assert mid == "msg_abc123"

    def test_send_email_raises_on_4xx(self):
        c = ResendClient(token="re_fake")
        fake_response = MagicMock(status_code=422)
        fake_response.text = "validation failed"
        with patch("aeloria.distribution.newsletter_sender.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = fake_response
            with pytest.raises(NewsletterError):
                c.send_email(
                    from_addr="x", to=["a@b.com"], subject="hi",
                    html="<p>x</p>", text="x",
                )


def _make_send_db(*, queued_rows, subscribers):
    """Build a db mock that responds to the specific calls send_due_with_issue
    makes: table('newsletter_sends').select().eq().eq()... and
    table('newsletter_subscribers').select().eq().limit().execute()."""
    db = MagicMock()
    # Build the chained mock for newsletter_sends
    sends_table = db._client.table.return_value
    sends_select = sends_table.select.return_value
    sends_eq_status = sends_select.eq.return_value
    sends_eq_issue = sends_eq_status.eq.return_value
    sends_eq_issue.order.return_value.limit.return_value.execute.return_value.data = queued_rows

    # The subscriber lookup chains differently per row — rebuild per call.
    def fake_table(name):
        m = MagicMock()
        if name == "newsletter_subscribers":
            m.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = subscribers
        elif name == "newsletter_sends":
            m.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = queued_rows
            # Also support single-eq chain (used in some paths)
            m.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = queued_rows
        return m
    db._client.table.side_effect = fake_table
    return db


class TestSendDueWithIssue:
    def test_no_queued_sends_returns_zero(self):
        db = _make_send_db(queued_rows=[], subscribers=[])
        client = ResendClient(token="re_x")
        issue = IssueContent(issue_slug="2026-08-17-w34", subject="Hi",
                             html_body="<p>{{UNSUBSCRIBE_URL}}</p>",
                             text_body="{{UNSUBSCRIBE_URL}}")
        assert send_due_with_issue(db, MagicMock(), issue, client=client) == 0

    def test_substitutes_unsubscribe_url(self):
        sent_payloads = []
        client = MagicMock(spec=ResendClient)
        client.enabled = True
        client.send_email.side_effect = lambda **kw: sent_payloads.append(kw) or "msg_1"

        db = MagicMock()
        def fake_table(name):
            m = MagicMock()
            if name == "newsletter_subscribers":
                m.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
                    {"id": "sub_1", "email": "a@b.com", "status": "active", "confirm_token": "tok_x"}
                ]
            else:
                m.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
                    {"id": "send_1", "subscriber_id": "sub_1", "subject": "Hi", "issue_slug": "s"}
                ]
            return m
        db._client.table.side_effect = fake_table

        issue = IssueContent(issue_slug="s", subject="Hi",
                             html_body="<p>before {{UNSUBSCRIBE_URL}} after</p>",
                             text_body="before {{UNSUBSCRIBE_URL}} after")
        n = send_due_with_issue(db, MagicMock(), issue, client=client)
        assert n == 1
        assert len(sent_payloads) == 1
        sent = sent_payloads[0]
        assert "{{UNSUBSCRIBE_URL}}" not in sent["html"]
        assert "tok_x" in sent["html"]
        assert "List-Unsubscribe" in sent["headers"]


# ── Runner ────────────────────────────────────────────────────────────────────

class TestIssueSlug:
    def test_format(self):
        # 2026-08-17 is a Monday, ISO week 34
        d = datetime(2026, 8, 17, 9, 0, tzinfo=timezone.utc)
        assert _issue_slug(d) == "2026-08-17-w34"


class TestRunnerGate:
    def test_skips_when_wrong_weekday(self):
        db = MagicMock()
        s = MagicMock()
        s.newsletter_send_weekday = 0   # Monday
        s.newsletter_send_hour_utc = 9
        # 2026-08-19 = Wednesday
        wed = datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc)
        assert run_newsletter_pending(db, s, MagicMock(), now=wed) == 0

    def test_skips_when_too_early(self):
        db = MagicMock()
        s = MagicMock()
        s.newsletter_send_weekday = 0
        s.newsletter_send_hour_utc = 9
        # Monday 08:00 UTC — before the 09:00 gate
        mon_am = datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc)
        assert run_newsletter_pending(db, s, MagicMock(), now=mon_am) == 0


class TestHasNewsletterRunToday:
    def test_returns_true_when_sent_exists(self):
        db = MagicMock()
        db._client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = [{"id": "x"}]
        assert has_newsletter_run_today(db) is True

    def test_returns_false_when_empty(self):
        db = MagicMock()
        db._client.table.return_value.select.return_value.eq.return_value.eq.return_value.limit.return_value.execute.return_value.data = []
        assert has_newsletter_run_today(db) is False
