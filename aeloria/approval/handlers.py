from datetime import datetime, timedelta, timezone
from pathlib import Path

from aeloria.db.client import Db

CAPTION_PROMPT_PREFIX = "Reply to this message with the new caption for queue:"


def handle_callback(data: str, db: Db) -> tuple[str, str | None]:
    action, _, queue_id = data.partition(":")
    if action == "approve":
        db.update("queue", queue_id, {"approval": "approved"})
        return "✅ Approved", None
    if action == "reject":
        db.update("queue", queue_id, {"approval": "rejected", "reject_reason": "manual reject"})
        return "❌ Rejected", None
    if action == "regen":
        rows = db.select("queue", {"id": queue_id}, limit=1)
        if not rows:
            return "⚠️ queue row not found", None
        db.update("queue", queue_id, {"approval": "rejected", "reject_reason": "regen requested"})
        if rows[0].get("brief_id"):
            db.update("briefs", rows[0]["brief_id"], {"status": "planned"})
        return "🔁 Regen queued", None
    if action == "caption":
        return "✏️ Send new caption", f"{CAPTION_PROMPT_PREFIX} {queue_id}"
    if action == "engapprove":
        db.update("engagements", queue_id, {"approval": "approved"})
        return "✅ Approved", None
    if action == "engreject":
        db.update("engagements", queue_id, {"approval": "rejected"})
        return "❌ Rejected", None
    return f"unknown action: {action}", None


def handle_photo_command(text: str, tg) -> str:
    """`/photo <scene>` — generate a single PRO_PHOTOGRAPHY image and preview it via Telegram.

    Tries local ComfyUI + trained Aeloria LoRA first (zero API cost).
    Falls back to FAL Flux API if ComfyUI is unavailable.
    """
    scene = text.split(maxsplit=1)[1].strip() if len(text.split(maxsplit=1)) > 1 else ""
    if not scene:
        return "Usage: /photo <scene>\ne.g. /photo Aeloria at a Parisian café, morning light"

    from aeloria.config import get_settings
    s = get_settings()

    # ── Try local ComfyUI + LoRA first ──
    try:
        from aeloria.generation.comfy_client import generate_image_comfy, check_comfyui_ready
        from aeloria.generation.post_processor import (
            auto_wb_exposure, selective_sharpen, film_grain, vignette,
        )
        import random

        if check_comfyui_ready():
            lora_name = "aeloria_sdxl_v1.safetensors"

            # Rich SD1.5 prompt using visual_dna from persona — SD1.5 needs detailed prompts
            from aeloria.persona.loader import load_persona
            persona = load_persona()
            vd = persona.visual_dna
            trigger = "aeloria woman"
            prompt = (
                f"RAW photo, {trigger}, young woman in her mid-twenties, slender build, "
                f"{vd['hair']}, {vd['eyes']}, {vd['skin']}, "
                f"a warm half-smile, looking toward camera, "
                f"{scene}, wearing {vd['wardrobe']}, "
                f"85mm f/1.4 lens, Kodak Portra 400, shallow depth of field, "
                f"soft directional sunlight, natural skin texture, no makeup, "
                f"photorealistic, highly detailed face"
            )
            negative = (
                "ai-generated, CGI, 3d render, illustration, anime, cartoon, drawing, "
                "blurry, low resolution, pixelated, noisy, "
                "oversaturated, artificial skin, plastic skin, wax, mannequin, smooth skin, "
                "airbrushed, beauty filter, soft focus, "
                "distorted face, deformed hands, bad anatomy, extra limbs, "
                "asymmetric eyes, cross-eyed, duplicate face, "
                "watermark, text overlay, signature, frame, border, logo"
            )

            img = generate_image_comfy(
                prompt=prompt,
                negative_prompt=negative,
                seed=random.randint(0, 2**32),
                steps=30,
                cfg=8.0,
                sampler="euler_ancestral",
                lora_path=lora_name,
                lora_strength=0.85,
                width=832,
                height=1216,
                ckpt_name="Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
            )

            # Post-process
            img = auto_wb_exposure(img, strength=0.40)
            img = selective_sharpen(img, amount=1.3, radius=0.8, threshold=3)
            img = film_grain(img, intensity=0.12)
            img = vignette(img, strength=0.20)

            import io
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=95)
            image_bytes = buf.getvalue()

            caption = f"📸 ComfyUI SD1.5 + Aeloria LoRA (local, $0)\n{scene[:200]}"
            ok = tg.send_photo_data(image_bytes, caption)
            if not ok:
                return "❌ Telegram send failed"
            return f"✅ generated locally ({len(image_bytes)//1024} KB, $0.00)"
    except Exception as e:
        # Fall through to FAL
        pass

    # ── Fallback: FAL Flux API with realistic prompt engine ──
    from aeloria.generation.fal_images import generate_image
    from aeloria.generation.fal_router import WorkflowType
    from aeloria.generation.realistic_prompt_engine import build_realistic_prompt
    from aeloria.generation.post_processor import (
        auto_wb_exposure, selective_sharpen, film_grain, vignette,
    )
    from PIL import Image
    import io

    try:
        # Build ultra-realistic prompt using the anti-plastic engine
        positive, negative = build_realistic_prompt(scene, seed=random.randint(0, 2**32))
        
        import fal_client, httpx
        os.environ["FAL_KEY"] = s.fal_key
        
        arguments = {
            "prompt": positive,
            "guidance_scale": 3.5,
            "num_inference_steps": 40,
            "image_size": "portrait_16_9",
            "seed": random.randint(0, 2**32),
            "loras": [{"path": s.aeloria_lora_url, "scale": 0.7}],
            "num_images": 1,
            "enable_safety_checker": False,
        }
        
        result = fal_client.subscribe("fal-ai/flux-lora", arguments=arguments)
        img_url = result["images"][0]["url"]
        img_data = httpx.get(img_url, timeout=300).content
        
        # Post-process: WB + sharpen + grain + vignette
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        img = auto_wb_exposure(img, strength=0.35)
        img = selective_sharpen(img, amount=1.2, radius=0.8, threshold=3)
        img = film_grain(img, intensity=0.10)
        img = vignette(img, strength=0.15)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        image_bytes = buf.getvalue()
        
        caption = f"📸 Aeloria (FAL Flux + LoRA + realistic engine)\n{scene[:200]}"
        ok = tg.send_photo_data(image_bytes, caption)
        if not ok:
            return "❌ Telegram send failed"
        return f"✅ generated ({len(image_bytes)//1024} KB, $0.05)"
    except Exception as e:
        return f"❌ generation failed: {e}"


def handle_caption_reply(replied_text: str, new_caption: str, db: Db) -> str:
    if not replied_text.startswith(CAPTION_PROMPT_PREFIX):
        return ""
    queue_id = replied_text.removeprefix(CAPTION_PROMPT_PREFIX).strip()
    db.update("queue", queue_id, {"caption": new_caption})
    return "✏️ Caption updated"


def handle_edit_command(text: str, db, tg=None) -> str:
    """`/edit <queue_id> <instruction>` — outfit/scene edit of an existing post's
    image via flux-kontext (identity-safe). Queues the result as a new pending
    post and previews it in Telegram. Deps are built lazily to keep bot startup light."""
    parts = text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].strip() or not parts[2].strip():
        return ("Usage: /edit <queue_id> <instruction>\n"
                "e.g. /edit 1a2b… change her jacket to a red leather moto jacket")
    queue_id, instruction = parts[1].strip(), parts[2].strip()

    from aeloria.config import get_settings
    from aeloria.generation.edit import EditError, edit_queued_post
    from aeloria.generation.face_gate import load_reference
    from aeloria.storage.r2 import R2

    s = get_settings()
    try:
        ref = load_reference(s.face_ref_path)
    except Exception:
        ref = None
    try:
        res = edit_queued_post(queue_id, instruction, db, s, R2(), ref_embedding=ref, tg=tg)
    except EditError as e:
        return f"❌ edit failed: {e}"
    sim = res.get("face_similarity")
    return f"✏️ edit queued as {res['queue_id']}" + (f" (face_sim {sim:.2f})" if sim is not None else "")


TREND_TTL_DAYS = 7
_VALID_KINDS = ("audio", "format", "hashtag")
_TREND_HELP = (
    "Usage:\n"
    "/trend add <audio|format|hashtag> <ref> | <note>\n"
    "/trend list\n"
    "/trend expire <id>"
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def handle_trend_command(text: str, db) -> str:
    parts = text.split(maxsplit=3)
    # parts: ["/trend", sub, ...]
    if len(parts) < 2:
        return _TREND_HELP
    sub = parts[1].lower()
    if sub == "add":
        if len(parts) < 4:
            return _TREND_HELP
        kind = parts[2].lower()
        if kind not in _VALID_KINDS:
            return _TREND_HELP
        rest = parts[3]
        if "|" not in rest:
            return _TREND_HELP
        ref, note = (s.strip() for s in rest.split("|", 1))
        if not ref:
            return _TREND_HELP
        db.insert("trends", {
            "platform": "instagram",
            "kind": kind, "ref": ref, "note": note,
            "expires_at": (datetime.now(timezone.utc) + timedelta(days=TREND_TTL_DAYS)).isoformat(),
        })
        return f"✅ added {kind} trend: {ref}"
    if sub == "list":
        rows = db.select("trends")
        now = datetime.now(timezone.utc)
        active = []
        for r in rows:
            exp = r.get("expires_at")
            if exp:
                try:
                    e = datetime.fromisoformat(str(exp))
                    if e.tzinfo is None:
                        e = e.replace(tzinfo=timezone.utc)
                    if e < now:
                        continue
                except ValueError:
                    pass
            active.append(r)
        if not active:
            return "no active trends"
        # Row ids included so `/trend expire <id>` is usable from the listing.
        lines = [f"- {r.get('id', '?')} [{r['kind']}] {r['ref']} — {r.get('note', '')}"
                 for r in active]
        return "active trends:\n" + "\n".join(lines)
    if sub == "expire":
        if len(parts) < 3:
            return _TREND_HELP
        tid = parts[2]
        db.update("trends", tid, {"expires_at": _now_iso()})
        return f"✅ expired trend {tid}"
    return _TREND_HELP
