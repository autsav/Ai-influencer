# claude.md: Aeloria v2.0 Architecture & Standard Operating Procedure

## 1. STRATEGIC CONCEPTION & PERSONA STATE
**Character:** Aeloria — 24-year-old virtual wellness/nature influencer. 
**Monetization Engine:** Multi-channel. Instagram (Brand sponsorships) + Fanvue (Subscription & Pay-Per-View DMs).
**The Anchor/Variable Rule:** All prompts must contain a fixed "Anchor" (Aeloria's exact physical descriptors and LoRA trigger) and a "Variable" (forest life, slow living outfits) to maintain mathematical consistency across the generation pipeline.

## 2. ARCHITECTURE UPGRADES (The "Aitana" Playbook)

```text
app.py (FastAPI)
├── generation/pipeline.py       — Unified gen entry 
│   ├── fal_images.py            — fal.ai API calls (FLUX.1 + IPAdapter FaceID + ControlNet triad)
│   ├── video_engine.py          — [NEW] Kling 3.0 / Wan 2.5 API for Image-to-Video Anchor method
│   ├── vellum_upscaler.py        — [NEW] Vellum AI integration for biological skin micro-textures
│   ├── face_gate.py              — Face similarity verification
│   ├── prompt_builder.py         — Builds prompts (Anchor + Variable method)
│   └── worker.py                 — Batch processing
├── showrunner/runner.py          — Arc/beat scheduling, content calendar
├── scheduler.py                  — APScheduler jobs
├── publishing/
│   ├── meta.py                  — Instagram Graph API carousel/post
│   └── fanvue.py                — [NEW] Fanvue API publishing integration
├── engagement/                  
│   ├── dm_orchestrator.py        — [UPGRADED] n8n + Supabase + LLM (Gemini/Claude) for automated PPV sales
│   └── reengagement_cron.py     — [NEW] Queries Supabase for inactive fans to send memory-based nudges
├── compliance/                   — [NEW MODULE FOR 2026]
│   └── c2pa_injector.py          — Embeds IPTC 2025.1 tags & C2PA cryptographics before R2 upload
├── approval/bot.py              — Telegram bot for human review
├── storage/r2.py                 — Cloudflare R2 media upload
├── db/client.py                  — Supabase PostgreSQL (Persona State + Fan Purchase Memory)
├── training/                     — [REPLACES HERMES]
│   └── kohya_flux.py            — Kohya_ss / OneTrainer scripts for localized FLUX.1 LoRA updates
└── config.py                     — Env settings
```

## 3. KEY PIPELINE FLOWS (Upgraded)

**Flow 1: Hyper-Realistic Generation (Image & Video)**
1. `prompt_builder.py` constructs the prompt using Aeloria's Anchor + Variable scene.
2. `fal_images.py` generates the image using **FLUX.1 + IPAdapter FaceID + ControlNet** to force the exact anatomical pose and facial identity.
3. `vellum_upscaler.py` processes the raw output to rebuild natural skin pores, micro-tonal variations, and biological textures (fixing the "plastic" AI look).
4. *If Video:* The upscaled static image is passed to `video_engine.py` (Kling 3.0 or Wan 2.5) using the **Image-to-Video Anchor Method**. The prompt describes *only* camera movement (e.g., "slow orbit, wind blowing"), completely omitting Aeloria's physical description to prevent identity drift.

**Flow 2: Engagement & The Automated DM "Printer"**
1. `dm_orchestrator.py` polls inbound Fanvue/IG DMs.
2. The workflow queries `Supabase` for the user's full conversation history and **Pay-Per-View (PPV) purchase record**.
3. The LLM (Gemini Flash/Claude) generates a response that remembers past chats, waits for a natural opening, and pitches exclusive PPV content without ever offering content the fan already owns.
4. `reengagement_cron.py` automatically messages fans who haven't spoken in days, referencing a past conversation to pull them back into the monetization funnel.

**Flow 3: 2026 Legal Compliance (MANDATORY)**
1. Before any media hits `storage/r2.py`, it routes through `c2pa_injector.py`.
2. The system embeds **IPTC 2025.1** fields (`AISystemUsed`) and signs the asset with a **C2PA cryptographic manifest**. This legally protects the platform under the EU AI Act (effective Aug 2026) and FTC guidelines, preventing massive fines or shadowbans from Meta/TikTok.

## 4. RESOLVING THE ROUGH EDGES
*   **Hermes Photo Trainer:** Deprecate the unintegrated root-level output. Standardize local training using Kohya's `sd-scripts` or OneTrainer for FLUX.1 LoRAs, which require 15-30 images and easily achieve consistency in ~1,500 steps.
*   **Higgsfield Engine:** Replace missing Higgsfield references with Kling 3.0 API or Wan 2.5 API, which currently lead the industry in maintaining character consistency during video generation.
*   **TS/Python Hybrid:** Containerize the `src/` TypeScript fal.ai router and the Python backend using `docker-compose`. Create a `requirements.txt` for the Python environment and build deployment docs using Railway's GitHub integration.
