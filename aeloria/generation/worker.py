import logging
from datetime import datetime, time as dtime, timezone

from aeloria.budget import BudgetExceeded, check_budget
from aeloria.db.client import Db
from aeloria.distribution.hook_spec import validate as validate_hook
from aeloria.distribution.planner import plan as plan_distribution
from aeloria.generation.caption import write_caption
from aeloria.generation.carousel import generate_carousel
from aeloria.generation.face_gate import FaceGateError, passes_gate
from aeloria.generation.fal_images import FLUX_GENERAL_COST_USD, generate_image
from aeloria.generation.fal_router import resolve_workflow
from aeloria.generation.post import extract_frame, overlay_text
from aeloria.generation.prompt_builder import build_prompt
from aeloria.generation.refine import refine_and_regate
from aeloria.generation.video_worker import produce_video

log = logging.getLogger(__name__)

MAX_ATTEMPTS = 2
MAX_VIDEO_ATTEMPTS = 2
SLOT_HOUR_UTC = {"story": 9, "static": 17, "reel": 18}
APPROVAL_BUTTONS = [
    [("✅ Approve", "approve:{qid}"), ("❌ Reject", "reject:{qid}")],
    [("🔁 Regen", "regen:{qid}"), ("✏️ Caption", "caption:{qid}")],
]


class WorkerError(Exception):
    pass


def slot_time_utc(brief: dict) -> str:
    plan = brief.get("distribution_plan") or {}
    if plan.get("slot_time"):
        return plan["slot_time"]
    day = datetime.strptime(brief["slot_day"], "%Y-%m-%d").date()
    hour = SLOT_HOUR_UTC.get(brief["slot_type"], 12)
    return datetime.combine(day, dtime(hour=hour), tzinfo=timezone.utc).isoformat()


def process_brief(brief, db, settings, r2, persona, ref_embedding, tg=None) -> dict | None:
    db.update("briefs", brief["id"], {"status": "generating"})

    # Hook gate: discovery reels must carry a non-empty hook_spec BEFORE any
    # fal cost. Failing here marks the brief failed + alerts the operator;
    # check_budget / generate_image are never reached (zero spend).
    ok, why = validate_hook(brief)
    if not ok:
        db.update("briefs", brief["id"], {"status": "failed"})
        if tg:
            tg.send_message(f"❌ hook gate failed for {brief['id']}: {why}")
        return None

    # Carousel: generate N slides up front, queue the parent (first slide asset).
    # Routed before build_prompt/aspect setup — generate_carousel builds its own
    # prompt internally, so carousel briefs never enter the still-image loop.
    if brief.get("content_format") == "carousel":
        slides = generate_carousel(brief, db, settings, r2, persona, ref_embedding)
        if not slides:
            db.update("briefs", brief["id"], {"status": "failed"})
            raise WorkerError(f"carousel face gate failed for brief {brief['id']}")
        caption = write_caption(persona, brief, settings=settings,
                                distribution_plan=brief.get("distribution_plan"),
                                cta_kind=brief.get("cta_kind", "none"))
        q = db.insert("queue", {
            "asset_id": slides[0]["id"], "brief_id": brief["id"], "caption": caption,
            "platforms": brief["platforms"], "slot_time": slot_time_utc(brief),
        })
        db.update("briefs", brief["id"], {"status": "generated"})
        if tg:
            tg.send_photo(slides[0]["r2_url"],
                          f"[carousel · {brief['slot_day']}]\n{caption}",
                          [[(t, c.format(qid=q["id"])) for t, c in row] for row in APPROVAL_BUTTONS])
        return q

    aspect = "9:16" if brief["slot_type"] in ("story", "reel") else "4:5"
    prompt = build_prompt(persona, brief)
    last_sim = None

    # Route via the brief's workflow (identity-locked by default); the router
    # stacks the realism LoRA internally. Legacy briefs without a workflow fall
    # back to the default path, where realism is passed via extra_loras.
    wf = resolve_workflow(brief)
    extra_loras = None
    if wf is None and settings.realism_lora_url:
        extra_loras = [{"path": settings.realism_lora_url, "scale": settings.realism_lora_scale}]

    for attempt in range(MAX_ATTEMPTS):
        check_budget(db, settings, "fal", FLUX_GENERAL_COST_USD)
        result = generate_image(
            prompt, settings=settings, aspect_ratio=aspect,
            workflow=wf, extra_loras=extra_loras,
        )
        try:
            sim, ok = passes_gate(result.image_bytes, ref_embedding, settings.face_gate_threshold)
        except FaceGateError:
            sim, ok = None, False
        else:
            last_sim = sim
        final_bytes = result.image_bytes
        if ok:  # only refine a passing base; sim may improve or fall back
            final_bytes, sim = refine_and_regate(result.image_bytes, settings, ref_embedding, sim)
        key = f"content/{brief['slot_day']}/{brief['id']}-{attempt}.png"
        still_url = r2.upload(final_bytes, key, "image/png")
        still_asset = db.insert("media_assets", {
            "brief_id": brief["id"], "r2_url": still_url, "kind": "image",
            "engine": "fal", "gen_params": result.gen_params,
            "cost": result.cost_usd, "face_similarity": sim,
        })
        if not ok:
            continue

        # Reel: animate the hero still, then run the video face-gate on a late
        # frame. Drift → retry up to MAX_VIDEO_ATTEMPTS. A video media_assets
        # row is inserted on EVERY attempt (raw mp4 on drift, overlaid on pass)
        # so kling cost is tracked even when post-processing fails. The raw
        # Kling i2v call is delegated to produce_video; the gate/overlay/retry
        # loop lives here so extract_frame/overlay_text failures propagate and
        # the spend row is always recorded first.
        if brief["slot_type"] == "reel":
            keywords = (brief.get("distribution_plan") or {}).get("on_screen_keywords") or []
            asset = None
            for v_attempt in range(MAX_VIDEO_ATTEMPTS):
                check_budget(db, settings, "fal", settings.kling_video_cost_usd)
                v = produce_video(still_url, prompt, settings)
                # Record spend IMMEDIATELY after kling — if extract_frame /
                # overlay / upload fail below, the cost row must still exist.
                asset = db.insert("media_assets", {
                    "brief_id": brief["id"], "r2_url": None, "kind": "video",
                    "engine": "fal", "gen_params": v.gen_params,
                    "cost": v.cost_usd, "face_similarity": None,
                })
                frame = extract_frame(v.video_bytes, settings.video_gate_frame_seconds, settings)
                try:
                    sim, ok = passes_gate(frame, ref_embedding, settings.face_gate_threshold)
                except FaceGateError:
                    sim, ok = None, False
                mp4 = overlay_text(v.video_bytes, keywords, settings) if ok else v.video_bytes
                key = f"content/{brief['slot_day']}/{brief['id']}-v{v_attempt}.mp4"
                url = r2.upload(mp4, key, "video/mp4")
                db.update("media_assets", asset["id"], {"r2_url": url, "face_similarity": sim})
                asset = {**asset, "r2_url": url, "face_similarity": sim}
                if ok:
                    break
            else:
                db.update("briefs", brief["id"], {"status": "failed"})
                raise WorkerError(
                    f"video face gate failed {MAX_VIDEO_ATTEMPTS}x for brief {brief['id']} "
                    f"(still sim={last_sim})"
                )
        else:
            asset = still_asset

        caption = write_caption(persona, brief, settings=settings,
                                distribution_plan=brief.get("distribution_plan"),
                                cta_kind=brief.get("cta_kind", "none"))
        q = db.insert("queue", {
            "asset_id": asset["id"], "brief_id": brief["id"], "caption": caption,
            "platforms": brief["platforms"], "slot_time": slot_time_utc(brief),
        })
        db.update("briefs", brief["id"], {"status": "generated"})
        if tg:
            buttons = [
                [(t, c.format(qid=q["id"])) for t, c in row] for row in APPROVAL_BUTTONS
            ]
            tg.send_photo(still_url, f"[{brief['slot_type']} · {brief['slot_day']}]\n{caption}", buttons)
        return q

    db.update("briefs", brief["id"], {"status": "failed"})
    raise WorkerError(
        f"face gate failed {MAX_ATTEMPTS}x for brief {brief['id']} (last sim={last_sim})"
    )


def run_pending(db: Db, settings, r2, persona, ref_embedding, tg=None, limit: int = 10) -> int:
    briefs = db.select("briefs", {"status": "planned", "engine": "fal"}, limit=limit)
    done = 0
    for b in briefs:
        # Race guard: if the worker ticks before the distribution planner has
        # enriched this brief, plan inline so the post never generates without
        # hashtags/keywords. Planner failure/None -> proceed; the hook gate in
        # process_brief still decides whether generation is allowed.
        if not b.get("distribution_plan"):
            try:
                inline_plan = plan_distribution(b, db, settings, persona)
            except Exception as e:
                inline_plan = None
                log.warning("inline distribution plan failed for brief %s: %s", b["id"], e)
            if inline_plan:
                b = {**b, "distribution_plan": inline_plan}
        try:
            process_brief(b, db, settings, r2, persona, ref_embedding, tg=tg)
            done += 1
        except BudgetExceeded as e:
            db.update("briefs", b["id"], {"status": "planned"})
            log.warning("budget cap hit, stopping: %s", e)
            break
        except Exception as e:
            db.update("briefs", b["id"], {"status": "failed"})
            log.warning("run_pending: %s", e)
            return done
    return done
