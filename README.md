# AI Influencer Platform — Setup Guide

**Stack:** FastAPI · Supabase free · Cloudflare R2 free · fal.ai · Meta Graph API · Railway $5
**Estimated monthly cost: ~$20–22**

---

## 1. Clone & install

```bash
git clone <your-repo>
cd ai-influencer
pip install -r requirements.txt
cp .env.example .env
```

---

## 2. Supabase (free tier)

1. Create project at [supabase.com](https://supabase.com)
2. SQL editor → paste + run `bootstrap.sql`
3. Edit the seed INSERT values (face_reference_urls, core_prompt_base)
4. Copy `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` → `.env`
5. Copy the generated `character_profiles.id` UUID → `CHARACTER_ID` in `.env`

---

## 3. Cloudflare R2

1. [dash.cloudflare.com](https://dash.cloudflare.com) → R2 → Create bucket → name: `ig-media`
2. Bucket → Settings → **Public Access → Allow Access**
3. Copy the `r2.dev` public URL → `R2_PUBLIC_BASE_URL` in `.env`
4. R2 → Manage R2 API Tokens → Create token (Object Read & Write)
5. Copy Account ID + Access Key + Secret → `.env`

> **Upload your character reference face images to R2 first**, copy their public URLs,
> then paste them into the `face_reference_urls` array in `bootstrap.sql` before seeding.

---

## 4. fal.ai

1. [fal.ai](https://fal.ai) → sign up → API Keys → create key
2. Paste → `FAL_KEY` in `.env`

---

## 5. Meta Graph API

1. [developers.facebook.com](https://developers.facebook.com) → create app → add Instagram product
2. Get a **short-lived token** → exchange for **long-lived token** (60 days):
   ```
   GET https://graph.facebook.com/v23.0/oauth/access_token
     ?grant_type=fb_exchange_token
     &client_id=APP_ID
     &client_secret=APP_SECRET
     &fb_exchange_token=SHORT_LIVED_TOKEN
   ```
3. Paste long-lived token → `META_LONG_LIVED_TOKEN` in `.env`
4. Get IG User ID:
   ```
   GET https://graph.facebook.com/v23.0/me/accounts?access_token=TOKEN
   ```
   Then: `GET /v23.0/{page_id}?fields=instagram_business_account&access_token=TOKEN`
5. Paste → `IG_USER_ID` in `.env`

---

## 6. Anthropic

1. [console.anthropic.com](https://console.anthropic.com) → API Keys → create
2. Paste → `ANTHROPIC_API_KEY` in `.env`

---

## 7. Test locally

```bash
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000/health — verify scheduler shows all jobs with next_run times.

**Test each stage:**
```bash
# 1. Generate one batch (creates 3 queue rows)
curl -X POST http://localhost:8000/trigger/generate

# 2. Publish image
curl -X POST http://localhost:8000/trigger/publish/image

# 3. Check metrics
curl -X POST http://localhost:8000/trigger/metrics

# 4. Run optimizer (needs >3 published posts with analytics)
curl -X POST http://localhost:8000/trigger/optimize
```

---

## 8. Deploy to Railway

```bash
# Install Railway CLI
npm install -g @railway/cli

railway login
railway init          # link to new project
railway up            # deploy

# Set env vars
railway variables set FAL_KEY=xxx SUPABASE_URL=xxx ...
```

Or paste all `.env` values in Railway Dashboard → Variables.

Railway auto-detects `railway.toml` and runs:
```
uvicorn main:app --host 0.0.0.0 --port $PORT
```

---

## File structure

```
ai-influencer/
├── main.py                         # FastAPI app + scheduler start
├── requirements.txt
├── railway.toml                    # Railway deploy config
├── bootstrap.sql                   # Run once in Supabase SQL editor
├── .env.example
└── src/
    ├── config.py                   # All settings (Pydantic)
    ├── db/client.py                # All Supabase reads/writes
    ├── generation/
    │   ├── fal_client.py           # Flux 2 Pro (images) + Wan 2.6 (video)
    │   ├── prompt_builder.py       # Assembles prompts from style_weights
    │   └── caption.py              # Claude Haiku caption generator
    ├── storage/r2.py               # Cloudflare R2 upload
    ├── publishing/meta.py          # Meta 3-step container flow + insights
    ├── scheduler/
    │   ├── jobs.py                 # APScheduler cron timings
    │   └── orchestrator.py        # Generate + publish + metrics logic
    ├── optimization/optimizer.py  # Nightly LLM feedback loop
    └── auth/token_refresh.py      # Meta 60-day token auto-refresh
```

---

## Monthly cost at 3 posts/day

| Service | Cost |
|---|---|
| fal.ai images (180/mo × ~$0.04) | ~$7 |
| fal.ai video — Wan 2.6 (30 × 5s × $0.05) | ~$7.50 |
| Supabase free tier | $0 |
| Cloudflare R2 free tier (10 GB, free egress) | $0 |
| Railway Hobby | $5 |
| Anthropic (Haiku captions + Sonnet optimizer) | ~$1.50 |
| **Total** | **~$21/month** |
