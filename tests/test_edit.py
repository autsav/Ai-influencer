from unittest.mock import MagicMock, patch

import pytest

from aeloria.approval.handlers import handle_edit_command
from aeloria.generation.edit import EditError, edit_image, edit_queued_post


def _settings():
    s = MagicMock()
    s.fal_key = "k"
    s.face_gate_threshold = 0.35
    return s


@patch("aeloria.generation.edit.httpx.get")
@patch("aeloria.generation.edit.fal_client.subscribe")
def test_edit_image_routes_kontext_and_uploads(mock_sub, mock_get):
    mock_sub.return_value = {"images": [{"url": "https://fal/edited.png"}]}
    mock_get.return_value = MagicMock(content=b"png", raise_for_status=MagicMock())
    r2 = MagicMock()
    r2.upload.return_value = "https://r2/edits/x.png"

    out = edit_image("https://r2/src.png", "change her jacket to a red leather moto jacket",
                     _settings(), r2)

    assert mock_sub.call_args.args[0] == "fal-ai/flux-kontext/dev"
    args = mock_sub.call_args.kwargs["arguments"]
    assert args["image_url"] == "https://r2/src.png"       # edits the existing correct image
    assert args["guidance_scale"] == 3.5 and args["num_inference_steps"] == 28
    assert out["r2_url"] == "https://r2/edits/x.png"
    assert out["face_similarity"] is None                  # no ref embedding -> no gate


@patch("aeloria.generation.edit.passes_gate", return_value=(0.71, True))
@patch("aeloria.generation.edit.httpx.get")
@patch("aeloria.generation.edit.fal_client.subscribe")
def test_edit_image_runs_face_gate_when_ref_given(mock_sub, mock_get, _mock_gate):
    mock_sub.return_value = {"images": [{"url": "https://fal/edited.png"}]}
    mock_get.return_value = MagicMock(content=b"png", raise_for_status=MagicMock())
    r2 = MagicMock()
    r2.upload.return_value = "https://r2/e.png"

    out = edit_image("https://r2/src.png", "swap background to a rainy street",
                     _settings(), r2, ref_embedding=object())
    assert out["face_similarity"] == 0.71  # drift sanity-check applied


def test_edit_image_requires_source_url():
    with pytest.raises(EditError):
        edit_image("", "x", _settings(), MagicMock())


@patch("aeloria.generation.edit.edit_image")
def test_edit_queued_post_creates_pending_and_previews(mock_edit):
    mock_edit.return_value = {"r2_url": "https://r2/e.png", "image_bytes": b"p",
                             "face_similarity": 0.7, "cost_usd": 0.05}
    db = MagicMock()
    db.select.side_effect = [
        [{"id": "q1", "asset_id": "a1", "brief_id": "b1", "caption": "cap",
          "platforms": ["instagram"], "slot_time": "2026-08-01T00:00:00+00:00"}],
        [{"id": "a1", "r2_url": "https://r2/src.png"}],
    ]
    db.insert.side_effect = [{"id": "a2"}, {"id": "q2"}]
    tg = MagicMock()

    res = edit_queued_post("q1", "red leather jacket", db, _settings(), MagicMock(), tg=tg)

    assert res["queue_id"] == "q2" and res["asset_id"] == "a2"
    assert db.insert.call_count == 2                     # new asset + new pending queue row
    tg.send_photo.assert_called_once()                  # preview with approval buttons
    new_queue_row = db.insert.call_args_list[1].args[1]
    assert new_queue_row["caption"] == "cap"            # inherits the source post's caption
    assert new_queue_row["asset_id"] == "a2"
    assert "approval" not in new_queue_row              # defaults to pending in the DB


def test_edit_queued_post_missing_queue_raises():
    db = MagicMock()
    db.select.return_value = []
    with pytest.raises(EditError, match="not found"):
        edit_queued_post("nope", "x", db, _settings(), MagicMock())


def test_edit_queued_post_source_without_r2_url_raises():
    db = MagicMock()
    db.select.side_effect = [
        [{"id": "q1", "asset_id": "a1"}],
        [{"id": "a1", "r2_url": None}],
    ]
    with pytest.raises(EditError, match="r2_url"):
        edit_queued_post("q1", "x", db, _settings(), MagicMock())


def test_handle_edit_command_usage_on_missing_args():
    assert handle_edit_command("/edit", MagicMock()).startswith("Usage")
    assert handle_edit_command("/edit q1", MagicMock()).startswith("Usage")
