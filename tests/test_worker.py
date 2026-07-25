from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from aeloria.budget import BudgetExceeded
from aeloria.generation.worker import WorkerError, process_brief, run_pending, slot_time_utc


BRIEF = {
    "id": "b1", "slot_day": "2026-07-20", "slot_type": "static",
    "prompt_seed": "porch tea", "beat": "tea", "caption_brief": "calm",
    "platforms": ["instagram"], "engine": "fal", "status": "planned",
}


def _mocks():
    db, r2, tg = MagicMock(), MagicMock(), MagicMock()
    db.insert.side_effect = lambda table, row: {**row, "id": f"{table}-id"}
    r2.upload.return_value = "https://pub.r2.dev/x.png"
    settings = MagicMock()
    settings.face_gate_threshold = 0.35
    settings.realism_lora_url = ""   # off by default — no skin-LoRA stacking
    settings.realism_lora_scale = 0.6
    settings.kling_video_cost_usd = 0.20
    settings.video_gate_frame_seconds = 4.0
    settings.refine_enabled = False
    persona, ref = MagicMock(), MagicMock()
    return db, r2, tg, settings, persona, ref


def _mock_gen_result(png_bytes=b"png", cost_usd=0.035, gen_params=None):
    """Proper mock for generate_image: image_bytes must be a real bytes-like object
    (not a MagicMock) so InsightFace cv2.imdecode does not raise TypeError."""
    result = MagicMock()
    type(result).image_bytes = PropertyMock(return_value=png_bytes)
    result.cost_usd = cost_usd
    result.gen_params = gen_params or {}
    return result


def test_slot_time_utc():
    assert slot_time_utc(BRIEF) == "2026-07-20T17:00:00+00:00"


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_happy_path_creates_queue_and_notifies(mock_budget, mock_gen, mock_gate, mock_cap):
    mock_gen.return_value = _mock_gen_result()
    db, r2, tg, settings, persona, ref = _mocks()
    q = process_brief(BRIEF, db, settings, r2, persona, ref, tg=tg)
    assert q["id"] == "queue-id"
    db.update.assert_any_call("briefs", "b1", {"status": "generated"})
    tg.send_photo.assert_called_once()
    photo_url = tg.send_photo.call_args.args[0]
    assert photo_url == "https://pub.r2.dev/x.png"
    inserted_asset = db.insert.call_args_list[0].args[1]
    assert inserted_asset["face_similarity"] == 0.8


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.refine_and_regate", return_value=(b"refined-png", 0.72))
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_worker_uploads_refined_still(mock_budget, mock_gen, mock_gate, mock_refine, mock_cap):
    mock_gen.return_value = _mock_gen_result(b"base-png", cost_usd=0.05)
    db, r2, tg, settings, persona, ref = _mocks()
    settings.refine_enabled = True
    process_brief(BRIEF, db, settings, r2, persona, ref)
    # the refined bytes were uploaded, not the base
    up = r2.upload.call_args.args
    assert up[0] == b"refined-png"
    mock_refine.assert_called_once()


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate")
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_gate_fail_then_pass_retries(mock_budget, mock_gen, mock_gate, mock_cap):
    mock_gen.return_value = _mock_gen_result()
    mock_gate.side_effect = [(0.1, False), (0.9, True)]
    db, r2, tg, settings, persona, ref = _mocks()
    q = process_brief(BRIEF, db, settings, r2, persona, ref)
    assert q["id"] == "queue-id"
    assert mock_gen.call_count == 2
    asset_inserts = [c for c in db.insert.call_args_list if c.args[0] == "media_assets"]
    assert len(asset_inserts) == 2  # both attempts recorded (cost spent either way)


@patch("aeloria.generation.worker.passes_gate", return_value=(0.1, False))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_gate_fails_twice_marks_failed(mock_budget, mock_gen, mock_gate):
    mock_gen.return_value = _mock_gen_result()
    db, r2, tg, settings, persona, ref = _mocks()
    with pytest.raises(WorkerError):
        process_brief(BRIEF, db, settings, r2, persona, ref)
    db.update.assert_any_call("briefs", "b1", {"status": "failed"})


@patch("aeloria.generation.worker.plan_distribution", return_value=None)
@patch("aeloria.generation.worker.process_brief")
def test_run_pending_budget_stop_resets_brief(mock_process, mock_plan):
    mock_process.side_effect = BudgetExceeded("cap")
    db = MagicMock()
    db.select.return_value = [dict(BRIEF), dict(BRIEF, id="b2")]
    n = run_pending(db, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    assert n == 0
    assert mock_process.call_count == 1  # stops after first budget hit
    db.update.assert_called_once_with("briefs", "b1", {"status": "planned"})


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate")
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_face_gate_error_counts_as_failed_attempt(mock_budget, mock_gen, mock_gate, mock_cap):
    from aeloria.generation.face_gate import FaceGateError
    mock_gen.return_value = _mock_gen_result()
    mock_gate.side_effect = [FaceGateError("no face"), (0.9, True)]
    db, r2, tg, settings, persona, ref = _mocks()
    q = process_brief(BRIEF, db, settings, r2, persona, ref)
    assert q["id"] == "queue-id"
    asset_inserts = [c for c in db.insert.call_args_list if c.args[0] == "media_assets"]
    assert len(asset_inserts) == 2
    assert asset_inserts[0].args[1]["face_similarity"] is None


@patch("aeloria.generation.worker.plan_distribution", return_value=None)
@patch("aeloria.generation.worker.process_brief")
def test_run_pending_unexpected_error_marks_failed(mock_process, mock_plan):
    mock_process.side_effect = RuntimeError("boom")
    db = MagicMock()
    db.select.return_value = [dict(BRIEF)]
    n = run_pending(db, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    assert n == 0
    db.update.assert_called_once_with("briefs", "b1", {"status": "failed"})


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_worker_stacks_realism_lora_when_configured(mock_budget, mock_gen, mock_gate, mock_cap):
    mock_gen.return_value = _mock_gen_result()
    db, r2, tg, settings, persona, ref = _mocks()
    settings.realism_lora_url = "https://hf/realism.safetensors"
    settings.realism_lora_scale = 0.6
    process_brief(BRIEF, db, settings, r2, persona, ref)
    _, kwargs = mock_gen.call_args
    assert kwargs["extra_loras"] == [{"path": "https://hf/realism.safetensors", "scale": 0.6}]


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_worker_routes_via_brief_workflow(mock_budget, mock_gen, mock_gate, mock_cap):
    from aeloria.generation.fal_router import WorkflowType
    mock_gen.return_value = _mock_gen_result()
    db, r2, tg, settings, persona, ref = _mocks()
    settings.realism_lora_url = "https://hf/realism.safetensors"  # router will stack it, not extra_loras
    settings.realism_lora_scale = 0.45
    process_brief({**BRIEF, "workflow": "IDENTITY_LOCKED_LORA"}, db, settings, r2, persona, ref)
    _, kwargs = mock_gen.call_args
    assert kwargs["workflow"] == WorkflowType.IDENTITY_LOCKED_LORA
    assert kwargs["extra_loras"] is None  # realism handled inside the router, not double-stacked


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_worker_skips_realism_lora_when_empty(mock_budget, mock_gen, mock_gate, mock_cap):
    mock_gen.return_value = _mock_gen_result()
    db, r2, tg, settings, persona, ref = _mocks()
    settings.realism_lora_url = ""  # kill switch
    process_brief(BRIEF, db, settings, r2, persona, ref)
    _, kwargs = mock_gen.call_args
    assert kwargs["extra_loras"] is None


from aeloria.distribution.hook_spec import validate  # noqa: F401  (documents the gate source)

DISCOVERY_REEL = dict(BRIEF, slot_type="reel", audience="discovery",
    hook_spec="still cabin window golden hour then match-cut to motion on the beat")


def test_slot_time_utc_prefers_distribution_plan():
    b = dict(BRIEF, distribution_plan={"slot_time": "2026-07-20T22:30:00+00:00"})
    assert slot_time_utc(b) == "2026-07-20T22:30:00+00:00"


def test_slot_time_utc_falls_back_when_no_plan():
    assert slot_time_utc(BRIEF) == "2026-07-20T17:00:00+00:00"


@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_discovery_reel_without_hook_spec_fails_no_spend(mock_budget, mock_gen):
    db, r2, tg, settings, persona, ref = _mocks()
    bad = dict(DISCOVERY_REEL, hook_spec=None)
    q = process_brief(bad, db, settings, r2, persona, ref, tg=tg)
    assert q is None
    db.update.assert_any_call("briefs", bad["id"], {"status": "failed"})
    mock_gen.assert_not_called()
    mock_budget.assert_not_called()
    tg.send_message.assert_called_once()
    assert "hook" in tg.send_message.call_args.args[0]


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget", return_value=None)
def test_discovery_reel_with_hook_generates(mock_budget, mock_gen, mock_gate, mock_cap):
    # reel path: still gen passes -> produce_video animates -> video queued.
    # NOTE: produce_video is patched via context manager only (not as decorator) to
    # avoid two independent patches on the same name conflicting.
    with patch("aeloria.generation.worker.produce_video") as mock_vid, \
         patch("aeloria.generation.worker.extract_frame"), \
         patch("aeloria.generation.worker.overlay_text"):
        mock_vid.return_value = _vid_mock()
        db, r2, tg, settings, persona, ref = _mocks()
        q = process_brief(DISCOVERY_REEL, db, settings, r2, persona, ref, tg=tg)
    assert q["id"] == "queue-id"
    mock_gen.assert_called()
    mock_vid.assert_called()
    kinds = [c.args[1]["kind"] for c in db.insert.call_args_list if c.args[0] == "media_assets"]
    assert "image" in kinds and "video" in kinds
    assert db.insert.call_args_list[-1].args[0] == "queue"


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_worker_passes_distribution_plan_to_caption(mock_budget, mock_gen, mock_gate, mock_cap):
    mock_gen.return_value = _mock_gen_result()
    db, r2, tg, settings, persona, ref = _mocks()
    plan = {"hashtags": ["#a", "#b"], "slot_time": "2026-07-20T18:00:00+00:00"}
    b = dict(BRIEF, distribution_plan=plan)
    process_brief(b, db, settings, r2, persona, ref, tg=tg)
    _, kwargs = mock_cap.call_args
    assert kwargs["distribution_plan"] == plan


# ---- Reel / video face-gate (Phase 3b) ----

REEL = dict(BRIEF, slot_type="reel", distribution_plan={
    "on_screen_keywords": ["slow mornings"], "slot_time": "2026-07-20T18:00:00+00:00",
})


def _vid_mock():
    return MagicMock(video_bytes=b"mp4", cost_usd=0.20, gen_params={"model": "kling"})


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.overlay_text")
@patch("aeloria.generation.worker.extract_frame")
@patch("aeloria.generation.worker.produce_video")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget", return_value=None)
def test_reel_happy_path_queues_video_and_previews_still(
    mock_budget, mock_gen, mock_gate, mock_vid, mock_frame, mock_overlay, mock_cap):
    mock_gen.return_value = _mock_gen_result(cost_usd=0.05)
    mock_vid.return_value = _vid_mock()
    mock_frame.return_value = b"frame-png"
    mock_overlay.return_value = b"mp4-overlaid"
    db, r2, tg, settings, persona, ref = _mocks()
    q = process_brief(REEL, db, settings, r2, persona, ref, tg=tg)
    assert q["id"] == "queue-id"
    mock_vid.assert_called_once()
    mock_overlay.assert_called_once()  # gate passed -> overlay applied
    kinds = [c.args[1]["kind"] for c in db.insert.call_args_list if c.args[0] == "media_assets"]
    assert kinds.count("image") == 1
    assert kinds.count("video") == 1
    video_rows = [c.args[1] for c in db.insert.call_args_list
                  if c.args[0] == "media_assets" and c.args[1]["kind"] == "video"]
    assert len(video_rows) == 1
    # insert side_effect assigns id f"{table}-id" -> "media_assets-id"; queue
    # must point at the VIDEO asset (not the still image asset).
    assert q["asset_id"] == "media_assets-id"
    tg.send_photo.assert_called_once()  # still url used as the preview
    assert tg.send_photo.call_args.args[0] == "https://pub.r2.dev/x.png"


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.overlay_text")
@patch("aeloria.generation.worker.extract_frame")
@patch("aeloria.generation.worker.produce_video")
@patch("aeloria.generation.worker.passes_gate")
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget", return_value=None)
def test_reel_video_gate_drift_both_fail_marks_failed(
    mock_budget, mock_gen, mock_gate, mock_vid, mock_frame, mock_overlay, mock_cap):
    mock_gen.return_value = _mock_gen_result(cost_usd=0.05)
    mock_vid.return_value = _vid_mock()
    mock_frame.return_value = b"frame-png"
    # still passes (call 1), video late-frame drifts twice (calls 2,3).
    mock_gate.side_effect = [(0.9, True), (0.1, False), (0.1, False)]
    db, r2, tg, settings, persona, ref = _mocks()
    with pytest.raises(WorkerError):
        process_brief(REEL, db, settings, r2, persona, ref, tg=tg)
    assert mock_vid.call_count == 2          # both attempts ran (cost debited)
    mock_overlay.assert_not_called()          # never passed -> no overlay
    kinds = [c.args[1]["kind"] for c in db.insert.call_args_list if c.args[0] == "media_assets"]
    assert kinds.count("image") == 1
    assert kinds.count("video") == 2          # raw mp4 recorded on each failed attempt
    assert not any(c.args[0] == "queue" for c in db.insert.call_args_list)
    db.update.assert_any_call("briefs", REEL["id"], {"status": "failed"})


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.overlay_text")
@patch("aeloria.generation.worker.extract_frame")
@patch("aeloria.generation.worker.produce_video")
@patch("aeloria.generation.worker.passes_gate")
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget", return_value=None)
def test_reel_video_gate_drift_then_pass(
    mock_budget, mock_gen, mock_gate, mock_vid, mock_frame, mock_overlay, mock_cap):
    mock_gen.return_value = _mock_gen_result(cost_usd=0.05)
    mock_vid.return_value = _vid_mock()
    mock_frame.return_value = b"frame-png"
    mock_overlay.return_value = b"mp4-overlaid"
    # still passes (1), video drift (2), video passes (3) -> queued on 2nd attempt.
    mock_gate.side_effect = [(0.9, True), (0.1, False), (0.85, True)]
    db, r2, tg, settings, persona, ref = _mocks()
    q = process_brief(REEL, db, settings, r2, persona, ref, tg=tg)
    assert q["id"] == "queue-id"
    assert mock_vid.call_count == 2
    mock_overlay.assert_called_once()         # overlay only on the passing attempt
    kinds = [c.args[1]["kind"] for c in db.insert.call_args_list if c.args[0] == "media_assets"]
    assert kinds.count("video") == 2


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.produce_video")
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_reel_budget_miss_on_video_leg_no_video_gen(
    mock_budget, mock_gen, mock_vid, mock_gate, mock_cap):
    mock_gen.return_value = _mock_gen_result(cost_usd=0.05)
    # image-leg check passes (None), video-leg check trips the cap -> propagate.
    mock_budget.side_effect = [None, BudgetExceeded("kling cap")]
    db, r2, tg, settings, persona, ref = _mocks()
    with pytest.raises(BudgetExceeded):
        process_brief(REEL, db, settings, r2, persona, ref, tg=tg)
    mock_gen.assert_called_once()             # hero still generated
    mock_vid.assert_not_called()              # budget tripped before kling


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.produce_video")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
def test_static_brief_never_calls_video_path(mock_budget, mock_gen, mock_gate, mock_vid, mock_cap):
    mock_gen.return_value = _mock_gen_result(cost_usd=0.05)
    db, r2, tg, settings, persona, ref = _mocks()
    q = process_brief(BRIEF, db, settings, r2, persona, ref, tg=tg)
    assert q["id"] == "queue-id"
    mock_vid.assert_not_called()
    kinds = [c.args[1]["kind"] for c in db.insert.call_args_list if c.args[0] == "media_assets"]
    assert kinds == ["image"]                 # static -> image-only, no video


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.overlay_text")
@patch("aeloria.generation.worker.extract_frame", side_effect=RuntimeError("ffmpeg boom"))
@patch("aeloria.generation.worker.produce_video")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget", return_value=None)
def test_video_cost_recorded_even_when_postprocessing_fails(
    mock_budget, mock_gen, mock_gate, mock_vid, mock_frame, mock_overlay, mock_cap):
    # fal spend happened -> the cost row must exist even though extract_frame died.
    mock_gen.return_value = _mock_gen_result(cost_usd=0.05)
    mock_vid.return_value = _vid_mock()
    db, r2, tg, settings, persona, ref = _mocks()
    with pytest.raises(RuntimeError):
        process_brief(REEL, db, settings, r2, persona, ref, tg=tg)
    video_rows = [c.args[1] for c in db.insert.call_args_list
                  if c.args[0] == "media_assets" and c.args[1]["kind"] == "video"]
    assert len(video_rows) == 1
    assert video_rows[0]["cost"] == 0.20


# ---- Worker/planner race: plan-less briefs are planned inline ----

INLINE_PLAN = {"hashtags": ["#a"], "on_screen_keywords": ["slow mornings"],
               "slot_time": "2026-07-20T18:00:00+00:00"}


@patch("aeloria.generation.worker.plan_distribution")
@patch("aeloria.generation.worker.process_brief")
def test_run_pending_plans_inline_when_brief_has_no_plan(mock_process, mock_plan):
    mock_plan.return_value = INLINE_PLAN
    db = MagicMock()
    db.select.return_value = [dict(BRIEF)]  # no distribution_plan
    n = run_pending(db, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    assert n == 1
    mock_plan.assert_called_once()
    assert mock_plan.call_args.args[0]["id"] == "b1"
    assert mock_process.call_args.args[0]["distribution_plan"] == INLINE_PLAN


@patch("aeloria.generation.worker.plan_distribution")
@patch("aeloria.generation.worker.process_brief")
def test_run_pending_skips_inline_plan_when_brief_has_plan(mock_process, mock_plan):
    db = MagicMock()
    db.select.return_value = [dict(BRIEF, distribution_plan=INLINE_PLAN)]
    run_pending(db, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    mock_plan.assert_not_called()
    assert mock_process.call_args.args[0]["distribution_plan"] == INLINE_PLAN


@patch("aeloria.generation.worker.plan_distribution", side_effect=RuntimeError("boom"))
@patch("aeloria.generation.worker.process_brief")
def test_run_pending_planner_failure_still_processes(mock_process, mock_plan):
    db = MagicMock()
    db.select.return_value = [dict(BRIEF)]
    n = run_pending(db, MagicMock(), MagicMock(), MagicMock(), MagicMock())
    assert n == 1  # hook gate inside process_brief decides, not the planner
    assert mock_process.call_args.args[0].get("distribution_plan") is None


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.passes_gate", return_value=(0.8, True))
@patch("aeloria.generation.worker.generate_image")
@patch("aeloria.generation.worker.check_budget")
@patch("aeloria.generation.worker.plan_distribution")
def test_inline_plan_attached_before_caption(
    mock_plan, mock_budget, mock_gen, mock_gate, mock_cap):
    mock_plan.return_value = INLINE_PLAN
    mock_gen.return_value = _mock_gen_result()
    db, r2, tg, settings, persona, ref = _mocks()
    db.select.return_value = [dict(BRIEF)]  # plan-less
    n = run_pending(db, settings, r2, persona, ref)
    assert n == 1
    _, kwargs = mock_cap.call_args
    assert kwargs["distribution_plan"] == INLINE_PLAN


# ---- Carousel routing (Phase 6a Task 5) ----


@patch("aeloria.generation.worker.write_caption", return_value="cap")
@patch("aeloria.generation.worker.generate_carousel")
@patch("aeloria.generation.worker.plan_distribution", return_value=None)
def test_process_brief_carousel_routes_to_generate_carousel(mock_plan, mock_gc, mock_wc):
    from aeloria.generation.worker import process_brief
    mock_gc.return_value = [
        {"id": "a1", "r2_url": "u1"}, {"id": "a2", "r2_url": "u2"},
    ]
    brief = {
        "id": "b1", "slot_day": "2026-07-20", "slot_type": "static",
        "content_format": "carousel", "cta_kind": "save", "audience": "retention",
        "platforms": ["instagram"], "distribution_plan": {"on_screen_keywords": ["a", "b"]},
        "hook_spec": None,
    }
    db = MagicMock()
    db.insert.side_effect = lambda t, row: {**row, "id": "q1"}
    process_brief(brief, db, MagicMock(), MagicMock(), MagicMock(), [0.1], tg=None)
    mock_gc.assert_called_once()
    # queue references the first slide asset
    q_row = [c.args[1] for c in db.insert.call_args_list if c.args[0] == "queue"][0]
    assert q_row["asset_id"] == "a1"
    # caption got cta_kind
    assert mock_wc.call_args.kwargs["cta_kind"] == "save"
