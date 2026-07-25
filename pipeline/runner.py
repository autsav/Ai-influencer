"""Pipeline runner — orchestrates all stages asynchronously with error handling and logging.

Usage:
    python -m pipeline.runner --config config/pipeline.json --scene "café morning light"
    python -m pipeline.runner --config config/pipeline.json --carousel --slides 3 --scene "Covent Garden" --wardrobe "cream sweater"
    python -m pipeline.runner --queue   # process all pending queue entries
    python -m pipeline.runner --status  # show queue summary
    python -m pipeline.runner --config config/pipeline.json --dry-run
"""
from __future__ import annotations

import warnings
warnings.filterwarnings("ignore", message=".*found in sys.modules.*")

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pipeline.config_loader import (
    CharacterConfig,
    PipelineConfig,
    load_pipeline_config,
)
from pipeline.image_stage import generate_image, ImageResult
from pipeline.qc_stage import run_qc, QCResult
from pipeline.publish_stage import (
    QueueEntry,
    add_entry,
    get_pending,
    load_queue,
    save_image,
    save_queue,
    update_entry,
)
from pipeline.voice_stage import generate_voice, generate_lip_sync

logger = logging.getLogger("pipeline")

MAX_RETRIES = 3


def setup_logging(log_file: str = "logs/pipeline.log", dry_run: bool = False):
    """Configure logging to file + console."""
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    if not dry_run:
        from logging.handlers import RotatingFileHandler
        handlers.append(
            RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        )
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


def auto_select_creative(pose: str, camera_angle: str, seed: int | None = None) -> tuple[str, str]:
    """Auto-select pose and camera from the 200-entry creative database."""
    try:
        from aeloria.generation.creative_database import CREATIVE_CAMERA_ANGLES, CREATIVE_POSES
        rng = random.Random(seed)
        if not pose:
            pose = rng.choice(CREATIVE_POSES)
            logger.info("Auto-selected pose: %s", pose[:60])
        if not camera_angle:
            camera_angle = rng.choice(CREATIVE_CAMERA_ANGLES)
            logger.info("Auto-selected camera: %s", camera_angle[:60])
    except ImportError:
        logger.warning("creative_database not available — using empty pose/camera")
    return pose, camera_angle


async def process_single(
    config: PipelineConfig,
    scene: str,
    wardrobe: str = "",
    pose: str = "",
    camera_angle: str = "",
    voice_script: str = "",
    seed: int | None = None,
) -> dict:
    """Process a single content request through all enabled stages.
    Retries image generation + QC up to MAX_RETRIES times with re-seed on failure.
    """
    # Auto-select creative pose/camera if not provided
    pose, camera_angle = auto_select_creative(pose, camera_angle, seed)

    entry_id = f"post_{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    result = {
        "id": entry_id,
        "scene": scene,
        "wardrobe": wardrobe,
        "pose": pose,
        "camera_angle": camera_angle,
        "stages": {},
        "total_cost": 0.0,
        "total_time": 0.0,
        "errors": [],
    }

    image_bytes = b""

    # ── Stage 1+3: Image Generation + QC (with retry loop) ─────────────────
    if "image" in config.stages:
        face_ref = os.environ.get("FACE_REF_PATH", "aeloria/persona/face_ref.json")
        face_ref_path = face_ref if os.path.exists(face_ref) else ""

        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("[%s] Image attempt %d/%d", entry_id, attempt, MAX_RETRIES)
            try:
                img_result = await generate_image(
                    config.character, scene, wardrobe, pose, camera_angle,
                    seed=seed if attempt == 1 else None,  # re-seed on retry
                    dry_run=config.dry_run,
                )
                image_bytes = img_result.image_bytes
                result["stages"]["image"] = {
                    "seed": img_result.seed,
                    "cost": img_result.cost_usd,
                    "time": img_result.gen_time,
                    "attempt": attempt,
                    "params": img_result.params,
                }
                result["total_cost"] += img_result.cost_usd
            except Exception as e:
                logger.error("[%s] Image attempt %d failed: %s", entry_id, attempt, e)
                if attempt == MAX_RETRIES:
                    result["errors"].append(f"image: {e}")
                    return result
                continue

            # Quick QC check
            if "qc" in config.stages and image_bytes and not config.dry_run:
                logger.info("[%s] QC check (attempt %d)", entry_id, attempt)
                try:
                    qc_result = run_qc(
                        image_bytes, config.qc,
                        face_ref_path=face_ref_path,
                        dry_run=config.dry_run,
                    )
                    result["stages"]["qc"] = {
                        "passed": qc_result.passed,
                        "errors": qc_result.errors,
                        "warnings": qc_result.warnings,
                        "checks": qc_result.checks,
                        "attempt": attempt,
                    }
                    if qc_result.passed:
                        logger.info("[%s] QC passed on attempt %d", entry_id, attempt)
                        break
                    else:
                        logger.warning("[%s] QC failed attempt %d: %s",
                                        entry_id, attempt, qc_result.errors)
                        if attempt == MAX_RETRIES:
                            result["errors"].extend(qc_result.errors)
                            # Save last attempt for manual review
                            img_path = save_image(entry_id, image_bytes, config.output_dir)
                            result["stages"]["publish"] = {"image_path": img_path, "qc_failed": True}
                            logger.info("[%s] Last attempt saved for review: %s", entry_id, img_path)
                            result["total_time"] = round(time.time() - t0, 2)
                            return result
                except Exception as e:
                    logger.error("[%s] QC error attempt %d: %s", entry_id, attempt, e)
                    if attempt == MAX_RETRIES:
                        result["errors"].append(f"qc: {e}")
                        return result
            else:
                break  # no QC stage or dry run

    # ── Stage 2: Voice Generation (optional) ────────────────────────────────
    if "voice" in config.stages and voice_script:
        logger.info("[%s] Voice generation", entry_id)
        try:
            voice_result = await generate_voice(
                voice_script, config.voice,
                output_path=f"output/pipeline/{entry_id}_voice.mp3",
                dry_run=config.dry_run,
            )
            result["stages"]["voice"] = {
                "cost": voice_result.cost_usd,
                "time": voice_result.gen_time,
                "path": voice_result.audio_path,
            }
            result["total_cost"] += voice_result.cost_usd

            if config.voice.enable_lip_sync and image_bytes and voice_result.audio_bytes:
                video_path = await generate_lip_sync(
                    image_bytes, voice_result.audio_bytes, config.voice,
                    output_path=f"output/pipeline/{entry_id}_lipsync.mp4",
                    dry_run=config.dry_run,
                )
                if video_path:
                    result["stages"]["lip_sync"] = {"path": video_path}
        except Exception as e:
            logger.error("[%s] Voice stage failed: %s", entry_id, e)
            result["errors"].append(f"voice: {e}")

    # ── Stage 4: Publish ────────────────────────────────────────────────────
    if "publish" in config.stages and image_bytes and not config.dry_run:
        logger.info("[%s] Publishing to queue", entry_id)
        img_path = save_image(entry_id, image_bytes, config.output_dir)
        entry = QueueEntry(
            id=entry_id,
            prompt=result.get("stages", {}).get("image", {}).get("params", {}).get("prompt", scene),
            scene=scene,
            wardrobe=wardrobe,
            pose=pose,
            camera_angle=camera_angle,
            status="qc_passed",
            image_path=img_path,
            seed=result.get("stages", {}).get("image", {}).get("seed", 0),
            cost_usd=result["total_cost"],
        )
        add_entry(entry)
        result["stages"]["publish"] = {"image_path": img_path, "queue_id": entry_id}

    result["total_time"] = round(time.time() - t0, 2)
    logger.info("[%s] Complete: %.1fs, $%.4f, %d stages, %d errors",
                entry_id, result["total_time"], result["total_cost"],
                len(result["stages"]), len(result["errors"]))
    return result


async def process_carousel(
    config: PipelineConfig,
    scene: str,
    wardrobe: str,
    slides: int,
    seed: int | None = None,
) -> list[dict]:
    """Generate a carousel: same outfit + location, rotating pose/camera/lighting."""
    logger.info("Carousel mode: %d slides, scene=%s, wardrobe=%s", slides, scene[:50], wardrobe[:50])
    results = []
    for i in range(slides):
        logger.info("Carousel slide %d/%d", i + 1, slides)
        result = await process_single(
            config,
            scene=scene,
            wardrobe=wardrobe,
            seed=seed + i if seed else None,
        )
        result["carousel_slide"] = i + 1
        results.append(result)
    return results


async def process_queue(config: PipelineConfig) -> list[dict]:
    """Process all pending entries in the queue."""
    pending = get_pending()
    if not pending:
        logger.info("No pending queue entries")
        return []

    logger.info("Processing %d pending queue entries", len(pending))
    results = []
    for entry in pending:
        update_entry(entry["id"], {"status": "generating"})
        result = await process_single(
            config,
            scene=entry.get("scene", ""),
            wardrobe=entry.get("wardrobe", ""),
            pose=entry.get("pose", ""),
            camera_angle=entry.get("camera_angle", ""),
            voice_script=entry.get("voice_script", ""),
        )
        if result["errors"]:
            update_entry(entry["id"], {"status": "qc_failed", "errors": result["errors"]})
        else:
            update_entry(entry["id"], {
                "status": "published",
                "image_path": result.get("stages", {}).get("publish", {}).get("image_path", ""),
                "seed": result.get("stages", {}).get("image", {}).get("seed", 0),
            })
        results.append(result)
    return results


def show_queue_status() -> None:
    """Print queue status summary."""
    from collections import Counter
    queue = load_queue()
    statuses = Counter(e.get("status", "unknown") for e in queue)
    print(f"Queue: {len(queue)} entries")
    for status, count in statuses.most_common():
        print(f"  {status}: {count}")
    print()
    for e in queue[-5:]:
        print(f"  [{e.get('status', '?')}] {e.get('id', '?')}: {e.get('scene', '?')[:50]}")


def main():
    parser = argparse.ArgumentParser(description="AI Influencer Pipeline Runner")
    parser.add_argument("--config", "-c", default="config/pipeline.json",
                        help="Path to pipeline JSON config")
    parser.add_argument("--scene", "-s", help="Scene description for single generation")
    parser.add_argument("--wardrobe", "-w", default="", help="Wardrobe override")
    parser.add_argument("--pose", "-p", default="", help="Pose description (auto-selected if empty)")
    parser.add_argument("--camera", default="", help="Camera angle (auto-selected if empty)")
    parser.add_argument("--voice", default="", help="Voice script text (enables voice stage)")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    parser.add_argument("--queue", "-q", action="store_true",
                        help="Process all pending queue entries")
    parser.add_argument("--status", action="store_true",
                        help="Show queue status summary")
    parser.add_argument("--carousel", action="store_true",
                        help="Generate carousel (locked outfit/location, rotating pose/camera)")
    parser.add_argument("--slides", type=int, default=3,
                        help="Number of carousel slides (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, log only")
    args = parser.parse_args()

    if args.status:
        show_queue_status()
        return

    config = load_pipeline_config(args.config)
    if args.dry_run:
        config.dry_run = True

    setup_logging(config.log_file, dry_run=config.dry_run)
    logger.info("Pipeline starting (dry_run=%s, stages=%s)", config.dry_run, config.stages)

    if args.carousel and args.scene:
        results = asyncio.run(process_carousel(
            config, args.scene, args.wardrobe, args.slides, args.seed
        ))
        print(json.dumps(results, indent=2, default=str))
    elif args.queue:
        results = asyncio.run(process_queue(config))
        print(json.dumps(results, indent=2, default=str))
    elif args.scene:
        result = asyncio.run(process_single(
            config, args.scene, args.wardrobe, args.pose, args.camera, args.voice, args.seed
        ))
        print(json.dumps(result, indent=2, default=str))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()