"""Video post-processing: animate identity-locked still via Kling i2v,
then run the video face-gate on a late frame. Exists separately from
the image worker so the two concerns (static → video) are decoupled."""

import logging

from aeloria.budget import BudgetExceeded, check_budget
from aeloria.db.client import Db
from aeloria.generation.fal_video import generate_video
from aeloria.generation.face_gate import FaceGateError, passes_gate
from aeloria.generation.post import extract_frame, overlay_text

log = logging.getLogger(__name__)

MAX_VIDEO_ATTEMPTS = 2


def produce_video(
    brief: dict,
    db: Db,
    settings,
    r2,
    ref_embedding,
    prompt: str,
    still_url: str,
) -> dict | None:
    """Animate the identity-locked hero still via Kling i2v, then run the video
    face-gate on a late frame. Drift → retry up to MAX_VIDEO_ATTEMPTS.

    A video asset row is inserted on EVERY attempt (raw mp4 on drift,
    overlaid+text on pass) so cost is tracked via media_assets.

    Returns the passing asset dict or None (all attempts failed).
    """
    keywords = (brief.get("distribution_plan") or {}).get("on_screen_keywords") or []

    for attempt in range(MAX_VIDEO_ATTEMPTS):
        check_budget(db, settings, "fal", settings.kling_video_cost_usd)

        v = generate_video(still_url, prompt, settings=settings)

        # Record spend IMMEDIATELY after the fal generation — if extract_frame /
        # overlay / upload fail below, the cost row must still exist for budgeting.
        asset = db.insert(
            "media_assets",
            {
                "brief_id": brief["id"],
                "r2_url": None,
                "kind": "video",
                "engine": "fal",
                "gen_params": v.gen_params,
                "cost": v.cost_usd,
                "face_similarity": None,
            },
        )

        frame = extract_frame(v.video_bytes, settings.video_gate_frame_seconds, settings)
        try:
            sim, ok = passes_gate(frame, ref_embedding, settings.face_gate_threshold)
        except FaceGateError:
            sim, ok = None, False

        mp4 = overlay_text(v.video_bytes, keywords, settings) if ok else v.video_bytes

        key = f"content/{brief['slot_day']}/{brief['id']}-v{attempt}.mp4"
        url = r2.upload(mp4, key, "video/mp4")

        patch = {"r2_url": url, "face_similarity": sim}
        db.update("media_assets", asset["id"], patch)
        asset = {**asset, **patch}

        if ok:
            return asset

    return None
