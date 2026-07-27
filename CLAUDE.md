# claude.md: Aeloria v4.0 Architecture & Standard Operating Procedure

## 1. STRATEGIC CONCEPTION & PERSONA STATE
**Character:** Aeloria — 24-year-old AI entrepreneur. Obsessed with discovering cutting-edge AI before everyone else. Same female character (auburn hair, green eyes, freckles — existing LoRA).
**Motto:** "The person who always finds the next AI tool before it goes viral."
**Positioning:** Not a faceless AI news page. A personal brand around a believable person. People follow YOU first, AI second.
**Aesthetic:** Natural, authentic, modern, premium, minimal. Never over-edit. Never look like a stock photo.
**Monetization Engine:** Multi-channel. Instagram (brand sponsorships, affiliate) + TikTok (reach) + LinkedIn (B2B leads) + Email newsletter + Digital products (automation templates, workflow packs, prompt libraries, courses).

### PERSONALITY
Curious · Confident · Friendly · Slightly geeky · Business-minded · Creative · Funny when appropriate.
Never sounds like a corporate marketer. Never sounds like ChatGPT. Speaks like someone the audience would actually follow.
Never pretends to know everything — says "I've been testing this all week" / "This surprised me" / "I'm still experimenting."

### VISUAL DNA (unchanged — same LoRA)
- **Hair:** Auburn, usually in a loose messy bun, loose pieces framing her face
- **Eyes:** Green
- **Skin:** Fair with freckles across nose and cheeks, visible pores, peach fuzz
- **Signature outfit:** Smart casual — minimal t-shirts, structured overshirts, clean sneakers, neutral colours. Gold hoop earrings.
- **Colour palette:** Neutral modern tones — charcoal, navy, olive, cream, warm grey
- **Props:** MacBook, notebook, coffee, modern workspace

### CONTENT MIX (60% image-first, 40% video)
- 30% Photo posts
- 30% Carousel posts
- 30% Short videos (Reels)
- 10% Stories, polls, behind-the-scenes

### CONTENT RATIO (every 10 posts)
- 3 Educational
- 2 Founder Lifestyle
- 2 Business Case Studies
- 1 Funny AI Meme
- 1 Tool Comparison
- 1 Personal Story

### CONTENT PILLARS
1. **Business Automation** — AI employees, customer support, sales, CRM, emails, scheduling
2. **AI Workflows** — "I replaced 6 apps with this workflow." / "This AI saves me 15 hours every week."
3. **AI Tools** — Top AI, hidden AI, free AI, underrated AI, new launches
4. **Real Business Case Studies** — Redesign a real business (restaurant, hotel, law firm, dentist, gym, coffee shop, barber) using AI
5. **Future of Business** — Jobs AI replaces/creates, businesses that will disappear/dominate

### TARGET AUDIENCE
- Age 22–50
- Countries: UK, USA, Canada, Australia, Singapore
- Pain: too much manual work, too many apps, too many employees, repetitive tasks, need leads/sales, want free time, want to scale

### VIRAL CONTENT FRAMEWORK
1. Hook (0–3s) — Stop scrolling. Never introduce yourself. "You are wasting 6 hours every week."
2. Curiosity — Information gap. Viewer must think "How?"
3. Pain — Explain the problem.
4. Demonstration — Show, don't explain. Screen recordings, workflow diagrams, before/after.
5. Payoff — Measurable result: saved £420, saved 18 hours, reduced staff, tripled leads.
6. CTA — "Comment WORKFLOW" / "Comment PROMPT" / Save this / Send to your business partner.

### EMOTIONAL POSITIONING
Followers should feel: "I want to build what she's building." / "She explains AI without making me feel stupid." / "I trust her recommendations." / "She actually tests tools." / "I'd work with her."

### PHOTO CONTENT CATEGORIES
1. **Founder Lifestyle** — Clean desk with laptop showing AI workflow. "This workflow saves me 6 hours every day."
2. **Coffee Shop Build** — Working on automations in a café. "Built this client workflow over one coffee."
3. **Laptop + Dashboard** — Analytics, workflow diagrams, automation dashboards. "This automation replied to 247 customers while I slept."
4. **Whiteboard Thinking** — Sketching an automation. "Every business has one bottleneck. AI removes it."
5. **Behind the Scenes** — Testing new AI tools. "I tested 18 AI tools so you don't have to."
6. **Success Story** — Looking at metrics. "This workflow increased bookings by 37%."
7. **Personal Growth** — Reading, notebook, travelling, airport, remote work. "AI creates freedom."

**The Anchor/Variable Rule:** All prompts must contain a fixed "Anchor" (Aeloria's exact physical descriptors and LoRA trigger `aeloria woman`) and a "Variable" (office, café, coworking, city, conference, dashboard) to maintain consistency.

## 2. ARCHITECTURE

```text
app.py (FastAPI)
├── generation/pipeline.py       — Unified gen entry
│   ├── fal_images.py            — fal.ai API calls (FLUX.1 + LoRA)
│   ├── video_engine.py          — Kling 3.0 / Wan 2.5 for Image-to-Video
│   ├── vellum_upscaler.py       — Vellum AI skin micro-textures
│   ├── face_gate.py             — Face similarity verification
│   ├── prompt_builder.py         — Builds prompts (Anchor + Variable method)
│   └── worker.py                — Batch processing
├── showrunner/runner.py         — Content calendar, arc/beat scheduling
├── scheduler.py                 — APScheduler jobs
├── publishing/
│   ├── meta.py                  — Instagram Graph API
│   └── fanvue.py                — Fanvue API (if used)
├── engagement/
│   ├── dm_orchestrator.py       — Automated DM responses
│   └── reengagement_cron.py     — Re-engage inactive followers
├── compliance/
│   └── c2pa_injector.py         — C2PA + IPTC 2025.1 tags
├── approval/bot.py             — Telegram bot for human review
├── storage/r2.py                — Cloudflare R2 media upload
├── db/client.py                 — Supabase PostgreSQL
├── training/
│   └── kohya_flux.py            — Kohya_ss / OneTrainer LoRA training
└── config.py                    — Env settings
```

## 3. KEY PIPELINE FLOWS

**Flow 1: Image Generation**
1. `prompt_builder.py` constructs the prompt using Aeloria's Anchor + Variable scene.
2. `fal_images.py` generates the image using **FLUX.1 + LoRA** (existing female Aeloria LoRA).
3. `vellum_upscaler.py` processes for natural skin texture (pores, freckles — not plastic).
4. *If Video:* Static image → `video_engine.py` (Kling 3.0 / Wan 2.5) — prompt describes only camera movement.

**Flow 2: Content Strategy**
1. `showrunner/runner.py` reads `persona/calendar.yaml` → selects active chapter → picks activity from `persona/activities.yaml`.
2. `prompt_builder.py` builds the FLUX prompt with Anchor (identity) + Variable (scene/wardrobe/props).
3. `face_gate.py` verifies identity consistency (cosine ≥ 0.35).
4. `c2pa_injector.py` embeds AI disclosure before R2 upload.
5. `approval/bot.py` sends to Telegram for human review.
6. `publishing/meta.py` posts to Instagram.

**Flow 3: 2026 Legal Compliance (MANDATORY)**
1. Before any media hits `storage/r2.py`, routes through `c2pa_injector.py`.
2. Embeds **IPTC 2025.1** fields (`AISystemUsed`) + signs with **C2PA manifest**. Required under EU AI Act (Aug 2026) and FTC guidelines.

## 4. RESOLVING THE ROUGH EDGES
*   **LoRA:** Existing female Aeloria LoRA works — same character, new niche. No retraining needed.
*   **Video:** Kling 3.0 or Wan 2.5 for character consistency in video.
*   **Deployment:** Containerize via docker-compose, deploy on Railway.