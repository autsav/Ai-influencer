import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aeloria.analytics.runner import run_analytics_pending
from aeloria.distribution.runner import run_distribution_pending
from aeloria.engagement.runner import run_engagement_pending
from aeloria.generation.pipeline import run_pending
from aeloria.optimizer.runner import run_optimizer_pending
from aeloria.publishing.runner import publish_pending
from aeloria.showrunner.runner import run_showrunner_pending

log = logging.getLogger(__name__)


def make_run_pending_job(db, settings, r2, persona, ref, tg, executor):
    async def _run_pending_job():
        try:
            await asyncio.get_running_loop().run_in_executor(
                executor, run_pending, db, settings, r2, persona, ref, tg)
        except Exception:
            log.exception("run_pending job failed")
    return _run_pending_job


def make_publish_pending_job(db, settings, tg, executor):
    async def _publish_pending_job():
        try:
            await asyncio.get_running_loop().run_in_executor(
                executor, publish_pending, db, settings, tg)
        except Exception:
            log.exception("publish_pending job failed")
    return _publish_pending_job


def make_distribution_job(db, settings, persona, executor):
    async def _distribution_job():
        try:
            await asyncio.get_running_loop().run_in_executor(
                executor, run_distribution_pending, db, settings, persona)
        except Exception:
            log.exception("run_distribution_pending job failed")
    return _distribution_job


def make_showrunner_job(db, settings, persona, executor):
    async def _showrunner_job():
        try:
            await asyncio.get_running_loop().run_in_executor(
                executor, run_showrunner_pending, db, settings, persona)
        except Exception:
            log.exception("run_showrunner_pending job failed")
    return _showrunner_job


def make_analytics_job(db, settings, executor):
    async def _analytics_job():
        try:
            await asyncio.get_running_loop().run_in_executor(
                executor, run_analytics_pending, db, settings)
        except Exception:
            log.exception("run_analytics_pending job failed")
    return _analytics_job


def make_engagement_job(db, settings, persona, tg, executor):
    async def _engagement_job():
        try:
            await asyncio.get_running_loop().run_in_executor(
                executor, run_engagement_pending, db, settings, persona, tg)
        except Exception:
            log.exception("run_engagement_pending job failed")
    return _engagement_job


def make_optimizer_job(db, settings, persona, tg, executor):
    async def _optimizer_job():
        try:
            await asyncio.get_running_loop().run_in_executor(
                executor, run_optimizer_pending, db, settings, persona, tg)
        except Exception:
            log.exception("run_optimizer_pending job failed")
    return _optimizer_job


def build_scheduler(db, settings, r2, persona, ref, tg, executor) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    run_job = make_run_pending_job(db, settings, r2, persona, ref, tg, executor)
    pub_job = make_publish_pending_job(db, settings, tg, executor)
    dist_job = make_distribution_job(db, settings, persona, executor)
    show_job = make_showrunner_job(db, settings, persona, executor)
    analytics_job = make_analytics_job(db, settings, executor)
    engagement_job = make_engagement_job(db, settings, persona, tg, executor)
    optimizer_job = make_optimizer_job(db, settings, persona, tg, executor)
    scheduler.add_job(run_job, "interval", minutes=settings.worker_interval_minutes, id="run_pending")
    scheduler.add_job(pub_job, "interval", minutes=settings.publish_interval_minutes, id="publish_pending")
    scheduler.add_job(dist_job, "interval", minutes=settings.distribution_interval_minutes, id="run_distribution_pending")
    scheduler.add_job(show_job, "interval", minutes=settings.showrunner_interval_minutes, id="run_showrunner_pending")
    scheduler.add_job(analytics_job, "interval", minutes=settings.analytics_interval_minutes, id="run_analytics_pending")
    scheduler.add_job(engagement_job, "interval", minutes=settings.engagement_interval_minutes, id="run_engagement_pending")
    scheduler.add_job(optimizer_job, "interval", minutes=settings.optimizer_interval_minutes, id="run_optimizer_pending")
    return scheduler
