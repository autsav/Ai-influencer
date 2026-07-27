# Aeloria — AI Influencer Pipeline

Automated end-to-end content generation platform for Aeloria, a 24-year-old AI entrepreneur character. Same LoRA, same face, new niche: AI automation for business owners.

Generation → QC + face consistency → C2PA compliance → R2 storage → publish (Instagram/Fanvue) → engagement → analytics feedback loop.

## Quick Start

```bash
# 1. Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env  # Add your API keys

# 3. Start backend (FastAPI + Celery workers + scheduler)
uvicorn aeloria.app:app --reload

# 4. Start frontend
cd web && npm install && npm run dev
```

## Architecture

Single live codebase in `aeloria/`. Legacy `pipeline/`, `src/`, root `config/`, `queue/` have been removed.

```
aeloria/
├── app.py                  # FastAPI entry: scheduler, bearer auth, runtime
├── pipeline_orchestrator.py # End-to-end orchestration
├── config.py / budget.py / stats.py / redact.py / llm_router.py
├── scheduler.py            # APScheduler jobs
├── api/v1/                 # REST API v1 (influencers, generations, jobs, uploads, health)
├── schemas/v1.py           # Pydantic v2 request/response models
├── generation/             # Image/video gen, prompt builder, face gate, upscaler, PuLID, carousel
├── workers/                # Celery tasks (image, video, caption, upscale)
├── core/                   # Celery + Redis config
├── persona/                # Character YAML (soul_id, cast, storylines, backstory, face_ref)
├── showrunner/             # Content calendar, arcs, beats, activities, briefing
├── publishing/             # Instagram Graph API + Fanvue
├── engagement/             # DM orchestrator, inbound/outbound, re-engagement cron
├── optimizer/              # Nightly scoring, strategy weights, memo, analyst
├── distribution/           # Planner, SEO, slots, collabs, trends, hooks
├── compliance/             # C2PA + IPTC 2025.1 injector
├── approval/               # Telegram review bot
├── training/               # Kohya/OneTrainer LoRA training
├── storage/r2.py           # Cloudflare R2 upload
├── db/client.py            # Supabase PostgreSQL
└── auth/                   # Token store + refresh

web/                        # Next.js + Tailwind + React Query frontend
scripts/                    # auto_tagger, smoke_generate, single_pose, kontext_pipeline
docs/                       # MASTER_SYSTEM_PROMPT, DAILY_BLUEPRINT, prompt architecture
tests/                      # 60+ pytest files
```

## Key Pipeline Flow

1. `showrunner/runner.py` reads `persona/*.yaml` → picks active chapter + activity
2. `generation/prompt_builder.py` builds FLUX prompt (Anchor = Aeloria identity + LoRA trigger, Variable = scene/wardrobe/props)
3. `generation/fal_images.py` generates via fal.ai FLUX.1 + LoRA; `generation/pulid.py` + `face_detailer.py` enforce face consistency
4. `generation/vellum_upscaler.py` adds natural skin micro-texture
5. `generation/face_gate.py` verifies identity (InsightFace cosine ≥ 0.35)
6. `compliance/c2pa_injector.py` embeds AI disclosure (EU AI Act + FTC)
7. `storage/r2.py` uploads media
8. `approval/bot.py` sends to Telegram for human review
9. `publishing/meta.py` posts to Instagram; `publishing/fanvue.py` to Fanvue
10. `optimizer/runner.py` runs nightly: scores posts, updates strategy weights

## API v1

Bearer-authenticated REST under `/api/v1`:
- `POST /generations` — create image/video/carousel job (Celery dispatched)
- `GET /jobs/{id}` — job status (PENDING → STARTED → COMPLETED/FAILED)
- `GET /influencers` — list characters
- `POST /uploads` — upload asset
- `GET /health` — service health

## Scripts

### Auto-Tagger (`scripts/auto_tagger.py`)
LoRA-ready captions for training dataset images.

```bash
python scripts/auto_tagger.py --input /path/to/dataset --trigger "aeloria woman"
python scripts/auto_tagger.py --input /path/to/dataset --trigger "aeloria woman" --backend ollama
python scripts/auto_tagger.py --input /path/to/dataset --dry-run
```

### Smoke Generate (`scripts/smoke_generate.py`)
End-to-end single-image generation test.

## Environment Variables (`.env`)

```
FAL_KEY=...
MINIMAX_API_KEY=...
ELEVENLABS_API_KEY=...
SYNCLABS_API_KEY=...
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_PUBLIC_BASE_URL=...
API_SECRET_KEY=...
```

## Logging

Pipeline ops log to `logs/pipeline.log` (rotating, 5MB × 3).

## Tests

```bash
pytest -q
```