import pytest


REQUIRED_ENV = {
    "SUPABASE_URL": "https://x.supabase.co",
    "SUPABASE_SERVICE_KEY": "sk-test",
    "R2_ACCOUNT_ID": "acct",
    "R2_ACCESS_KEY_ID": "key",
    "R2_SECRET_ACCESS_KEY": "secret",
    "R2_PUBLIC_BASE_URL": "https://pub-x.r2.dev",
    "FAL_KEY": "fal-test",
}


def _set_env(monkeypatch):
    for k, v in REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)


def test_settings_loads_from_env(monkeypatch):
    _set_env(monkeypatch)
    from aeloria.config import Settings

    s = Settings(_env_file=None)
    assert s.supabase_url == "https://x.supabase.co"
    assert s.r2_bucket == "ig-media"
    assert s.fal_daily_usd_cap == 2.50
    assert s.higgsfield_daily_credits_cap == 15.0
    assert s.higgsfield_soul_id == "d94858ae-ea6e-48c7-89e0-7fc8083f2d0f"


def test_settings_missing_required_raises(monkeypatch):
    for k in REQUIRED_ENV:
        monkeypatch.delenv(k, raising=False)
    from aeloria.config import Settings

    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_phase2_settings_defaults(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("FACE_GATE_THRESHOLD", raising=False)
    monkeypatch.delenv("FACE_REF_PATH", raising=False)
    monkeypatch.delenv("REALISM_LORA_URL", raising=False)
    monkeypatch.delenv("REALISM_LORA_SCALE", raising=False)
    from aeloria.config import Settings

    s = Settings(_env_file=None)
    assert s.telegram_bot_token == ""
    assert s.telegram_chat_id == ""
    assert s.face_gate_threshold == 0.35
    assert s.face_ref_path == "aeloria/persona/face_ref.json"
    # Image base model defaults to Juggernaut FLUX (photoreal skin, Flux.1).
    assert s.image_model == "rundiffusion-fal/juggernaut-flux-lora"
    assert s.image_inference_steps == 30
    # Skin-realism LoRA disabled by default (Juggernaut is natively realistic).
    assert s.realism_lora_url.endswith("flux-RealismLora/resolve/main/lora.safetensors")
    assert s.realism_lora_scale == 0.45
    assert s.aeloria_lora_scale == 0.7
    assert s.image_guidance_scale == 1.9


def test_refine_defaults():
    from aeloria.config import get_settings
    s = get_settings()
    assert s.refine_enabled is True
    assert s.refine_model == "fal-ai/clarity-upscaler"
    assert 0.0 <= s.refine_creativity <= 1.0 and 0.0 <= s.refine_resemblance <= 1.0
    assert s.refine_upscale_factor >= 1


def test_realism_lora_kill_switch(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.setenv("REALISM_LORA_URL", "")
    from aeloria.config import Settings

    s = Settings(_env_file=None)
    assert s.realism_lora_url == ""  # empty → worker skips stacking


def test_deploy_settings_defaults(monkeypatch):
    _set_env(monkeypatch)
    monkeypatch.delenv("API_SECRET_KEY", raising=False)
    monkeypatch.delenv("WORKER_INTERVAL_MINUTES", raising=False)
    from aeloria.config import Settings

    s = Settings(_env_file=None)
    assert s.api_secret_key == ""
    assert s.worker_interval_minutes == 10


def test_publish_settings_defaults(monkeypatch):
    _set_env(monkeypatch)
    for k in ("META_APP_ID", "META_APP_SECRET", "IG_USER_ID",
             "PUBLISH_INTERVAL_MINUTES", "PUBLISH_JITTER_MINUTES",
             "MIN_FOLLOWERS_FOR_STORIES", "PUBLISH_DRY_RUN", "GRAPH_BASE"):
        monkeypatch.delenv(k, raising=False)
    from aeloria.config import Settings
    s = Settings(_env_file=None)
    assert s.meta_app_id == ""
    assert s.meta_app_secret == ""
    assert s.ig_user_id == ""
    assert s.graph_base == "https://graph.facebook.com/v23.0"
    assert s.publish_interval_minutes == 10
    assert s.publish_jitter_minutes == 20
    assert s.min_followers_for_stories == 5000
    assert s.publish_dry_run is False


def test_engagement_defaults(monkeypatch):
    _set_env(monkeypatch)
    from aeloria.config import Settings

    s = Settings(_env_file=None)
    assert s.engagement_interval_minutes == 30
    assert s.engagement_outbound_daily_cap == 3
    assert s.engagement_recent_days == 3


def test_optimizer_defaults(monkeypatch):
    _set_env(monkeypatch)
    from aeloria.config import Settings
    s = Settings(_env_file=None)
    assert s.optimizer_interval_minutes == 1440
    assert s.optimizer_baseline_days == 14
    assert s.optimizer_max_weight_delta == 0.20
    assert s.optimizer_min_posts == 10
