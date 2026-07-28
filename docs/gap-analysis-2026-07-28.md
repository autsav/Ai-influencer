# Aeloria Pipeline — Gap Analysis & Upgrade Recommendations

**Date:** 2026-07-28  
**Method:** Brainstorming skill (Hermes Agent direct exploration)  
**Codebase:** `~/Documents/ai-influencer-v2/` — 8,044 Python files, ~450K LOC, 948 test files, Next.js web frontend

---

## 1. Current State Summary

### What Exists

Aeloria v4.0 is a **full-stack AI influencer pipeline** with impressive depth:

- **Two-pass identity consistency engine** (`consistency_pipeline.py`): PuLID face conditioning (Pass 1) + LoRA fallback + face detailer inpainting (Pass 2). Identity scores consistently 0.55-0.68 — well above the 0.35 gate.
- **10-layer FLUX prompt architecture** (`prompt_builder.py`, 410 lines): Deterministic per-brief hash picking from 3 signature styles (film_editorial, flash_candid, paparazzi_night) with wardrobe/pose/expression/prop/hair pools. City catalogue for London-specific shoots.
- **Content strategy system**: `showrunner/` with beat sheets, activities, calendar (360-day), storylines, series, signature segments. Distribution planner with slot scheduling. Hook validation gate.
- **Publishing**: Instagram Graph API (`meta.py`) — image, reel, story, carousel. 2-step container flow with retry. Fanvue publishing stub.
- **Engagement**: DM orchestrator for Fanvue (PPV sales loop). Re-engagement cron. LLM-powered reply drafter.
- **Analytics**: IG insights fetcher (reel/image metrics), follower snapshots, optimizer with north-star tier weights.
- **Infrastructure**: Celery + Redis + FastAPI v1 + Next.js 15 dashboard. R2 storage with presigned URLs. Supabase DB. Telegram approval bot.
- **Compliance**: C2PA/IPTC 2025.1 metadata injector (`c2pa_injector.py`).
- **LLM router**: MiniMax primary → Claude Code fallback. NO OLLAMA (hard user preference).
- **Training**: Kohya/OneTrainer LoRA training script.

### What Works Well

1. **Identity consistency** is production-grade. The PuLID + LoRA + face detailer chain produces reliable character lock across diverse scenes.
2. **Prompt engineering** is sophisticated — the deterministic hash-based style selection prevents repetitive outputs while maintaining brand coherence.
3. **Content strategy** is well-architected: calendar → beat sheet → brief → generation → approval → publish → analytics → optimize loop.
4. **Test coverage** is substantial (948 test files, 384+ passing).

---

## 2. Gap Analysis

### (a) Image Generation & Quality

| Gap | Impact |
|---|---|
| **No upscaling pipeline in production** | `vellum_upscaler.py` has a placeholder endpoint (`"placeholder; adjust to actual Vellum API"`). `refine.py` exists in worker imports but clarity-upscaler is configured in settings — unclear if active. Images ship at fal.ai resolution (~1024px) without 4K upscaling for print/zoom quality. |
| **No background removal / compositing** | Can't place Aeloria on custom backgrounds, product shots, or branded environments without full regeneration. No segmentation/masking pipeline (SAM exists as a Hermes skill but isn't integrated). |
| **No image-to-image editing** | Can't iteratively refine a generated image ("make the smile bigger", "change the jacket to blue") without full regeneration. `scripts/image_to_image.py` and `scripts/kontext_pipeline.py` exist but aren't wired into the main pipeline. |
| **No multi-persona support** | CLAUDE.md mentions "multi-persona roadmap" but the pipeline is hardwired for one character. The `aeloria_lora_url` is a single global setting. No persona switching, multi-LoRA stacking, or character roster. |
| **Video pipeline is thin** | `video_worker.py` is 17 lines — just a wrapper. No face-gate on video output, no lip-sync, no voice synthesis, no text overlay on reels. Kling i2v is configured but the video face-gate / overlay / retry loop lives in `worker.py` and may be incomplete. |
| **No audio / voice** | `audio_pipeline.py` and `render_pipeline.py` exist but no voice cloning, TTS, or lip-sync integration for reels. |

### (b) Identity Consistency

| Gap | Impact |
|---|---|
| **Single reference face** | Only `reference_face.jpg`. No multi-angle reference set. PuLID works best with diverse reference angles — using one image limits identity lock for extreme angles (profile, top-down). |
| **No identity drift detection across batches** | Each generation scores independently. No cumulative drift tracking — if LoRA output drifts over weeks (model updates, seed exhaustion), there's no alert. |
| **Face gate threshold is static** | 0.35 is a flat threshold. No adaptive threshold based on scene complexity, angle, or distance. Wide shots and motion-blur scenes routinely score lower but may still be good. |
| **No body consistency** | Only face is gated. Body shape, height, hand appearance, and skin tone on body (not face) are unchecked. LoRA handles this implicitly but there's no verification. |

### (c) Content Strategy & Automation

| Gap | Impact |
|---|---|
| **No trend-responsive content** | `trend_scraper.py` and `distribution/trends.py` exist but no integration with X/Twitter trends, Google Trends, Product Hunt, or Hacker News for real-time AI tool discovery content. Content calendar is pre-planned, not reactive. |
| **No A/B testing framework** | Can't test two captions, two images, or two hooks against each other. No champion/challenger system for optimization. |
| **No user-generated content (UGC) loop** | No mechanism to repost, remix, or respond to follower content. No mention/reply tracking. |
| **No content repurposing** | Each piece is generated for one platform. No automatic reformatting (IG post → TikTok → LinkedIn post → Twitter thread → newsletter). |
| **Carousel generation is hardcoded** | `templates/carousel_gen.py` is a standalone script, not integrated into the worker pipeline for automatic multi-slide generation. |

### (d) Distribution & Publishing

| Gap | Impact |
|---|---|
| **Instagram-only** | `meta.py` is the only working publisher. Fanvue is stubbed. No TikTok, LinkedIn, YouTube Shorts, or X/Twitter publishing. CLAUDE.md mentions multi-channel strategy but only IG is wired. |
| **No cross-platform optimization** | Same image/caption goes to IG. No platform-specific aspect ratios (TikTok 9:16, LinkedIn 1.91:1, X 16:9), no platform-specific caption tuning (hashtags for IG, none for LinkedIn, threads for X). |
| **No scheduling intelligence** | `distribution/slots.py` exists but scheduling is rule-based (fixed UTC hours). No optimal-time detection based on audience activity patterns. |
| **No Story/Reel native creation** | Stories and Reels use the same image pipeline. No Story-specific features: polls, quizzes, question stickers, countdown timers, music overlays. |

### (e) Infrastructure & Scalability

| Gap | Impact |
|---|---|
| **No Docker/deployment config** | CLAUDE.md says "containerize via docker-compose, deploy on Railway" but no Dockerfile, docker-compose.yml, or deployment scripts exist. Everything runs locally. |
| **No CI/CD** | No GitHub Actions, no automated test runs, no deploy on merge. Tests must be run manually. |
| **Celery + Redis not containerized** | Requires manual startup of 4 services (Redis, Celery, FastAPI, Next.js). No process manager, no health monitoring beyond the `/health` endpoint. |
| **No rate limiting / cost guardrails** | `budget.py` is imported in `worker.py` but no visible cost cap per day/week. fal.ai balance exhaustion is detected only on 403. No pre-flight balance check in the pipeline. |
| **No webhook ingress** | No inbound webhooks for IG comments, DMs, or mentions. All engagement is poll-based. |
| **Database is Supabase-only** | No local SQLite fallback for development. No migration system (Supabase manages schema). |

### (f) Compliance & Safety

| Gap | Impact |
|---|---|
| **C2PA not active** | `c2pa_injector.py` exists but `c2pa_cert_path` and `c2pa_private_key_path` are empty in config. No signing keys configured. All images ship unsigned. EU AI Act deadline: Aug 2026. |
| **No content moderation** | No automated check for brand-safety violations before publishing. `hard_rules` in YAML are not enforced programmatically. No NSFW filter, no hate speech filter. |
| **No age verification / platform policy checks** | No verification that content meets platform-specific TOS before publishing. |
| **Caption AI disclosure disabled** | `caption_ai_disclosure: bool = False` in config. Relies on bio disclosure + Meta's native label only. |

### (g) Analytics & Feedback Loop

| Gap | Impact |
|---|---|
| **No real-time performance tracking** | Analytics run hourly but no dashboard. No view of "today's posts → performance → optimization signal" in real-time. |
| **No competitor benchmarking** | No tracking of competitor influencer accounts, their content performance, or gap opportunities. |
| **No audience sentiment analysis** | Comments are fetched for DM replies but not analyzed for sentiment, recurring questions, or content requests. |
| **No hashtag performance tracking** | SEO module generates hashtags but doesn't track which hashtags drive reach. No hashtag rotation optimization. |
| **No growth funnel visualization** | No view of: impressions → reach → profile visits → follows → engagement. Only raw follower count and per-post metrics. |
| **Optimizer is nightly only** | `optimizer_interval_minutes: 1440` (24h). No real-time signal for viral posts (sudden spike detection → boost via story/repost). |

### (h) Monetization

| Gap | Impact |
|---|---|
| **No affiliate link tracking** | No system to generate, track, or attribute affiliate links mentioned in posts/captions. No revenue per post tracking. |
| **No brand deal pipeline** | `distribution/collabs.py` exists but no sponsor management, media kit generation, rate card, or outreach automation. |
| **No digital product store** | CLAUDE.md mentions "automation templates, workflow packs, prompt libraries, courses" but no storefront, no product creation, no delivery mechanism. |
| **No email newsletter** | No email list, no newsletter generation from weekly content, no conversion funnel from IG → email. |
| **No paid subscription tier** | No premium content gating, no Patreon/Fanvue subscription management beyond the stub. |

---

## 3. Upgrade Recommendations (Prioritized)

### P0 — Critical / Now

| # | Upgrade | Why | Effort | Touches |
|---|---|---|---|---|
| 1 | **Activate C2PA compliance** | EU AI Act enforcement starts Aug 2026. Generate signing keys, set `c2pa_cert_path` / `c2pa_private_key_path`, test the injector end-to-end. | Small (2h) | `config.py`, `c2pa_injector.py`, `.env` |
| 2 | **Docker + docker-compose** | Can't deploy without it. Create Dockerfile (Python), docker-compose.yml (FastAPI + Celery + Redis + Next.js), .dockerignore. | Medium (1d) | New: `Dockerfile`, `docker-compose.yml`, `web/Dockerfile` |
| 3 | **Pre-flight fal.ai balance check** | Add balance check before batch generation. Currently fails mid-batch on 403. | Small (1h) | `consistency_pipeline.py`, `worker.py` |
| 4 | **Image-to-image editing pipeline** | Wire `kontext_pipeline.py` / `image_to_image.py` into the main pipeline. Enables iterative refinement ("change jacket color", "bigger smile") without full regen — saves cost + time. | Medium (2d) | `generation/edit.py` (new), `worker.py`, `api/v1/endpoints/generations.py` |

### P1 — High / Next Sprint

| # | Upgrade | Why | Effort | Touches |
|---|---|---|---|---|
| 5 | **TikTok publishing** | Largest reach channel after IG. TikTok Research API or unofficial posting. Platform-specific 9:16 reformatting. | Medium (2d) | New: `publishing/tiktok.py`, `distribution/planner.py` |
| 6 | **Content repurposing engine** | Auto-reformat IG post → TikTok (9:16) → LinkedIn (1.91:1 + professional caption) → X thread → email newsletter. Multiplies each piece 4x. | Medium (3d) | New: `distribution/repurpose.py`, `caption.py` |
| 7 | **Video face-gate + lip-sync** | Reels need identity verification. Add face-gate on Kling output's last frame. Integrate lip-sync (Wav2Lip / SadTalker) for talking-head reels. | Large (1wk) | `video_worker.py`, `worker.py`, new: `generation/lipsync.py` |
| 8 | **Multi-reference face set** | Add 3-5 reference faces (different angles, distances). Rotate or average PuLID embeddings. Improves identity lock for extreme angles. | Small (3h) | `pulid.py`, `consistency_pipeline.py`, `persona/` |
| 9 | **GitHub Actions CI/CD** | Run tests on every PR, auto-deploy on merge to main. No more manual test runs. | Small (3h) | New: `.github/workflows/ci.yml` |
| 10 | **Cost guardrails** | Daily/weekly fal.ai spend cap. Budget tracker with alert at 80% threshold. Hard stop at 100%. | Small (3h) | `budget.py`, `config.py`, `worker.py` |

### P2 — Medium / Next Month

| # | Upgrade | Why | Effort | Touches |
|---|---|---|---|---|
| 11 | **Multi-persona support** | User is "building multi-persona AI content factory". Refactor: `aeloria_lora_url` → per-persona config. Persona registry YAML. LoRA switching at generation time. | Large (1wk) | `config.py`, `consistency_pipeline.py`, `persona/`, new: `persona/registry.py` |
| 12 | **Background removal + compositing** | SAM integration for subject isolation. Place Aeloria on branded backgrounds, product shots, event backdrops without full regen. | Medium (3d) | New: `generation/compositing.py`, integrate SAM skill |
| 13 | **Real-time viral spike detection** | Monitor insights hourly. If a post's engagement rate > 3x account median within 2h → auto-boost (repost to Story, push to other platforms). | Medium (2d) | `analytics/runner.py`, new: `analytics/spike_detector.py` |
| 14 | **Audience sentiment analysis** | Analyze IG comments for sentiment, recurring questions, content requests. Feed into optimizer + content calendar. | Medium (2d) | `engagement/`, new: `analytics/sentiment.py` |
| 15 | **Email newsletter + capture** | IG bio link → landing page → email capture → weekly newsletter auto-generated from that week's best posts. | Medium (3d) | New: `distribution/newsletter.py`, landing page |
| 16 | **A/B testing framework** | Generate 2 variants (different hooks/images). Publish variant A to 50% audience window, B to 50%. Score winner. Rotate champion. | Medium (2d) | `distribution/planner.py`, `worker.py`, `analytics/` |
| 17 | **Adaptive face gate threshold** | Score threshold adjusts based on scene type (wide shot → 0.25, closeup → 0.40). Reduces false rejects on valid wide shots. | Small (3h) | `face_gate.py`, `consistency_pipeline.py` |

### P3 — Nice-to-Have

| # | Upgrade | Why | Effort | Touches |
|---|---|---|---|---|
| 18 | **Brand deal pipeline** | Sponsor CRM, media kit auto-generation from analytics, rate card calculator based on reach/engagement. | Medium (3d) | `distribution/collabs.py`, new: `sponsor/` |
| 19 | **Digital product storefront** | Stripe checkout for prompt packs, workflow templates, courses. Auto-delivery on purchase. | Large (1wk) | New: `commerce/` module |
| 20 | **Competitor benchmarking** | Track 5-10 competitor influencers. Weekly report: their top posts, growth rate, content gaps we can exploit. | Medium (2d) | New: `analytics/competitors.py` |
| 21 | **Trend-responsive content** | Auto-detect trending AI tools (X, Product Hunt, HN). Generate same-day reactive content. Insert into calendar. | Medium (3d) | `trend_scraper.py`, `showrunner/`, `calendar.py` |
| 22 | **UGC / mention tracking** | Track mentions, repost UGC with Aeloria commentary. Community building. | Medium (2d) | `engagement/`, new: `engagement/ugc.py` |
| 23 | **Voice cloning for reels** | Clone a consistent voice for Aeloria. Use for talking-head reels, story narrations. | Large (1wk) | New: `generation/voice.py` |
| 24 | **Interactive Story builder** | Story-specific features: polls, quizzes, countdowns, music overlays, question stickers via Graph API. | Medium (2d) | `publishing/meta.py` |

---

## 4. Proposed Architecture Evolution

### Before (Current)

```
Persona YAMLs → Showrunner → Brief → Prompt Builder → FLUX+LoRA+PuLID
  → Face Gate → C2PA (inactive) → R2 → Instagram
  → Analytics (hourly) → Optimizer (nightly) → Memo

Infrastructure: Local dev (manual 4-service startup)
Video: Kling i2v (thin wrapper, no face-gate)
Channels: Instagram only
Compliance: C2PA code exists, not activated
```

### After (Target)

```
Persona Registry (multi-character) → Showrunner + Trend Engine
  → Brief → Prompt Builder → FLUX+LoRA+PuLID (multi-ref face set)
  → Face Gate (adaptive) → Image-to-Image Edit (iterative)
  → Upscale (4K) → SAM Compositing (branded bg)
  → C2PA Signing (active) → R2
  → Repurpose Engine → IG / TikTok / LinkedIn / X / Email
  → Analytics (real-time + spike detection + sentiment)
  → Optimizer (real-time + A/B testing)
  → Monetization (affiliate, brand deals, storefront)

Video: Kling i2v → Video Face-Gate → Lip-Sync → Voice Clone → Reel
Infrastructure: Docker → Railway → CI/CD (GitHub Actions)
Compliance: C2PA active, content moderation, brand-safety enforcement
```

### Key Architectural Shifts

1. **One-to-many personas**: Single `aeloria_lora_url` → `persona/registry.yaml` with per-character LoRA, reference faces, and visual DNA.
2. **Linear-to-iterative generation**: Generate → edit → refine without full regen (image-to-image).
3. **Single-to-multi-channel**: One IG publisher → channel-agnostic distribution with platform-specific formatting.
4. **Reactive content**: Pre-planned calendar → trend-responsive insertion (same-day content for viral AI tools).
5. **Manual-to-automated ops**: Local dev → Docker → CI/CD → Railway auto-deploy.
6. **Passive-to-active analytics**: Nightly memo → real-time spike detection + sentiment + A/B testing.
7. **Cost-uncontrolled-to-guardrailed**: No spend cap → daily/weekly budget with alerts + hard stops.