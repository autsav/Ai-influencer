"""Pipeline runner — orchestrates all stages asynchronously with error handling and logging.

Usage:
    python -m pipeline.runner --config config/pipeline.json
    python -m pipeline.runner --config config/pipeline.json --dry-run
    python -m pipeline.runner --queue   # process all pending queue entries
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
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


def setup_logging(log_file: str = "logs/pipeline.log", dry_run: bool = False):
    """Configure logging to file + console."""
    os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [
        logging.StreamHandler(sys.stdout),
    ]
    if not dry_run:
        from logging.handlers import RotatingFileHandler
        handlers.append(
            RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        )
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)


async def process_single(
    config: PipelineConfig,
    scene: str,
    wardrobe: str = "",
    pose: str = "",
    camera_angle: str = "",
    voice_script: str = "",
) -> dict:
    """Process a single content request through all enabled stages."""
    entry_id = f"post_{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    result = {
        "id": entry_id,
        "scene": scene,
        "stages": {},
        "total_cost": 0.0,
        "total_time": 0.0,
        "errors": [],
    }

    # ── Stage 1: Image Generation ───────────────────────────────────────────
    if "image" in config.stages:
        logger.info("[%s] Stage 1: Image generation", entry_id)
        try:
            img_result = await generate_image(
                config.character, scene, wardrobe, pose, camera_angle,
                dry_run=config.dry_run,
            )
            result["stages"]["image"] = {
                "seed": img_result.seed,
                "cost": img_result.cost_usd,
                "time": img_result.gen_time,
                "params": img_result.params,
            }
            result["total_cost"] += img_result.cost_usd
            image_bytes = img_result.image_bytes
        except Exception as e:
            logger.error("[%s] Image stage failed: %s", entry_id, e)
            result["errors"].append(f"image: {e}")
            return result
    else:
        image_bytes = b""

    # ── Stage 2: Voice Generation (optional) ────────────────────────────────
    if "voice" in config.stages and voice_script:
        logger.info("[%s] Stage 2: Voice generation", entry_id)
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

            # Lip-sync if enabled
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

    # ── Stage 3: Quality Control ────────────────────────────────────────────
    if "qc" in config.stages and image_bytes:
        logger.info("[%s] Stage 3: QC validation", entry_id)
        try:
            face_ref = os.environ.get("FACE_REF_PATH", "aeloria/persona/face_ref.json")
            qc_result = run_qc(
                image_bytes, config.qc,
                face_ref_path=face_ref if os.path.exists(face_ref) else "",
                dry_run=config.dry_run,
            )
            result["stages"]["qc"] = {
                "passed": qc_result.passed,
                "errors": qc_result.errors,
                "warnings": qc_result.warnings,
                "checks": qc_result.checks,
            }
            if not qc_result.passed:
                logger.warning("[%s] QC FAILED — not publishing", entry_id)
                result["errors"].extend(qc_result.errors)
                return result
        except Exception as e:
            logger.error("[%s] QC stage failed: %s", entry_id, e)
            result["errors"].append(f"qc: {e}")

    # ── Stage 4: Publish ────────────────────────────────────────────────────
    if "publish" in config.stages and image_bytes and not config.dry_run:
        logger.info("[%s] Stage 4: Saving to queue", entry_id)
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


def main():
    parser = argparse.ArgumentParser(description="AI Influencer Pipeline Runner")
    parser.add_argument("--config", "-c", default="config/pipeline.json",
                        help="Path to pipeline JSON config")
    parser.add_argument("--scene", "-s", help="Scene description for single generation")
    parser.add_argument("--wardrobe", "-w", default="", help="Wardrobe override")
    parser.add_argument("--pose", "-p", default="", help="Pose description")
    parser.add_argument("--camera", default="", help="Camera angle/composition")
    parser.add_argument("--voice", default="", help="Voice script text (enables voice stage)")
    parser.add_argument("--queue", "-q", action="store_true",
                        help="Process all pending queue entries")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls, log only")
    args = parser.parse_args()

    config = load_pipeline_config(args.config)
    if args.dry_run:
        config.dry_run = True

    setup_logging(config.log_file, dry_run=config.dry_run)
    logger.info("Pipeline starting (dry_run=%s, stages=%s)", config.dry_run, config.stages)

    if args.queue:
        results = asyncio.run(process_queue(config))
        print(json.dumps(results, indent=2, default=str))
    elif args.scene:
        result = asyncio.run(process_single(
            config, args.scene, args.wardrobe, args.pose, args.camera, args.voice
        ))
        print(json.dumps(result, indent=2, default=str))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()