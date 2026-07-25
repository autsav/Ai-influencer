from unittest.mock import MagicMock, patch

from aeloria.engagement.runner import _RUN_LOCK, run_engagement_pending


def _settings():
    s = MagicMock()
    s.meta_app_id = "APP"
    s.ig_user_id = "IG"
    return s


@patch("aeloria.engagement.runner.poll_outbound", return_value=0)
@patch("aeloria.engagement.runner.poll_dms", return_value=0)
@patch("aeloria.engagement.runner.poll_inbound", return_value=0)
@patch("aeloria.engagement.runner.send_dm", return_value="posted-dm")
@patch("aeloria.engagement.runner.reply_to_comment", return_value="posted-reply")
@patch("aeloria.engagement.runner.refresh_if_needed")
def test_posts_approved_reply_and_dm(mock_refresh, mock_reply, mock_dm, mock_pi, mock_pd, mock_po):
    approved = [
        {"id": "e1", "kind": "reply", "target": "c1", "draft": "thanks", "approval": "approved", "posted_at": None},
        {"id": "e2", "kind": "dm", "target": "u1", "draft": "hi", "approval": "approved", "posted_at": None},
        {"id": "e3", "kind": "comment_out", "target": "http://x", "draft": "nice", "approval": "approved", "posted_at": None},
    ]
    db = MagicMock()
    db.select_approved_unposted_engagements.return_value = approved
    db.select_undigested_pending_engagements.return_value = []
    n = run_engagement_pending(db, _settings(), MagicMock(), tg=MagicMock())
    assert n == 2  # reply + dm posted; comment_out is manual
    # reply/DM posted with the row's target + draft
    assert mock_reply.call_args.args[1:] == ("c1", "thanks")
    assert mock_dm.call_args.args[1:] == ("u1", "hi")
    # posted rows marked with posted_id; outbound not auto-posted
    updates = {c.args[1]: c.args[2] for c in db.update.call_args_list}
    assert "e1" in updates and updates["e1"]["posted_id"] == "posted-reply"
    assert "e2" in updates and updates["e2"]["posted_id"] == "posted-dm"
    assert "e3" not in updates


@patch("aeloria.engagement.runner.poll_outbound", return_value=0)
@patch("aeloria.engagement.runner.poll_dms", return_value=0)
@patch("aeloria.engagement.runner.poll_inbound", return_value=2)
@patch("aeloria.engagement.runner.refresh_if_needed")
def test_sends_digest_for_undigested_pending(mock_refresh, mock_pi, mock_pd, mock_po):
    db = MagicMock()
    db.select_approved_unposted_engagements.return_value = []
    pending = [
        {"id": "e1", "kind": "reply", "target": "c1", "draft": "thanks", "approval": "pending"},
        {"id": "e2", "kind": "comment_out", "target": "http://x", "draft": "nice", "approval": "pending"},
    ]
    db.select_undigested_pending_engagements.return_value = pending
    tg = MagicMock()
    run_engagement_pending(db, _settings(), MagicMock(), tg=tg)
    tg.send_message.assert_called_once()
    _, kwargs = tg.send_message.call_args
    assert kwargs.get("buttons")  # inline approve/reject buttons attached
    # each shown row gets stamped digested_at so it's never re-shown
    stamped_ids = {c.args[1] for c in db.update.call_args_list if "digested_at" in c.args[2]}
    assert stamped_ids == {"e1", "e2"}


@patch("aeloria.engagement.runner.poll_outbound", return_value=0)
@patch("aeloria.engagement.runner.poll_dms", return_value=0)
@patch("aeloria.engagement.runner.poll_inbound", return_value=0)
@patch("aeloria.engagement.runner.refresh_if_needed")
def test_idle_round_sends_nothing(mock_refresh, mock_pi, mock_pd, mock_po):
    db = MagicMock()
    db.select_approved_unposted_engagements.return_value = []
    db.select_undigested_pending_engagements.return_value = []  # backlog already digested
    tg = MagicMock()
    run_engagement_pending(db, _settings(), MagicMock(), tg=tg)
    tg.send_message.assert_not_called()


@patch("aeloria.engagement.runner.refresh_if_needed")
def test_gated_when_no_meta_creds(mock_refresh):
    s = MagicMock()
    s.meta_app_id = ""
    s.ig_user_id = ""
    db = MagicMock()
    n = run_engagement_pending(db, s, MagicMock(), tg=MagicMock())
    assert n == 0


@patch("aeloria.engagement.runner.poll_outbound", return_value=0)
@patch("aeloria.engagement.runner.poll_dms", return_value=0)
@patch("aeloria.engagement.runner.poll_inbound", return_value=0)
@patch("aeloria.engagement.runner.refresh_if_needed")
def test_run_serializes_on_module_lock(mock_refresh, mock_pi, mock_pd, mock_po):
    """run_engagement_pending must hold _RUN_LOCK for its duration so the
    scheduler job and the manual /trigger/engagement endpoint can't post the
    same approved row concurrently."""
    db = MagicMock()
    db.select_approved_unposted_engagements.return_value = []
    db.select_undigested_pending_engagements.return_value = []
    seen_locked = []

    def fake_refresh(*a, **k):
        seen_locked.append(_RUN_LOCK.locked())

    mock_refresh.side_effect = fake_refresh
    assert not _RUN_LOCK.locked()
    run_engagement_pending(db, _settings(), MagicMock(), tg=MagicMock())
    assert seen_locked == [True]  # lock was held while the run's body executed
    assert not _RUN_LOCK.locked()  # released after the run completes
