"""Outfit / scene edits on an existing, identity-correct Aeloria image via the
IN_PAINTING_EDIT workflow (fal flux-kontext).

Identity-safe by construction: it EDITS the already-correct image (face intact)
rather than regenerating from scratch, so the identity LoRA isn't needed and the
face is preserved. The edit result is still re-checked against the face gate as a
drift sanity check, then queued as a new pending post for operator approval.
"""
import os
from datetime import datetime, timezone

import fal_client
import httpx

from aeloria.generation.face_gate import FaceGateError, passes_gate
from aeloria.generation.fal_images import FLUX_GENERAL_COST_USD
from aeloria.generation.fal_router import WorkflowType, build_payload
from aeloria.generation.worker import APPROVAL_BUTTONS


class EditError(Exception):
    pass


def edit_image(image_url, instruction, settings, r2, ref_embedding=None, seed=None) -> dict:
    """Apply `instruction` to `image_url` via flux-kontext and upload the result.

    Returns `{r2_url, image_bytes, face_similarity, cost_usd}`. `face_similarity`
    is None when no reference embedding is supplied or the gate finds no face.
    """
    if not image_url:
        raise EditError("edit_image requires a source image_url")
    os.environ["FAL_KEY"] = settings.fal_key
    endpoint, arguments = build_payload(
        WorkflowType.IN_PAINTING_EDIT, instruction, image_url=image_url, seed=seed)
    try:
        result = fal_client.subscribe(endpoint, arguments=arguments)
    except Exception as e:
        raise EditError(f"fal edit failed: {e}") from e
    images = result.get("images") or []
    if not images:
        raise EditError(f"fal returned no images: {result}")

    resp = httpx.get(images[0]["url"], timeout=60)
    resp.raise_for_status()
    img = resp.content

    sim = None
    if ref_embedding is not None:
        try:
            sim, _ok = passes_gate(img, ref_embedding, settings.face_gate_threshold)
        except FaceGateError:
            sim = None

    key = f"edits/{datetime.now(timezone.utc):%Y%m%dT%H%M%S}.png"
    url = r2.upload(img, key, "image/png")
    return {"r2_url": url, "image_bytes": img, "face_similarity": sim,
            "cost_usd": FLUX_GENERAL_COST_USD}


def edit_queued_post(queue_id, instruction, db, settings, r2, ref_embedding=None, tg=None) -> dict:
    """Edit the image behind an existing queue row and queue the result as a NEW
    pending post (same caption / slot_time / brief). Sends a Telegram preview with
    approval buttons when `tg` is given. Returns the new queue + asset ids.
    """
    rows = db.select("queue", {"id": queue_id}, limit=1)
    if not rows:
        raise EditError(f"queue row {queue_id} not found")
    q = rows[0]
    assets = db.select("media_assets", {"id": q["asset_id"]}, limit=1)
    if not assets or not assets[0].get("r2_url"):
        raise EditError("source asset missing or has no r2_url")

    edited = edit_image(assets[0]["r2_url"], instruction, settings, r2, ref_embedding=ref_embedding)

    new_asset = db.insert("media_assets", {
        "brief_id": q.get("brief_id"), "r2_url": edited["r2_url"], "kind": "image",
        "engine": "fal", "gen_params": {"edit": instruction, "source_asset": q["asset_id"]},
        "cost": edited["cost_usd"], "face_similarity": edited["face_similarity"],
    })
    new_q = db.insert("queue", {
        "asset_id": new_asset["id"], "brief_id": q.get("brief_id"),
        "caption": q["caption"], "platforms": q["platforms"], "slot_time": q["slot_time"],
    })

    if tg is not None:
        buttons = [[(t, c.format(qid=new_q["id"])) for t, c in row] for row in APPROVAL_BUTTONS]
        sim = edited["face_similarity"]
        caption = f"✏️ edited: {instruction}" + (f"\nface_sim={sim:.2f}" if sim is not None else "")
        tg.send_photo(edited["r2_url"], caption, buttons)

    return {"queue_id": new_q["id"], "asset_id": new_asset["id"],
            "r2_url": edited["r2_url"], "face_similarity": edited["face_similarity"]}
