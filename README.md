# Aeloria — AI Influencer Pipeline

Automated end-to-end content generation pipeline for AI influencer accounts.
Image generation → voice/lip-sync → QC validation → publish queue → analytics feedback loop.

## Quick Start

```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env  # Add your API keys

# 3. Run a single generation
python -m pipeline.runner --config config/pipeline.json --scene "sitting at a London café, morning light"

# 4. Dry run (no API calls, logs only)
python -m pipeline.runner --config config/pipeline.json --scene "walking through Covent Garden" --dry-run
```

## Pipeline Stages

```
JSON Config → Image Generation (FAL Flux LoRA) → Post-Processing (PIL)
            → QC Validation (dimensions + artifacts + face gate)
            → Publish Queue (queue/scheduled_prompts.json)
            → [Optional: Voice (ElevenLabs) + Lip-Sync (SyncLabs/Hedra)]
```

### Stage 1: Image Generation (`pipeline/image_stage.py`)
- FAL Flux LoRA with character identity (scale 0.7, guidance 3.5, 40 steps)
- PIL post-processing: WB correction + sharpen + vignette (zero API cost)
- Async execution via `asyncio` + `run_in_executor`

### Stage 2: QC Validation (`pipeline/qc_stage.py`)
Automated quality checks before publishing:
- **Dimensions**: minimum 512×512
- **File size**: max 20MB
- **Aspect ratio**: matches expected (4:5 default)
- **Artifact detection**: Laplacian variance (blur), solid color regions, dead pixel ratio
- **Face gate**: InsightFace cosine similarity to character reference (threshold 0.35)

### Stage 3: Voice & Lip-Sync (`pipeline/voice_stage.py`)
- ElevenLabs TTS (primary) with configurable voice ID, stability, similarity
- SyncLabs lip-sync (image + audio → talking video)
- Hedra lip-sync (placeholder — implement when API key available)

### Stage 4: Publish Queue (`pipeline/publish_stage.py`)
- All generated content goes to `queue/scheduled_prompts.json`
- Status tracking: `pending → generating → qc_passed → qc_failed → published`
- Queue can be processed in batch: `python -m pipeline.runner --queue`

## Scripts

### Auto-Tagger (`scripts/auto_tagger.py`)
Generates detailed .txt captions for LoRA training dataset images.

```bash
# Tag all images in a directory using Moondream2 (FAL, $0.005/image)
python scripts/auto_tagger.py --input /path/to/dataset --trigger "aeloria woman"

# Use local Qwen2.5-VL via Ollama (free, ~12GB RAM)
python scripts/auto_tagger.py --input /path/to/dataset --trigger "aeloria woman" --backend ollama

# Dry run (list files only)
python scripts/auto_tagger.py --input /path/to/dataset --dry-run
```

Each image gets a `<filename>.txt` with a LoRA-ready caption containing:
- Trigger token at the start
- Physical appearance, pose, expression, wardrobe, setting, lighting, camera
- Training suffix: "photorealistic, detailed skin texture, natural lighting"

### Analytics Feedback Loop (`scripts/analytics_loop.py`)
Reads performance metrics, LLM analyzes top posts, generates new content ideas → queue.

```bash
# Analyze JSON metrics and add 5 new ideas to queue
python scripts/analytics_loop.py --metrics data/performance.json --top-n 10 --ideas 5

# CSV input
python scripts/analytics_loop.py --metrics data/performance.csv --top-n 5

# Dry run (analyze without adding to queue)
python scripts/analytics_loop.py --metrics data/performance.json --dry-run
```

Expected metrics format (CSV or JSON array):
```json
[
  {"scene": "café morning", "wardrobe": "knit sweater", "pose": "sitting", 
   "views": 12000, "likes": 850, "comments": 45, "saves": 120, "shares": 30}
]
```

The LLM (via `aeloria.llm_router`: MiniMax → Claude Code) analyzes patterns and outputs
content ideas with predicted engagement levels and rationale, added directly to the queue.

## CLI Usage

### Single Generation
```bash
python -m pipeline.runner \
  --config config/pipeline.json \
  --scene "sitting at a London café, morning light" \
  --wardrobe "cream knit sweater and jeans" \
  --pose "hands around a coffee cup, warm half-smile" \
  --camera "eye-level 50mm, shallow DOF"
```

### With Voice
```bash
python -m pipeline.runner \
  --config config/pipeline.json \
  --scene "walking through Hyde Park" \
  --voice "A beautiful morning in the park..."
```

### Process Queue
```bash
# Process all pending entries
python -m pipeline.runner --config config/pipeline.json --queue
```

### Dry Run
```bash
python -m pipeline.runner --config config/pipeline.json --scene "test scene" --dry-run
```

## Configuration

### `config/pipeline.json`
Full pipeline config — character identity, voice settings, QC thresholds, stages.

### `config/character.json`
Character-only config — can be loaded separately for prompt generation.

### Environment Variables (`.env`)
```
FAL_KEY=your-fal-key
ELEVENLABS_API_KEY=your-elevenlabs-key
SYNCLABS_API_KEY=your-synclabs-key
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_PUBLIC_BASE_URL=...
```

## Logging

All pipeline operations log to `logs/pipeline.log` (rotating, 5MB × 3 files).
Dry-run mode logs to console only.

## Project Structure

```
pipeline/
├── __init__.py          # Package exports
├── config_loader.py     # JSON config loading + validation
├── image_stage.py       # Async FAL Flux LoRA generation + post-processing
├── voice_stage.py       # Async ElevenLabs TTS + SyncLabs/Hedra lip-sync
├── qc_stage.py          # Automated QC: dimensions, artifacts, face gate
├── publish_stage.py     # Queue management (queue/scheduled_prompts.json)
└── runner.py            # Async orchestrator with error handling + dry-run

scripts/
├── auto_tagger.py       # Auto-caption dataset images for LoRA training
├── analytics_loop.py    # LLM feedback loop: metrics → ideas → queue
└── train_character_lora/  # LoRA training scripts

config/
├── character.json       # Character identity config
└── pipeline.json        # Full pipeline config

queue/
└── scheduled_prompts.json   # Content queue with status tracking

logs/
└── pipeline.log         # Rotating pipeline log

aeloria/                 # Core influencer platform (FastAPI app, publishing, engagement)
├── generation/          # Image/video generation, prompt engines, post-processing
├── persona/             # Character YAML configs
├── publishing/          # Instagram + Fanvue publishing
├── engagement/          # DM orchestration, re-engagement
├── showrunner/          # Content calendar, beat sheets, storylines
├── optimizer/           # Nightly scoring + strategy weights
└── compliance/          # C2PA legal compliance
```