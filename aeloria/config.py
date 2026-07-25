from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str
    supabase_service_key: str

    r2_account_id: str
    r2_access_key_id: str
    r2_secret_access_key: str
    r2_bucket: str = "ig-media"
    r2_public_base_url: str

    fal_key: str
    aeloria_lora_url: str = "https://v3b.fal.media/files/b/0aa395a4/NmA-BW5lft984mV-yD4K9_pytorch_lora_weights.safetensors"
    # Image base model. Juggernaut FLUX (RunDiffusion) is a Flux.1 finetune tuned
    # for photoreal skin (no plastic/wax look) — our Flux.1 identity LoRA plugs
    # straight in. Flip back to "fal-ai/flux-general" to restore the old stack.
    image_model: str = "rundiffusion-fal/juggernaut-flux-lora"
    image_inference_steps: int = 30
    # Raw-realism tuning (anti-plastic): identity LoRA below 1.0 so it stops
    # over-fitting into a waxy look; guidance below flux's 3.5 to kill artificial
    # rim light / harsh contrast; XLabs flux-realism LoRA stacked lightly beneath.
    aeloria_lora_scale: float = 0.7
    image_guidance_scale: float = 1.9
    # Post-gen realism refinement (Phase 2): upscale + skin/texture pass on every
    # image via a fal detail-upscaler, tuned low-creativity/high-resemblance so it
    # adds micro-texture without changing the face. Re-gated after (upscalers drift).
    refine_enabled: bool = True
    refine_model: str = "fal-ai/clarity-upscaler"
    refine_upscale_factor: int = 2
    refine_creativity: float = 0.3
    refine_resemblance: float = 0.8
    refine_cost_usd: float = 0.05  # verified 2026-07-23: clarity-upscaler + data-URI work; sim 0.73->0.68 (held), 219KB->4.18MB
    # XLabs flux-realism LoRA (resolvable safetensors URL). Empty = kill switch.
    realism_lora_url: str = "https://huggingface.co/XLabs-AI/flux-RealismLora/resolve/main/lora.safetensors"
    realism_lora_scale: float = 0.45
    # Identity lock: IP-Adapter reference conditioning. ONLY sent to
    # fal-ai/flux-general (Juggernaut has no ip_adapters param); identity there
    # rests on the scale-1.0 LoRA. Empty ref url = kill switch.
    ip_adapter_ref_image_url: str = ""
    ip_adapter_scale: float = 0.7
    ip_adapter_path: str = "InstantX/FLUX.1-dev-IP-Adapter"
    ip_adapter_image_encoder_path: str = "google/siglip-so400m-patch14-384"

    # Video (Phase 3b): fal Kling image-to-video animates the identity-locked
    # hero still. video_gate_frame_seconds = late-frame probe for the video
    # face-gate (drift -> retry, MAX_ATTEMPTS=2). The flat "kling-image-to-video"
    # slug was retired by fal; Kling now lives under fal-ai/kling-video/<ver>.
    kling_model: str = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
    kling_video_cost_usd: float = 0.35  # budget estimate for 2.5-turbo/pro 5s
    kling_video_duration: int = 5       # fal wants this as a "5"/"10" string
    video_gate_frame_seconds: float = 4.0

    anthropic_api_key: str = ""
    briefing_enabled: bool = False  # opt-in Haiku briefing enrichment (else deterministic)
    # Seamless transparency: rely on the bio disclosure + Meta's native post-level AI
    # label rather than a per-post footer (which breaks immersion). Set True to restore.
    caption_ai_disclosure: bool = False
    # Telegram getUpdates long-poll seconds. Lower on networks that reset a held
    # 30s idle connection (proxies/sandboxes) so each poll returns before the reset.
    telegram_poll_timeout: int = 25

    fal_daily_usd_cap: float = 2.50
    higgsfield_daily_credits_cap: float = 15.0
    higgsfield_soul_id: str = "d94858ae-ea6e-48c7-89e0-7fc8083f2d0f"

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    face_gate_threshold: float = 0.35
    face_ref_path: str = "aeloria/persona/face_ref.json"

    # ── Video engines ─────────────────────────────────────────
    kling_api_key: str = ""
    wan_api_key: str = ""

    # ── Vellum AI skin micro-texture upscaler ─────────────────
    vellum_api_key: str = ""

    # ── Fanvue publishing ──────────────────────────────────────
    fanvue_api_key: str = ""

    # ── C2PA / IPTC 2025.1 compliance signing ─────────────────
    c2pa_cert_path: str = ""
    c2pa_private_key_path: str = ""

    # Deploy (S0): Bearer token for /trigger/* endpoints; empty disables them.
    api_secret_key: str = ""
    # run_pending cadence in minutes (idle run_pending costs $0 — safe to run often).
    worker_interval_minutes: int = 10

    # S1: Instagram publishing via Meta Graph API. Empty meta_app_id/ig_user_id
    # disables publishing (the publish job logs + no-ops each cycle).
    meta_app_id: str = ""
    meta_app_secret: str = ""
    ig_user_id: str = ""
    graph_base: str = "https://graph.facebook.com/v23.0"
    publish_interval_minutes: int = 10
    publish_jitter_minutes: int = 20
    min_followers_for_stories: int = 5000
    publish_dry_run: bool = False
    # Phase 3a: distribution planner cadence. Idle planner costs $0 — safe to run often.
    distribution_interval_minutes: int = 10
    # Phase 4: showrunner (rule-based beat sheet). Idle run is a no-op once the
    # week is built, so a short interval + 7-day horizon keeps briefs seeded.
    showrunner_interval_minutes: int = 60
    showrunner_horizon_days: int = 7
    # Phase 5a: analytics (IG insights -> metrics + daily follower snapshot).
    # $0; hourly interval — snapshot-due logic filters to ~1-2 fetches/post/day.
    analytics_interval_minutes: int = 60
    stats_window_days: int = 7

    # Phase 6a: weekly content mix (10/wk). reel+carousel+static counts per week.
    showrunner_weekly_mix: dict[str, int] = {"reel": 5, "carousel": 3, "static": 2}

    carousel_default_slides: int = 4
    carousel_max_slides: int = 7

    # Phase 6b: engagement loop cadence + volume caps.
    engagement_interval_minutes: int = 30
    engagement_outbound_daily_cap: int = 3
    engagement_recent_days: int = 3

    # Phase 6c: optimizer (nightly scoring -> bounded strategy weights).
    optimizer_interval_minutes: int = 1440
    optimizer_baseline_days: int = 14
    optimizer_max_weight_delta: float = 0.20
    optimizer_min_posts: int = 10
    optimizer_analyst_enabled: bool = False  # opt-in Claude growth-analyst on the nightly memo
    # North-star staged by follower tier: discovery-first while small, then +engagement,
    # then +retention/monetization. Each entry: {min_followers, weights per metric}.
    optimizer_north_star_tiers: list = [
        {"min_followers": 0,     "weights": {"reach": 2, "saves": 3, "shares": 3, "comments": 1, "likes": 0}},
        {"min_followers": 1000,  "weights": {"reach": 2, "saves": 3, "shares": 3, "comments": 2, "likes": 1}},
        {"min_followers": 10000, "weights": {"reach": 1, "saves": 2, "shares": 2, "comments": 2, "likes": 1}},
    ]
    # Honest limits (Phase 5): below 1000 followers we optimize reach+saves+shares only
    # (discovery-first — likes weight 0). `non_follower_reach` is NOT captured: IG Graph
    # API v23.0 has no compatible insights breakdown for it, so we score on `reach` +
    # `saves`/`shares` rates instead (documented, not a bug). The growth-analyst
    # (optimizer/analyst.py) is opt-in (`optimizer_analyst_enabled`) and its weight
    # nudges are suggestions only, surfaced on the nightly memo for human review —
    # never auto-applied.


@lru_cache
def get_settings() -> Settings:
    return Settings()
