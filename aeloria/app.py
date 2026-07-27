import asyncio
import logging
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from aeloria.analytics.runner import run_analytics_pending
from aeloria.approval.bot import supervise_bot
from aeloria.approval.telegram_api import Telegram
from aeloria.auth import token_store
from aeloria.compliance.c2pa_injector import inject_c2pa_metadata
from aeloria.config import get_settings
from aeloria.db.client import Db
from aeloria.engagement.dm_orchestrator import DMOrchestrator
from aeloria.engagement.reengagement_cron import ReengagementCron
from aeloria.engagement.runner import run_engagement_pending
from aeloria.generation.face_gate import load_reference
from aeloria.generation.pipeline import run_pending
from aeloria.generation.video_engine import generate_video
from aeloria.generation.vellum_upscaler import VellumUpscaler
from aeloria.optimizer.runner import run_optimizer_pending
from aeloria.persona.loader import load_persona
from aeloria.publishing.fanvue import FanvueClient, FanvuePost, PostType
from aeloria.scheduler import build_scheduler
from aeloria.showrunner.runner import run_showrunner_pending
from aeloria.stats import build_stats
from aeloria.storage.r2 import R2
from aeloria.training.kohya_flux import KohyaFluxTrainer

log = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


def _authorized(creds: HTTPAuthorizationCredentials | None, settings) -> bool:
    # compare_digest: constant-time compare, no timing side channel on the token.
    return (
        creds is not None
        and bool(settings.api_secret_key)
        and secrets.compare_digest(str(creds.credentials), str(settings.api_secret_key))
    )


def _build_runtime(settings):
    db = Db(settings)
    r2 = R2(settings)
    persona = load_persona()
    try:
        ref = load_reference(settings.face_ref_path)
    except FileNotFoundError:
        log.warning(
            "face_ref not found at %s — face gate disabled until provisioned; "
            "briefs will fail until then", settings.face_ref_path,
        )
        ref = None
    tg = None
    if settings.telegram_bot_token and settings.telegram_chat_id:
        tg = Telegram(settings.telegram_bot_token, settings.telegram_chat_id)
    return db, r2, persona, ref, tg


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    db, r2, persona, ref, tg = _build_runtime(settings)
    cred = db.get_credential("instagram")
    if cred:
        token_store.init(cred["access_token"])
    else:
        log.info("no instagram credential — token_store uninitialized, publishing will no-op")
    executor = ThreadPoolExecutor(max_workers=2)
    stop_event = threading.Event()
    bot_thread = threading.Thread(target=supervise_bot, args=(stop_event,), daemon=True)
    bot_thread.start()
    scheduler = build_scheduler(db, settings, r2, persona, ref, tg, executor)
    scheduler.start()
    app.state.db = db
    app.state.r2 = r2
    app.state.persona = persona
    app.state.ref = ref
    app.state.tg = tg
    app.state.executor = executor
    app.state.scheduler = scheduler
    app.state.bot_thread = bot_thread
    app.state.bot_stop_event = stop_event
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        stop_event.set()
        # Cancel queued jobs and stop accepting new submissions. An in-flight
        # fal generation is inherently uncancellable (blocking fal_client.subscribe);
        # Railway's SIGKILL grace window contains it until the async rewrite (S1+).
        executor.shutdown(wait=False, cancel_futures=True)


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    # Mount the new v1 API router
    from aeloria.api.v1.router import api_router
    app.include_router(api_router)

    @app.get("/health")
    async def health():
        sched = getattr(app.state, "scheduler", None)
        bot_thread = getattr(app.state, "bot_thread", None)
        return {
            "status": "ok",
            "scheduler_running": bool(sched and getattr(sched, "running", False)),
            "bot_running": bool(bot_thread and bot_thread.is_alive()),
        }

    @app.post("/trigger/run-pending")
    async def trigger_run_pending(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ):
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        loop = asyncio.get_running_loop()
        n = await loop.run_in_executor(
            app.state.executor, run_pending,
            app.state.db, settings, app.state.r2, app.state.persona,
            app.state.ref, app.state.tg,
        )
        return {"processed": n}

    @app.post("/trigger/showrunner")
    async def trigger_showrunner(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ):
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        loop = asyncio.get_running_loop()
        n = await loop.run_in_executor(
            app.state.executor, run_showrunner_pending,
            app.state.db, settings, app.state.persona,
        )
        return {"processed": n}

    @app.post("/trigger/analytics")
    async def trigger_analytics(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ):
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        loop = asyncio.get_running_loop()
        n = await loop.run_in_executor(
            app.state.executor, run_analytics_pending,
            app.state.db, settings,
        )
        return {"processed": n}

    @app.post("/trigger/engagement")
    async def trigger_engagement(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ):
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        loop = asyncio.get_running_loop()
        n = await loop.run_in_executor(
            app.state.executor, run_engagement_pending,
            app.state.db, settings, app.state.persona, app.state.tg,
        )
        return {"processed": n}

    @app.post("/trigger/optimizer")
    async def trigger_optimizer(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ):
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        loop = asyncio.get_running_loop()
        n = await loop.run_in_executor(
            app.state.executor, run_optimizer_pending,
            app.state.db, settings, app.state.persona, app.state.tg,
        )
        return {"processed": n}

    @app.post("/trigger/dm-orchestrator")
    async def trigger_dm_orchestrator(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ):
        """Poll inbound DMs, generate and send PPV-aware responses."""
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        orch = DMOrchestrator(settings)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(app.state.executor, orch.process_inbound)
        return result

    @app.post("/trigger/reengagement")
    async def trigger_reengagement(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ):
        """Send memory-based nudge DMs to inactive fans."""
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        cron = ReengagementCron(settings)
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(app.state.executor, cron.run)
        return result

    @app.post("/trigger/fanvue-post")
    async def trigger_fanvue_post(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
        post_type: str = "post",
        caption: str = "",
        media_urls: list[str] | None = None,
        price: float | None = None,
    ):
        """Create and publish a Fanvue post or PPV content."""
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        client = FanvueClient(settings)
        post = FanvuePost(
            post_type=PostType(post_type),
            caption=caption,
            media_urls=media_urls or [],
            price=price,
        )
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(app.state.executor, client.create_post, post)
        return result

    @app.post("/trigger/video-generate")
    async def trigger_video_generate(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
        image_url: str = "",
        prompt: str = "",
        engine: str = "kling",
        duration: int = 5,
    ):
        """
        Generate a short video from a face-verified hero still using the
        Image-to-Video Anchor Method (prompt = camera movement only).
        """
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        import httpx
        image_bytes = b""
        if image_url:
            with httpx.Client(timeout=30.0) as c:
                r = c.get(image_url)
                r.raise_for_status()
                image_bytes = r.content
        video_bytes = await asyncio.get_running_loop().run_in_executor(
            app.state.executor,
            lambda: generate_video(image_bytes, prompt, engine, settings, duration),
        )
        video_key = f"videos/{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        public_url = app.state.r2.upload(video_bytes, video_key, "video/mp4")
        return {"video_url": public_url}

    @app.post("/trigger/lora-train")
    async def trigger_lora_train(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
        dataset_config: str = "",
        output_name: str = "aeloria_lora",
        max_steps: int = 1500,
    ):
        """Launch a Kohya_ss FLUX.1 LoRA training run (background thread)."""
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        trainer = KohyaFluxTrainer(settings)
        from aeloria.training.kohya_flux import TrainingConfig
        cfg = TrainingConfig(max_train_steps=max_steps)
        run = trainer.start_training(dataset_config, output_name, cfg)
        return {"run_id": run.run_id, "status": run.status, "max_steps": run.max_steps}

    @app.get("/stats")
    async def stats(
        creds: HTTPAuthorizationCredentials | None = Security(_bearer),
    ):
        settings = get_settings()
        if not _authorized(creds, settings):
            raise HTTPException(status_code=401, detail="unauthorized")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            app.state.executor, build_stats, app.state.db, settings,
        )

    return app


app = create_app()
