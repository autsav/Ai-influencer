"""
Multi-Agent Pipeline Orchestrator — ai-influencer-v2

Wires all 7 agents together:
  Trend Radar → Script Agent → Image Prompt Engineer → FAL AI
  → QA Gate → Caption Agent → Distribution Scheduler → Growth Hacker

Adapted from engineering-multi-agent-systems-architect.md.
Implements:
  - Trace logging (trace_id + per-step latency)
  - Cost governance (per-step cost_usd tracking)
  - Failure recovery (retry with feedback loop)
  - HITL gate (Telegram approval before publish)
"""
from __future__ import annotations

import json
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Literal

from aeloria.distribution.trend_radar import TrendRadarAgent
from aeloria.generation.script_agent import ScriptAgent
from aeloria.generation.image_prompt_engineer import ImagePromptEngineer
from aeloria.generation.qa_gate import QAGate
from aeloria.generation.caption_agent import CaptionAgent
from aeloria.distribution.growth_hacker import GrowthHackerAgent
from aeloria.generation.fal_images import generate_image_young_energetic, GenerationError as ImageGenError
from aeloria.generation.fal_minimax_video import generate_video_i2va, VideoError
from aeloria.approval.sync_approval import send_for_approval, is_telegram_configured
from aeloria.publishing.meta import publish_image, publish_reel
from aeloria.config import get_settings


@dataclass
class PipelineStep:
    agent: str
    status: str  # "success" | "failure" | "skipped"
    latency_ms: int
    cost_usd: float = 0.0
    output: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class PipelineResult:
    trace_id: str
    status: str  # "running" | "success" | "qa_failed" | "human_rejected" | "approved_pending_publish"
    steps: list[PipelineStep]
    final_assets: dict = field(default_factory=dict)
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "status": self.status,
            "steps": [asdict(s) for s in self.steps],
            "final_assets": self.final_assets,
            "total_cost_usd": round(self.total_cost_usd, 4),
            "total_latency_ms": self.total_latency_ms,
        }


class MultiAgentPipeline:
    """Orchestrator that runs the full content creation pipeline."""

    def __init__(
        self,
        persona_name: str = "young_energetic",
        max_retries: int = 2,
        require_human_approval: bool = True,
        qa_strict: bool = True,
        learnings_path: Optional[Path] = None,
        trend_cache_path: Optional[Path] = None,
    ):
        self.persona_name = persona_name
        self.max_retries = max_retries
        self.require_human_approval = require_human_approval
        self.qa_strict = qa_strict
        self.learnings_path = learnings_path or Path("aeloria/distribution/learnings.json")

        # Agent instances (lazy init for testability)
        self.trend_agent = TrendRadarAgent(
            trend_cache_path=trend_cache_path,
            learnings_path=self.learnings_path,
        )
        self.script_agent = ScriptAgent(persona_name=persona_name)
        self.image_prompt_agent = ImagePromptEngineer(persona_name=persona_name)
        self.qa_gate = QAGate()
        self.caption_agent = CaptionAgent(persona_name=persona_name)
        self.growth_hacker = GrowthHackerAgent(learnings_path=self.learnings_path)

    # ── U3 (2026-08-17): consume trending_topics ─────────────────────────
    def get_trending_topic(self) -> Optional[str]:
        """Return the top-1 trending topic from learnings.json (if any).

        Reads directly from disk so the daily scan (independent scheduler job)
        stays the source of truth. Returns None if no trending_topics are
        recorded yet — callers treat None as "no trend context, carry on".
        """
        if not self.learnings_path.exists():
            return None
        try:
            data = json.loads(self.learnings_path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        topics = data.get("trending_topics") or []
        if not topics:
            return None
        # topics are stored as {"topic": str, "score": float, ...}
        # sort by score desc, return top-1
        topics_sorted = sorted(topics, key=lambda t: float(t.get("score", 0.0)), reverse=True)
        top = topics_sorted[0]
        return top.get("topic") if isinstance(top, dict) else str(top)

    def run(
        self,
        topic: str,
        content_pillar: str = "AI tools + productivity",
        format_type: Literal["reel", "static", "carousel"] = "static",
        preset: Optional[str] = None,
    ) -> PipelineResult:
        """
        Execute the full pipeline.

        1. Trend Radar — get trend signal
        2. Script Agent — write viral script (if reel)
        3. Image Prompt Engineer — build image prompt
        4. Generate image — FAL AI (or stub for offline test)
        5. QA Gate — quality check
        6. Generate video — MiniMax-H3 I2VA (if reel)
        7. Caption Agent — build caption + hashtags
        8. Distribution Scheduler — pick optimal posting time
        9. HITL approval — Telegram bot
        10. Publish — Meta Graph API (or stub)
        11. Growth Hacker — record result when analytics return
        """
        trace_id = f"run_{uuid.uuid4().hex[:12]}"
        result = PipelineResult(trace_id=trace_id, status="running", steps=[])
        start = time.time()

        # ── STEP 1: Trend Radar ──────────────────────────────────────────────
        step_start = time.time()
        # U3 (2026-08-17): pull top-1 from learnings['trending_topics']. If no
        # scan has run yet, None — pipeline proceeds without injecting a trend.
        daily_trend_topic = self.get_trending_topic()
        try:
            trend = self.trend_agent.get_trends(topic=topic, content_pillar=content_pillar)
            # Re-rank hook pattern by winning hook from learnings
            winning_hook = self.growth_hacker.get_winning_hook_type()
            chosen_hook_type = winning_hook or trend.trending_hook_patterns[0].pattern
            # Inject daily trend into brief context if available + topic not set
            if daily_trend_topic and (topic is None or not topic):
                topic = daily_trend_topic
            result.steps.append(PipelineStep(
                agent="TrendRadar",
                status="success",
                latency_ms=int((time.time() - step_start) * 1000),
                output={
                    **trend.to_dict(),
                    "daily_trend_topic": daily_trend_topic,
                },
            ))
        except Exception as e:
            result.steps.append(PipelineStep(
                agent="TrendRadar", status="failure",
                latency_ms=int((time.time() - step_start) * 1000),
                error=str(e),
            ))
            result.status = "trend_failed"
            result.total_latency_ms = int((time.time() - start) * 1000)
            return result

        # ── STEP 2: Script Agent (only if reel) ──────────────────────────────
        script = None
        if format_type == "reel":
            step_start = time.time()
            try:
                script = self.script_agent.write_script(
                    topic=topic,
                    content_pillar=content_pillar,
                    hook_type=chosen_hook_type if chosen_hook_type in ("pattern_interrupt", "curiosity_gap", "relatable_pain") else None,
                    duration_sec=22,
                )
                result.steps.append(PipelineStep(
                    agent="ScriptAgent",
                    status="success",
                    latency_ms=int((time.time() - step_start) * 1000),
                    output={"hook_type": script.hook_type, "retention": script.retention_probability_score},
                ))
            except Exception as e:
                result.steps.append(PipelineStep(
                    agent="ScriptAgent", status="failure",
                    latency_ms=int((time.time() - step_start) * 1000),
                    error=str(e),
                ))
                result.status = "script_failed"
                result.total_latency_ms = int((time.time() - start) * 1000)
                return result

        # ── STEP 3: Image Prompt Engineer ────────────────────────────────────
        step_start = time.time()
        try:
            # Pick preset — use winning preset if available
            chosen_preset = preset or self.growth_hacker.get_winning_preset() or "cafe_morning"
            image_prompt = self.image_prompt_agent.build_prompt(
                preset=chosen_preset,
                aspect_ratio="9:16" if format_type != "static" else "1:1",
            )
            result.steps.append(PipelineStep(
                agent="ImagePromptEngineer",
                status="success",
                latency_ms=int((time.time() - step_start) * 1000),
                output={"preset": image_prompt.preset_name, "prompt_words": len(image_prompt.prompt.split())},
            ))
        except Exception as e:
            result.steps.append(PipelineStep(
                agent="ImagePromptEngineer", status="failure",
                latency_ms=int((time.time() - step_start) * 1000),
                error=str(e),
            ))
            result.status = "prompt_failed"
            result.total_latency_ms = int((time.time() - start) * 1000)
            return result

        # ── STEP 4: Image Generation (FAL AI) — real call with stub fallback ─
        step_start = time.time()
        try:
            image_bytes, image_cost = self._generate_image(image_prompt.prompt, chosen_preset)
            result.steps.append(PipelineStep(
                agent="FAL_image_generation",
                status="success",
                latency_ms=int((time.time() - step_start) * 1000),
                cost_usd=image_cost,
                output={"image_bytes_size": len(image_bytes), "preset": chosen_preset},
            ))
        except Exception as e:
            result.steps.append(PipelineStep(
                agent="FAL_image_generation", status="failure",
                latency_ms=int((time.time() - step_start) * 1000),
                error=str(e),
            ))
            result.status = "image_failed"
            result.total_latency_ms = int((time.time() - start) * 1000)
            return result

        # ── STEP 5: QA Gate ─────────────────────────────────────────────────
        if self.qa_strict:
            step_start = time.time()
            qa_result = self.qa_gate.evaluate_image(image_bytes)
            qa_passed = qa_result.all_pass
            failure_reasons = self.qa_gate.image_failure_reasons(qa_result)
            result.steps.append(PipelineStep(
                agent="QAGate",
                status="success" if qa_passed else "failure",
                latency_ms=int((time.time() - step_start) * 1000),
                output={
                    "passed": qa_passed,
                    "warmth_RG": qa_result.warmth_RG,
                    "warmth_RB": qa_result.warmth_RB,
                    "edge_energy": qa_result.edge_energy,
                    "failures": failure_reasons,
                },
            ))

            if not qa_passed:
                # Retry loop with feedback
                for retry in range(self.max_retries):
                    image_prompt = self.image_prompt_agent.rebuild_with_feedback(
                        image_prompt, failure_reasons
                    )
                    image_bytes, image_cost = self._generate_image(image_prompt.prompt, image_prompt.preset_name)
                    qa_result = self.qa_gate.evaluate_image(image_bytes)
                    qa_passed = qa_result.all_pass
                    failure_reasons = self.qa_gate.image_failure_reasons(qa_result)
                    result.steps.append(PipelineStep(
                        agent="QAGate_retry",
                        status="success" if qa_passed else "failure",
                        latency_ms=0,
                        output={"retry": retry + 1, "passed": qa_passed, "failures": failure_reasons},
                    ))
                    if qa_passed:
                        break
                else:
                    result.status = "qa_failed"
                    result.total_latency_ms = int((time.time() - start) * 1000)
                    return result

        # ── STEP 6: Video Generation (MiniMax-H3) — real call with stub fallback
        video_url = None
        video_cost = 0.0
        if format_type == "reel" and script is not None:
            step_start = time.time()
            try:
                video_url, video_cost = self._generate_video(image_bytes, script.video_prompt)
                result.steps.append(PipelineStep(
                    agent="***",
                    status="success",
                    latency_ms=int((time.time() - step_start) * 1000),
                    cost_usd=video_cost,
                    output={"video_prompt": script.video_prompt[:80]},
                ))
            except Exception as e:
                result.steps.append(PipelineStep(
                    agent="***", status="failure",
                    latency_ms=int((time.time() - step_start) * 1000),
                    error=str(e),
                ))

        # ── STEP 7: Caption Agent ────────────────────────────────────────────
        step_start = time.time()
        caption_result = self.caption_agent.create_caption(
            hook_type=chosen_hook_type,
            caption_prefix=script.caption_prefix if script and script.caption_prefix else "",
            content_pillar=content_pillar,
            trending_hashtags=trend.hashtag_opportunities,
            topic=topic,
        )
        result.steps.append(PipelineStep(
            agent="CaptionAgent",
            status="success",
            latency_ms=int((time.time() - step_start) * 1000),
            output={"engagement_pred": caption_result.engagement_score_prediction},
        ))

        # ── STEP 8: Distribution Scheduler ───────────────────────────────────
        step_start = time.time()
        scheduled_time = trend.optimal_posting_window or "12:00"
        result.steps.append(PipelineStep(
            agent="DistributionScheduler",
            status="success",
            latency_ms=int((time.time() - step_start) * 1000),
            output={"scheduled_time": scheduled_time},
        ))

        # ── STEP 9: HITL Approval (Telegram) ─────────────────────────────────
        if self.require_human_approval:
            step_start = time.time()
            full_caption = f"{caption_result.feed_caption.hook}\n\n{caption_result.feed_caption.body}\n\n{caption_result.feed_caption.cta}"
            approved = self._human_approval(
                caption=full_caption,
                image_bytes=image_bytes,
            )
            result.steps.append(PipelineStep(
                agent="TelegramHITL",
                status="success" if approved else "failure",
                latency_ms=int((time.time() - step_start) * 1000),
                output={"approved": approved},
            ))
            if not approved:
                result.status = "human_rejected"
                result.total_latency_ms = int((time.time() - start) * 1000)
                return result

        # ── STEP 10: Publish to Instagram via Meta Graph API ────────────────
        # Upload the final image/video to R2 to get public URLs
        from aeloria.storage.r2 import R2
        from aeloria.config import get_settings as _gs
        s_r2 = _gs()
        r2 = R2(s_r2)
        final_image_url = None
        if format_type != "reel":
            img_key = f"final_{trace_id}.png"
            r2.upload(image_bytes, img_key, content_type="image/png")
            final_image_url = r2.public_url(img_key)

        full_caption = f"{caption_result.feed_caption.hook}\n\n{caption_result.feed_caption.body}\n\n{caption_result.feed_caption.cta}\n\n{' '.join(caption_result.hashtag_set.large + caption_result.hashtag_set.medium + caption_result.hashtag_set.niche + caption_result.hashtag_set.branded)}"

        post_id = self._publish(
            format_type=format_type,
            caption=full_caption,
            image_url=final_image_url,
            video_url=video_url,
            trace_id=trace_id,
        )
        result.steps.append(PipelineStep(
            agent="publish_to_instagram",
            status="success" if "pending" not in post_id else "skipped",
            latency_ms=0,
            output={"post_id": post_id, "status": "published" if "pending" not in post_id else "stub"},
        ))
        result.status = "published" if "pending" not in post_id else "approved_pending_publish"
        result.post_id = post_id  # type: ignore[attr-defined]

        # ── STEP 11: Update learnings.json via Growth Hacker (analytics back-fill) ──
        # Real analytics fetch would happen here in production; we record the run metadata now
        self.growth_hacker.record_analytics(
            post_id=post_id,
            hook_type=chosen_hook_type,
            content_pillar=content_pillar,
            impressions=0, likes=0, comments=0, shares=0, saves=0,
            preset=chosen_preset,
            hashtags=caption_result.hashtag_set.large,
            scheduled_time=scheduled_time,
        )

        # Populate final_assets for the caller
        result.final_assets = {
            "image_bytes": image_bytes,
            "video_url": video_url,
            "caption": {
                "hook": caption_result.feed_caption.hook,
                "body": caption_result.feed_caption.body,
                "cta": caption_result.feed_caption.cta,
            },
            "hashtags": {
                "large": caption_result.hashtag_set.large,
                "medium": caption_result.hashtag_set.medium,
                "niche": caption_result.hashtag_set.niche,
                "branded": caption_result.hashtag_set.branded,
            },
            "scheduled_time": scheduled_time,
            "post_id": post_id,
            "preset_used": chosen_preset,
            "hook_type": chosen_hook_type,
        }

        result.total_cost_usd = sum(s.cost_usd for s in result.steps)
        result.total_latency_ms = int((time.time() - start) * 1000)
        return result

    # ── Production implementations (stubs kept for offline testing) ──────
    def _generate_image_stub(self, prompt: str, preset: str) -> bytes:
        """OFFLINE STUB: synthetic warm iPhone-quality PNG. Used when FAL_KEY missing."""
        import io
        import numpy as np
        from PIL import Image
        np.random.seed(hash(preset) % 2**32)
        base = np.array([150, 135, 122], dtype=np.float32)
        noise = np.random.normal(0, 18, (576, 1024, 3))
        arr = np.clip(base + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr, 'RGB')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()

    def _generate_video_stub(self, video_prompt: str) -> str:
        """OFFLINE STUB: returns placeholder URL."""
        return f"https://r2.placeholder/video_{uuid.uuid4().hex[:8]}.mp4"

    def _stub_human_approval(self, caption: str, image_bytes: bytes) -> bool:
        """OFFLINE STUB: auto-approve. Used when Telegram not configured."""
        print("[HITL] Auto-approving (Telegram not configured)")
        return True

    def _generate_image(self, prompt: str, preset: str) -> tuple[bytes, float]:
        """Real FAL AI call (generate_image_young_energetic). Falls back to stub."""
        from aeloria.config import get_settings
        s = get_settings()
        if not s.fal_key:
            print("[FAL] No FAL_KEY configured — using stub image")
            return self._generate_image_stub(prompt, preset), 0.0
        result = generate_image_young_energetic(prompt=prompt, aspect_ratio="9:16", settings=s)
        return result.image_bytes, result.cost_usd

    def _generate_video(self, hero_image_bytes: bytes, video_prompt: str) -> tuple[str | None, float]:
        """Real MiniMax-H3 I2VA via FAL. Falls back to stub if no FAL_KEY."""
        from aeloria.config import get_settings
        s = get_settings()
        if not s.fal_key:
            print("[MiniMax-H3] No FAL_KEY — using stub video URL")
            return self._generate_video_stub(video_prompt), 0.0
        # Upload hero image to R2 to get a public URL FAL can fetch
        from aeloria.storage.r2 import R2
        from aeloria.config import get_settings as _get_settings
        s_for_r2 = _get_settings()
        r2 = R2(s_for_r2)
        hero_key = f"hero_{uuid.uuid4().hex[:8]}.png"
        r2.upload(hero_image_bytes, hero_key, content_type="image/png")
        hero_url = r2.public_url(hero_key)
        result = generate_video_i2va(first_frame_url=hero_url, prompt=video_prompt, settings=s)
        # Upload video to R2
        video_key = f"video_{uuid.uuid4().hex[:8]}.mp4"
        r2.upload(result.video_bytes, video_key, content_type="video/mp4")
        video_url = r2.public_url(video_key)
        return video_url, result.cost_usd

    def _human_approval(self, caption: str, image_bytes: bytes) -> bool:
        """Real Telegram send+wait. Falls back to stub if Telegram not configured."""
        if not is_telegram_configured():
            return self._stub_human_approval(caption, image_bytes)
        from aeloria.approval.telegram_api import Telegram
        from aeloria.config import get_settings
        s = get_settings()
        tg = Telegram(s.telegram_bot_token, s.telegram_chat_id)
        return send_for_approval(
            tg, s.telegram_chat_id,
            image_bytes=image_bytes,
            caption=caption,
            timeout_sec=600,
        )

    def _publish(
        self,
        format_type: str,
        caption: str,
        image_url: str | None = None,
        video_url: str | None = None,
        trace_id: str = "",
    ) -> str:
        """Real Meta Graph API publish. Returns media_id. Returns placeholder if no token."""
        from aeloria.config import get_settings
        s = get_settings()
        # Check Instagram token — token_store raises RuntimeError if not initialized
        try:
            from aeloria.auth import token_store
            ig_token = token_store.get()
        except RuntimeError:
            ig_token = None
        if not ig_token:
            print("[Meta] No Instagram token — returning placeholder post_id")
            return f"ig_{uuid.uuid4().hex[:10]}_pending_token"
        if format_type == "reel" and video_url:
            _, mid = publish_reel(s, video_url=video_url, caption=caption)
            return mid
        elif image_url:
            _, mid = publish_image(s, image_url=image_url, caption=caption)
            return mid
        return f"ig_{uuid.uuid4().hex[:10]}_no_asset"


# ── CLI entry point ──────────────────────────────────────────────────────────
def main():
    """CLI: python -m aeloria.generation.multi_agent_pipeline <topic>"""
    import sys
    topic = sys.argv[1] if len(sys.argv) > 1 else "AI tools and productivity"
    pillar = sys.argv[2] if len(sys.argv) > 2 else "AI tools + productivity"
    fmt = sys.argv[3] if len(sys.argv) > 3 else "static"

    # Use isolated test paths
    learnings_path = Path("/tmp/multi_agent_learnings.json")
    trend_cache_path = Path("/tmp/multi_agent_trend_cache.json")

    pipeline = MultiAgentPipeline(
        persona_name="young_energetic",
        max_retries=2,
        require_human_approval=False,  # auto-approve for smoke test
        qa_strict=False,                # skip QA gate for offline stub test
        learnings_path=learnings_path,
        trend_cache_path=trend_cache_path,
    )

    print(f"Running multi-agent pipeline: '{topic}' / {pillar} / {fmt}")
    print("=" * 60)
    result = pipeline.run(topic=topic, content_pillar=pillar, format_type=fmt)  # type: ignore

    print(f"\nTrace ID: {result.trace_id}")
    print(f"Status: {result.status}")
    print(f"Total latency: {result.total_latency_ms} ms")
    print(f"Total cost: ${result.total_cost_usd}")
    print(f"\nSteps ({len(result.steps)}):")
    for step in result.steps:
        marker = "✅" if step.status == "success" else ("⚠️" if step.status == "skipped" else "❌")
        print(f"  {marker} {step.agent}: {step.latency_ms}ms {f'(${step.cost_usd})' if step.cost_usd else ''}")
        if step.error:
            print(f"     error: {step.error}")

    if result.final_assets:
        assets = result.final_assets
        print(f"\nFinal assets:")
        print(f"  Hook: {assets['caption']['hook']}")
        print(f"  Body: {assets['caption']['body']}")
        print(f"  CTA: {assets['caption']['cta']}")
        print(f"  Hashtags (large): {assets['hashtags']['large']}")
        print(f"  Scheduled: {assets['scheduled_time']}")
        print(f"  Post ID: {assets['post_id']}")

    return result.status


if __name__ == "__main__":
    sys.exit(0 if main() in ["success", "approved_pending_publish"] else 1)
