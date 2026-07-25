from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import httpx

from aeloria.publishing import runner


def _settings(**over):
    s = MagicMock()
    s.meta_app_id = "APP"
    s.ig_user_id = "IGID"
    s.graph_base = "https://graph.facebook.com/v23.0"
    s.publish_jitter_minutes = 0  # deterministic in tests
    s.min_followers_for_stories = 5000
    s.publish_dry_run = False
    for k, v in over.items():
        setattr(s, k, v)
    return s


_KIND = {"a1": "image", "a-reel": "image", "a-story": "image"}
_SLOT = {"b1": "static", "b-reel": "reel", "b-story": "story"}


def _past_row(qid="q1", slot_type="static", kind="image", asset_id="a1", brief_id="b1"):
    return {
        "id": qid, "asset_id": asset_id, "brief_id": brief_id, "caption": "cap",
        "slot_time": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    }


def _mock_db(rows, follower_count=0):
    db = MagicMock()
    db.select_due_for_publish.return_value = rows
    db.current_follower_count.return_value = follower_count
    def _select(table, filters=None, limit=100):
        if table == "media_assets":
            return [{"id": filters["id"], "kind": _KIND.get(filters["id"], "image"),
                     "r2_url": "https://r2/x.png"}]
        if table == "briefs":
            return [{"id": filters["id"], "slot_type": _SLOT.get(filters["id"], "static")}]
        return []
    db.select.side_effect = _select
    db.insert.return_value = {"id": "post-1"}
    return db


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image", return_value=("CID", "MID"))
def test_static_publishes_and_inserts_post(mock_img, mock_ref):
    db = _mock_db([_past_row()])
    n = runner.publish_pending(db, _settings(), MagicMock())
    assert n == 1
    db.insert.assert_called_once()
    args = db.insert.call_args
    assert args.args[0] == "posts"
    assert args.args[1]["platform_post_id"] == "MID"
    assert args.args[1]["platform"] == "instagram"


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image", return_value=("CID", "MID"))
def test_idempotent_row_with_existing_posts_skipped(mock_img, mock_ref):
    # select_due_for_publish already excludes posted rows; simulate empty list
    db = _mock_db([])
    n = runner.publish_pending(db, _settings(), MagicMock())
    assert n == 0
    db.insert.assert_not_called()


@patch("aeloria.publishing.runner.refresh_if_needed")
def test_reel_with_image_asset_skipped_dormant(mock_ref):
    db = _mock_db([_past_row(qid="q2", asset_id="a-reel", brief_id="b-reel")])
    with patch("aeloria.publishing.runner.meta.publish_reel") as mock_reel:
        n = runner.publish_pending(db, _settings(), MagicMock())
        assert n == 0
        mock_reel.assert_not_called()  # skipped because kind != video


@patch("aeloria.publishing.runner.refresh_if_needed")
def test_story_below_threshold_skipped(mock_ref):
    db = _mock_db([_past_row(qid="q3", asset_id="a-story", brief_id="b-story")], follower_count=100)
    with patch("aeloria.publishing.runner.meta.publish_story") as mock_story:
        n = runner.publish_pending(db, _settings(), MagicMock())
        assert n == 0
        mock_story.assert_not_called()


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_story", return_value=("CID", "MID"))
def test_story_above_threshold_publishes(mock_story, mock_ref):
    db = _mock_db([_past_row(qid="q3", asset_id="a-story", brief_id="b-story")], follower_count=6000)
    n = runner.publish_pending(db, _settings(), MagicMock())
    assert n == 1


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image")
def test_400_marks_queue_skipped_and_alerts(mock_img, mock_ref):
    err = httpx.HTTPStatusError("policy", request=MagicMock(),
                                response=MagicMock(status_code=400, text="bad content"))
    mock_img.side_effect = err
    db = _mock_db([_past_row()])
    tg = MagicMock()
    n = runner.publish_pending(db, _settings(), tg)
    assert n == 0
    db.update.assert_called_once()
    uargs = db.update.call_args
    assert uargs.args[0] == "queue"
    assert uargs.args[2]["approval"] == "skipped"
    assert uargs.args[2]["reject_reason"].startswith("meta_400")
    tg.send_message.assert_called()


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image")
def test_401_refreshes_and_retries_once(mock_img, mock_ref):
    err = httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock(status_code=401))
    mock_img.side_effect = [err, ("CID", "MID2")]  # first 401, retry succeeds
    db = _mock_db([_past_row()])
    n = runner.publish_pending(db, _settings(), MagicMock())
    assert n == 1
    assert mock_img.call_count == 2
    assert mock_ref.call_count == 2  # initial + the 401 refresh


@patch("aeloria.publishing.runner.refresh_if_needed")
def test_dry_run_skips_meta_and_inserts_dry_run_post(mock_ref):
    db = _mock_db([_past_row()])
    with patch("aeloria.publishing.runner.meta.publish_image") as mock_img:
        n = runner.publish_pending(db, _settings(publish_dry_run=True), MagicMock())
        assert n == 1
        mock_img.assert_not_called()
        args = db.insert.call_args
        assert args.args[1]["platform_post_id"] == "dry_run"


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image", return_value=("CID", "MID"))
def test_disabled_when_meta_creds_empty(mock_img, mock_ref):
    db = _mock_db([_past_row()])
    n = runner.publish_pending(db, _settings(meta_app_id=""), MagicMock())
    assert n == 0
    mock_img.assert_not_called()
    db.select_due_for_publish.assert_not_called()


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image", return_value=("CID", "MID"))
def test_one_row_failure_doesnt_stop_round(mock_img, mock_ref):
    row_ok = _past_row(qid="ok", asset_id="a1", brief_id="b1")
    row_bad = _past_row(qid="bad", asset_id="a1", brief_id="b1")
    mock_img.side_effect = [httpx.ConnectError("boom"), ("CID", "MID")]
    db = _mock_db([row_bad, row_ok])
    n = runner.publish_pending(db, _settings(), MagicMock())
    assert n == 1  # second row still published


@patch("aeloria.publishing.runner.refresh_if_needed")
def test_jitter_defers_future_due_row(mock_ref):
    # slot_time in the future + large jitter → not due → skipped
    future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    row = {"id": "qf", "asset_id": "a1", "brief_id": "b1", "caption": "c", "slot_time": future}
    db = _mock_db([row])
    with patch("aeloria.publishing.runner.meta.publish_image") as mock_img:
        n = runner.publish_pending(db, _settings(publish_jitter_minutes=20), MagicMock())
        assert n == 0
        mock_img.assert_not_called()


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image")
def test_401_retry_failure_marks_queue_skipped(mock_img, mock_ref):
    err = httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock(status_code=401))
    mock_img.side_effect = [err, err]  # both attempts 401
    db = _mock_db([_past_row()])
    tg = MagicMock()
    n = runner.publish_pending(db, _settings(), tg)
    assert n == 0
    db.update.assert_called_once()
    uargs = db.update.call_args
    assert uargs.args[0] == "queue"
    assert uargs.args[2]["approval"] == "skipped"
    assert uargs.args[2]["reject_reason"] == "meta_401: retry failed"
    tg.send_message.assert_called()
    assert mock_img.call_count == 2  # initial + one retry
    assert mock_ref.call_count == 2  # top-of-cycle + the 401 refresh


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_image")
def test_401_retry_then_400_marks_meta_400(mock_img, mock_ref):
    err_401 = httpx.HTTPStatusError("401", request=MagicMock(), response=MagicMock(status_code=401))
    err_400 = httpx.HTTPStatusError("policy", request=MagicMock(),
                                    response=MagicMock(status_code=400, text="bad content"))
    mock_img.side_effect = [err_401, err_400]  # first 401, retry throws 400
    db = _mock_db([_past_row()])
    tg = MagicMock()
    n = runner.publish_pending(db, _settings(), tg)
    assert n == 0
    db.update.assert_called_once()
    uargs = db.update.call_args
    assert uargs.args[2]["approval"] == "skipped"
    assert uargs.args[2]["reject_reason"].startswith("meta_400")
    assert mock_img.call_count == 2
    assert mock_ref.call_count == 2


# ---- Carousel routing (Phase 6a Task 5) ----


@patch("aeloria.publishing.runner.meta")
def test_publish_routes_carousel_to_publish_carousel(mock_meta):
    from aeloria.publishing.runner import _publish_one
    settings = MagicMock()
    mock_meta.publish_carousel.return_value = ("parent", "MEDIA")
    mid = _publish_one(settings, "static", "image", ["u1", "u2"], "cap", content_format="carousel")
    assert mid == "MEDIA"
    mock_meta.publish_carousel.assert_called_once_with(settings, ["u1", "u2"], "cap")


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_carousel", return_value=("CID", "MID"))
def test_carousel_slides_published_in_created_order(mock_carousel, mock_ref):
    """Regression test: slides must be fetched via the ordered select_all(order="created_at"),
    not the unordered select() — otherwise carousel slides can publish scrambled."""
    row = _past_row(qid="qc", asset_id="a1", brief_id="b-carousel")
    db = MagicMock()
    db.select_due_for_publish.return_value = [row]
    db.current_follower_count.return_value = 0
    db.insert.return_value = {"id": "post-1"}

    ordered_slides = [
        {"id": "s0", "kind": "image", "r2_url": "https://r2/slide0.png"},
        {"id": "s1", "kind": "image", "r2_url": "https://r2/slide1.png"},
        {"id": "s2", "kind": "image", "r2_url": "https://r2/slide2.png"},
    ]
    reversed_slides = list(reversed(ordered_slides))

    def _select(table, filters=None, limit=100):
        if table == "media_assets" and filters and "id" in filters:
            return [{"id": filters["id"], "kind": "image", "r2_url": "https://r2/cover.png"}]
        if table == "briefs":
            return [{"id": filters["id"], "slot_type": "static", "content_format": "carousel"}]
        if table == "media_assets" and filters and "brief_id" in filters:
            # If runner regressed to unordered db.select(), it would land here and get
            # scrambled slides — makes the order assertion below fail.
            return reversed_slides
        return []
    db.select.side_effect = _select

    def _select_all(table, filters=None, order=None, page_size=1000):
        assert table == "media_assets"
        assert filters == {"brief_id": "b-carousel"}
        assert order == "created_at"
        return ordered_slides
    db.select_all.side_effect = _select_all

    n = runner.publish_pending(db, _settings(), MagicMock())

    assert n == 1
    db.select_all.assert_called_once_with("media_assets", {"brief_id": "b-carousel"}, order="created_at")
    mock_carousel.assert_called_once()
    slide_urls_arg = mock_carousel.call_args.args[1]
    assert slide_urls_arg == [
        "https://r2/slide0.png", "https://r2/slide1.png", "https://r2/slide2.png",
    ]


@patch("aeloria.publishing.runner.refresh_if_needed")
@patch("aeloria.publishing.runner.meta.publish_carousel", return_value=("CID", "MID"))
def test_carousel_regen_excludes_stale_slides_from_prior_run(mock_carousel, mock_ref):
    """Regression test: after a Regen, the brief_id carries slides from BOTH the
    old (rejected) generation and the new one. The approved queue row's asset_id
    is the new run's cover — publish must only send that run's slides, not the
    stale ones from the earlier generation (else IG's 10-child carousel cap is
    exceeded and Meta returns a 400)."""
    row = _past_row(qid="qc-regen", asset_id="new-cover", brief_id="b-carousel-regen")
    db = MagicMock()
    db.select_due_for_publish.return_value = [row]
    db.current_follower_count.return_value = 0
    db.insert.return_value = {"id": "post-1"}

    # Old generation: created first, would-be stale after a regen.
    old_slides = [
        {"id": "old0", "kind": "image", "r2_url": "https://r2/old0.png",
         "created_at": "2026-07-01T00:00:00+00:00"},
        {"id": "old1", "kind": "image", "r2_url": "https://r2/old1.png",
         "created_at": "2026-07-01T00:00:05+00:00"},
    ]
    # New generation: created later (after Regen re-ran generate_carousel).
    new_slides = [
        {"id": "new-cover", "kind": "image", "r2_url": "https://r2/new0.png",
         "created_at": "2026-07-01T01:00:00+00:00"},
        {"id": "new1", "kind": "image", "r2_url": "https://r2/new1.png",
         "created_at": "2026-07-01T01:00:05+00:00"},
    ]
    all_slides = old_slides + new_slides
    new_cover = new_slides[0]

    def _select(table, filters=None, limit=100):
        if table == "media_assets" and filters and "id" in filters:
            assert filters["id"] == "new-cover"
            return [new_cover]
        if table == "briefs":
            return [{"id": filters["id"], "slot_type": "static", "content_format": "carousel"}]
        return []
    db.select.side_effect = _select

    def _select_all(table, filters=None, order=None):
        assert table == "media_assets"
        assert filters == {"brief_id": "b-carousel-regen"}
        assert order == "created_at"
        return all_slides
    db.select_all.side_effect = _select_all

    n = runner.publish_pending(db, _settings(), MagicMock())

    assert n == 1
    mock_carousel.assert_called_once()
    slide_urls_arg = mock_carousel.call_args.args[1]
    assert slide_urls_arg == ["https://r2/new0.png", "https://r2/new1.png"]
    assert "https://r2/old0.png" not in slide_urls_arg
    assert "https://r2/old1.png" not in slide_urls_arg