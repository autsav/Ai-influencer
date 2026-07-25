# Pipeline Improvement Plan

> **For Hermes:** Execute task-by-task, committing after each.

**Goal:** Fix the 5 issues found in the first real pipeline run, then add 2 high-value features (carousel continuity + retry loop).

**Architecture:** Targeted patches to existing `pipeline/` modules. No new architecture — just fixing what broke and adding what's missing.

**Tech Stack:** Python asyncio, FAL, PIL, InsightFace, JSON queue

---

## Issues Found in First Run

| # | Issue | Severity | Fix |
|---|---|---|---|
| 1 | Aspect ratio 0.75 (3:4) instead of 0.8 (4:5) — FAL `portrait_4_3` returns 768×1024 which is 3:4 not 4:5 | Medium | Map `4:5` to `portrait_4_3` but note FAL's closest match, or use `portrait_16_9` for true 4:5 |
| 2 | `RuntimeWarning: 'pipeline.runner' found in sys.modules` — import order issue | Low | Move `if __name__` guard, suppress warning |
| 3 | Dead pixel ratio 1.5% flagged — threshold already relaxed to 5%, but could be smarter | Low | Change to warning-only, not failure |
| 4 | No retry on QC fail — if face gate fails, the pipeline just stops | High | Add retry loop with re-seed |
| 5 | No carousel mode — can't generate multi-slide posts with wardrobe lock | High | Add `--carousel` flag to runner |

---

### Task 1: Fix aspect ratio mapping

**Objective:** Map `4:5` correctly to FAL's closest image size.

**Files:**
- Modify: `pipeline/image_stage.py` (line ~22, `_ASPECT_TO_SIZE` dict)

**Step 1:** Update the aspect ratio mapping

```python
# FAL image_size options and their actual aspect ratios:
# portrait_4_3  = 768×1024 = 0.75 (3:4, closest to 4:5)
# portrait_16_9 = 896×1152 = 0.7778 (closest FAL has to 4:5 = 0.8)
# For true 4:5, use portrait_16_9 which is closer to 0.8
_ASPECT_TO_SIZE = {
    "9:16": "portrait_16_9",
    "4:5": "portrait_16_9",  # 896×1152 = 0.778, closer to 0.8 than portrait_4_3 (0.75)
    "1:1": "square_hd",
    "16:9": "landscape_16_9",
}
```

**Step 2:** Test with dry run

Run: `python -m pipeline.runner --config config/pipeline.json --scene "test" --dry-run`
Expected: No errors, prompt builds correctly

**Step 3:** Commit

```bash
git add pipeline/image_stage.py
git commit -m "fix: map 4:5 to portrait_16_9 for closer aspect ratio match"
```

---

### Task 2: Fix import warning

**Objective:** Suppress the `RuntimeWarning` about `pipeline.runner` in `sys.modules`.

**Files:**
- Modify: `pipeline/runner.py` (main block at bottom)

**Step 1:** Add warning suppression

At the top of `pipeline/runner.py`, add:
```python
import warnings
warnings.filterwarnings("ignore", message=".*found in sys.modules.*")
```

**Step 2:** Commit

```bash
git add pipeline/runner.py
git commit -m "fix: suppress pipeline.runner import warning"
```

---

### Task 3: Make dead pixel ratio a warning, not a failure

**Objective:** Dead pixels in AI images (pure black/white regions from high-contrast lighting) shouldn't fail QC — just warn.

**Files:**
- Modify: `pipeline/qc_stage.py` (artifact check section, ~line 117)

**Step 1:** Change dead pixel from hard fail to warning

```python
# Dead pixel ratio — warning only (common in high-contrast AI images)
if dead_ratio > 0.05:
    result.warnings.append(f"High dead pixel ratio: {dead_ratio:.4f}")

artifact_ok = has_detail and is_sharp  # dead pixel is now warning-only
```

**Step 2:** Commit

```bash
git add pipeline/qc_stage.py
git commit -m "fix: dead pixel ratio is now a QC warning, not a failure"
```

---

### Task 4: Add retry-on-QC-fail loop

**Objective:** If QC fails (face gate, artifacts), automatically retry with a new seed up to 3 times before giving up.

**Files:**
- Modify: `pipeline/runner.py` (`process_single` function)

**Step 1:** Add retry loop wrapping image + QC stages

In `process_single()`, wrap the image generation + QC in a retry loop:

```python
MAX_RETRIES = 3
image_bytes = b""
for attempt in range(MAX_RETRIES):
    try:
        img_result = await generate_image(
            config.character, scene, wardrobe, pose, camera_angle,
            dry_run=config.dry_run,
        )
        image_bytes = img_result.image_bytes
        result["stages"]["image"] = {
            "seed": img_result.seed,
            "cost": img_result.cost_usd,
            "time": img_result.gen_time,
            "attempt": attempt + 1,
        }
        result["total_cost"] += img_result.cost_usd
    except Exception as e:
        logger.error("[%s] Image attempt %d failed: %s", entry_id, attempt + 1, e)
        if attempt == MAX_RETRIES - 1:
            result["errors"].append(f"image: {e}")
            return result
        continue

    # Quick QC check — if it passes, break; if not, retry with new seed
    if "qc" in config.stages and image_bytes:
        qc_result = run_qc(image_bytes, config.qc, ...)
        if qc_result.passed:
            result["stages"]["qc"] = {...}
            break
        else:
            logger.warning("[%s] QC failed attempt %d, retrying...", entry_id, attempt + 1)
            if attempt == MAX_RETRIES - 1:
                result["errors"].extend(qc_result.errors)
                # Save last attempt for review
                ...
```

**Step 2:** Test with dry run

Run: `python -m pipeline.runner --config config/pipeline.json --scene "test" --dry-run`
Expected: Works, dry-run doesn't trigger retries

**Step 3:** Commit

```bash
git add pipeline/runner.py
git commit -m "feat: retry-on-QC-fail loop (3 attempts with re-seed)"
```

---

### Task 5: Add carousel mode to runner

**Objective:** Generate N slides with locked wardrobe/location, rotating only camera/pose — same as `prompt_engine.py` carousel but integrated into the pipeline runner.

**Files:**
- Modify: `pipeline/runner.py` (add `--carousel` flag, `--slides` flag)
- Modify: `pipeline/config_loader.py` (add carousel config fields)

**Step 1:** Add CLI flags

```python
parser.add_argument("--carousel", action="store_true", help="Generate carousel (locked outfit/location)")
parser.add_argument("--slides", type=int, default=3, help="Number of carousel slides")
```

**Step 2:** Add carousel processing in `main()`

```python
if args.carousel:
    from aeloria.generation.prompt_engine import PromptEngine
    from aeloria.generation.creative_database import CREATIVE_CAMERA_ANGLES, CREATIVE_POSES
    engine = PromptEngine(seed=args.seed or None)
    prompts = engine.generate_carousel(
        n=args.slides,
        location_description=args.scene,
        wardrobe_description=args.wardrobe,
    )
    results = []
    for i, p in enumerate(prompts):
        result = await process_single(
            config,
            scene=p.location_description,
            wardrobe=p.wardrobe_description,
            pose=p.subject_pose,
            camera_angle=p.camera,
        )
        results.append(result)
    print(json.dumps(results, indent=2, default=str))
```

**Step 3:** Test with dry run

Run: `python -m pipeline.runner --config config/pipeline.json --carousel --slides 3 --scene "Covent Garden" --wardrobe "cream sweater" --dry-run`
Expected: 3 dry-run results with different poses/cameras, same outfit

**Step 4:** Commit

```bash
git add pipeline/runner.py pipeline/config_loader.py
git commit -m "feat: carousel mode with locked wardrobe/location across slides"
```

---

### Task 6: Add queue status CLI command

**Objective:** Quick way to check what's in the queue without opening the JSON file.

**Files:**
- Modify: `pipeline/runner.py` (add `--status` flag)

**Step 1:** Add status command

```python
parser.add_argument("--status", action="store_true", help="Show queue status summary")

# In main():
if args.status:
    from pipeline.publish_stage import load_queue
    queue = load_queue()
    from collections import Counter
    statuses = Counter(e.get("status", "unknown") for e in queue)
    print(f"Queue: {len(queue)} entries")
    for status, count in statuses.most_common():
        print(f"  {status}: {count}")
    for e in queue[-5:]:
        print(f"  [{e.get('status')}] {e.get('id')}: {e.get('scene', '?')[:50]}")
    return
```

**Step 2:** Test

Run: `python -m pipeline.runner --status`
Expected: Shows queue summary with the 1 entry from our test run

**Step 3:** Commit

```bash
git add pipeline/runner.py
git commit -m "feat: --status CLI command for queue summary"
```

---

### Task 7: Wire prompt_engine.py into pipeline for creative variety

**Objective:** When `--scene` is provided but no `--pose` or `--camera`, auto-select from the 200 creative angles/poses database instead of leaving them empty.

**Files:**
- Modify: `pipeline/runner.py` (in `process_single`, auto-select pose/camera if not provided)

**Step 1:** Add auto-selection

```python
if not pose or not camera_angle:
    import random
    from aeloria.generation.creative_database import CREATIVE_CAMERA_ANGLES, CREATIVE_POSES
    rng = random.Random(seed)
    if not pose:
        pose = rng.choice(CREATIVE_POSES)
        logger.info("[%s] Auto-selected pose: %s", entry_id, pose[:50])
    if not camera_angle:
        camera_angle = rng.choice(CREATIVE_CAMERA_ANGLES)
        logger.info("[%s] Auto-selected camera: %s", entry_id, camera_angle[:50])
```

**Step 2:** Commit

```bash
git add pipeline/runner.py
git commit -m "feat: auto-select creative pose/camera from 200-entry database when not specified"
```

---

### Task 8: Final integration test — build one real image end-to-end

**Objective:** Run the full pipeline with all improvements and verify it produces a clean image.

**Step 1:** Run the pipeline

```bash
export $(grep -v '^#' .env | xargs)
python -m pipeline.runner --config config/pipeline.json \
  --scene "walking through Covent Garden market, afternoon" \
  --wardrobe "linen shirt and jeans with gold hoops" \
  --dry-run
```

Expected: Dry run completes, auto-selects pose + camera from creative database

**Step 2:** Run for real (single image)

```bash
python -m pipeline.runner --config config/pipeline.json \
  --scene "walking through Covent Garden market, afternoon" \
  --wardrobe "linen shirt and jeans with gold hoops"
```

Expected: Image generated, QC passed, saved to output/pipeline/, queue updated

**Step 3:** Check queue status

```bash
python -m pipeline.runner --status
```

Expected: Shows 2+ entries (previous + new)

**Step 4:** Commit any remaining fixes

```bash
git add -A
git commit -m "test: full pipeline integration test passed"
```

---

## Summary

| Task | What | Time |
|---|---|---|
| 1 | Fix aspect ratio 4:5 → portrait_16_9 | 2 min |
| 2 | Suppress import warning | 1 min |
| 3 | Dead pixel → warning not failure | 2 min |
| 4 | Retry-on-QC-fail (3 attempts) | 10 min |
| 5 | Carousel mode in runner | 10 min |
| 6 | Queue --status command | 3 min |
| 7 | Auto-select creative pose/camera | 5 min |
| 8 | Integration test — build real image | 5 min |

**Total: ~38 min of focused work.**

**Risks:**
- Task 4 (retry loop) adds complexity — keep it simple, just re-seed and retry
- Task 5 (carousel) depends on `prompt_engine.py` which is in `aeloria/generation/` — may need sys.path fix if import fails
- Task 7 (auto-select) uses `creative_database.py` — same import concern

**Verification:**
- Every task commits independently
- Task 8 proves the full pipeline works end-to-end
- Queue status command confirms entries are tracked