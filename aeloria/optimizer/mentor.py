"""Mentor: weekly-batch prompt rewriter for the Aeloria prompt-evolution loop.

Implements the Sonnet-class rewriter from the Mentor-Agent architecture spec
(2026-08-02-showrunner-mentor-architecture.md, sections 4 + 5 + 6) as a
weekly-batch job that augments run_optimizer_pending.

Three-tier ladder (per spec "Decisions pending sign-off" #3):
  - golden_dataset < 10   -> static prompt, no Mentor call, return 0
  - golden_dataset 10-29  -> static prompt, no Mentor call, return 0
  - golden_dataset >= 30  -> Mentor rewrites the active prompt P(t) -> P(t+1)

Hard-coded meta-instruction is appended verbatim to every Mentor LLM call
(spec section 4, "Mandatory meta-instruction"). Tests assert the literal
text is present (test_meta_instruction_appended_verbatim).
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hard-coded meta-instruction (spec section 4). DO NOT parameterize.
# ---------------------------------------------------------------------------
META_INSTRUCTION = (
    "- Output higher-level rules and constraints.\n"
    "- Do NOT encode hyper-specific if-then statements based on individual training posts.\n"
    "- Do NOT memorize exact topic names from the Golden Dataset.\n"
    "- Maximize generalizability to unseen inputs."
)

# Three-tier ladder thresholds (spec section "Decisions pending sign-off" #3).
TIER_STATIC = 10          # < 10 -> fully static
TIER_HYBRID = 30          # 10-29 -> static prompt, Mentor disabled
# >= 30 -> Mentor enabled with held-out validation

DEFAULT_BRAND_KEY = "aeloria"
DEFAULT_SEED_PROMPT = (
    "# Aeloria — write prompt (seed)\n\n"
    "Write as Aeloria: a 24-year-old AI entrepreneur. Curious, confident, friendly, "
    "slightly geeky, business-minded. Speak in first person, hook in the first line, "
    "no hashtag walls (3-5 max), no corporate-marketing tone, no ChatGPT phrasing. "
    "Show, don't lecture. End with a soft CTA that invites a comment or save.\n"
)


# ---------------------------------------------------------------------------
# LLM call adapter — defaults to aeloria.llm_router.llm_generate.
# ---------------------------------------------------------------------------
def _default_client() -> Callable[[str], str]:
    from aeloria.llm_router import llm_generate
    return llm_generate


def _call_llm(client: Callable[[str], str] | None, prompt: str) -> str:
    fn = client or _default_client()
    return fn(prompt)


# ---------------------------------------------------------------------------
# Prompt-version storage (spec section 5).
# ---------------------------------------------------------------------------
def _brand_dir(brand_key: str, base_dir: str = "prompts") -> Path:
    return Path(base_dir) / brand_key


def _history_dir(brand_key: str, base_dir: str = "prompts") -> Path:
    return _brand_dir(brand_key, base_dir) / "write.history"


def _data_dir(brand_key: str, base_dir: str = "data") -> Path:
    return Path(base_dir) / brand_key


def load_active_prompt(brand_key: str, base_dir: str = "prompts") -> str:
    """Read prompts/<brand>/write.md. Falls back to seed when missing."""
    path = _brand_dir(brand_key, base_dir) / "write.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return DEFAULT_SEED_PROMPT


def archive_prompt(
    brand_key: str,
    prompt_text: str,
    *,
    base_dir: str = "prompts",
    date: str | None = None,
    version: int | None = None,
    source_eval: str = "",
    held_out_score: float | None = None,
) -> Path:
    """Write a snapshot to write.history/<date>_v<n>.md with metadata frontmatter."""
    history = _history_dir(brand_key, base_dir)
    history.mkdir(parents=True, exist_ok=True)
    stamp = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if version is None:
        existing = sorted(history.glob(f"{stamp}_v*.md"))
        version = len(existing) + 1
    path = history / f"{stamp}_v{version}.md"
    front = (
        f"---\n"
        f"date: {stamp}\n"
        f"version: {version}\n"
        f"source_eval: {source_eval or 'mentor_weekly'}\n"
        f"held_out_score: {held_out_score if held_out_score is not None else 'n/a'}\n"
        f"---\n\n"
    )
    path.write_text(front + prompt_text, encoding="utf-8")
    return path


def commit_prompt(brand_key: str, prompt_text: str, *, base_dir: str = "prompts") -> Path:
    """Overwrite the active prompt file. Creates parent dirs."""
    target = _brand_dir(brand_key, base_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / "write.md"
    path.write_text(prompt_text, encoding="utf-8")
    return path


def append_diff_log(brand_key: str, diff_summary: dict, *, base_dir: str = "data") -> Path:
    """Append one JSON line to data/<brand>/diff-log.jsonl (append-only)."""
    target = _data_dir(brand_key, base_dir)
    target.mkdir(parents=True, exist_ok=True)
    path = target / "diff-log.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(diff_summary, sort_keys=True) + "\n")
    return path


# ---------------------------------------------------------------------------
# Mentor LLM call — builds the prompt and invokes the model.
# ---------------------------------------------------------------------------
def _build_mentor_prompt(
    current_prompt: str,
    evaluator_aggregates: dict,
    failure_modes: Iterable[str],
    held_out_score: float | None,
    candidate_score: float | None,
) -> str:
    """Compose the LLM prompt. META_INSTRUCTION is always appended verbatim."""
    aggregate_lines = json.dumps(evaluator_aggregates or {}, indent=2)
    failure_list = "\n".join(f"- {m}" for m in (failure_modes or [])) or "- (none reported)"
    held = "n/a" if held_out_score is None else f"{held_out_score:.3f}"
    cand = "n/a" if candidate_score is None else f"{candidate_score:.3f}"
    return (
        "You are the Mentor (high-reasoning prompt rewriter) for an AI social-media scheduler.\n"
        "Brand: aeloria. Task: rewrite the WRITE prompt P(t) into a new P(t+1) that scores better on the\n"
        "Evaluator rubric. Output the FULL new prompt file contents (markdown). No prose, no code fences.\n\n"
        f"Current prompt P(t):\n```\n{current_prompt}\n```\n\n"
        f"Evaluator aggregates (avg per rubric item, 0-100):\n{aggregate_lines}\n\n"
        f"Failure modes observed (negative signal):\n{failure_list}\n\n"
        f"Held-out validation score: {held}\n"
        f"Candidate score (latest batch): {cand}\n\n"
        "Constraints: higher-level rules, no if-then overfitting, no memorization of Golden topics, maximize generalizability.\n\n"
        "META-INSTRUCTION (always appended):\n"
        f"{META_INSTRUCTION}\n"
    )


def revise_prompt(
    *,
    brand_key: str,
    current_prompt: str,
    evaluator_aggregates: dict,
    failure_modes: list[str],
    held_out_score: float | None,
    candidate_score: float | None,
    client: Callable[[str], str] | None = None,
    meta_instruction: str | None = None,
) -> str:
    """Returns the new prompt P(t+1) text. META_INSTRUCTION appended verbatim.

    `meta_instruction` parameter exists only for backward-compat shimming and is
    not used; the spec's META_INSTRUCTION is the single source of truth.
    """
    prompt = _build_mentor_prompt(
        current_prompt=current_prompt,
        evaluator_aggregates=evaluator_aggregates,
        failure_modes=failure_modes,
        held_out_score=held_out_score,
        candidate_score=candidate_score,
    )
    text = _call_llm(client, prompt).lstrip()
    if not text:
        raise RuntimeError("Mentor model returned empty prompt")
    # Strip code fences the model sometimes wraps outputs in. Use a
    # leading-only anchor so we don't drop a real trailing newline that
    # some markdown renderers expect after a heading block.
    text = re.sub(r"^```(?:markdown|md)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    return text


# ---------------------------------------------------------------------------
# Golden dataset count — sourced from db if it has the hook, else 0.
# ---------------------------------------------------------------------------
def _golden_count(db: Any, brand_key: str, provided: int | None) -> int:
    if provided is not None:
        return int(provided)
    hook = getattr(db, "golden_dataset_count", None)
    if callable(hook):
        try:
            return int(hook(brand_key) or 0)
        except Exception:
            return 0
    return 0


def _evaluator_aggregates(db: Any, brand_key: str, provided: dict | None) -> dict:
    if provided is not None:
        return dict(provided)
    hook = getattr(db, "latest_evaluator_aggregates", None)
    if callable(hook):
        try:
            return dict(hook(brand_key) or {})
        except Exception:
            return {}
    return {}


# ---------------------------------------------------------------------------
# Weekly entry point.
# ---------------------------------------------------------------------------
def run_mentor_pending(
    db,
    settings,
    persona,
    tg=None,
    now: datetime | None = None,
    *,
    brand_key: str = DEFAULT_BRAND_KEY,
    golden_dataset_count: int | None = None,
    evaluator_aggregates: dict | None = None,
    failure_modes: list[str] | None = None,
    held_out_score: float | None = None,
    candidate_score: float | None = None,
    prompts_dir: str = "prompts",
    data_dir: str = "data",
    client: Callable[[str], str] | None = None,
) -> int:
    """Weekly batch Mentor rewriter. Returns count of prompts rewritten (0 or 1)."""
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    n_golden = _golden_count(db, brand_key, golden_dataset_count)

    if n_golden < TIER_HYBRID:
        # Tier 1 (<10) and tier 2 (10-29): static prompt, no Mentor call.
        log.info("mentor skipped (golden=%d, brand=%s)", n_golden, brand_key)
        return 0

    aggregates = _evaluator_aggregates(db, brand_key, evaluator_aggregates)
    current = load_active_prompt(brand_key, base_dir=prompts_dir)

    new_prompt = revise_prompt(
        brand_key=brand_key,
        current_prompt=current,
        evaluator_aggregates=aggregates,
        failure_modes=failure_modes or [],
        held_out_score=held_out_score,
        candidate_score=candidate_score,
        client=client,
    )

    # Archive the OLD active prompt under the same date+version stamp,
    # then commit the new one. The archive frontmatter records the eval source.
    version = len(list(_history_dir(brand_key, base_dir=prompts_dir).glob(f"{stamp}_v*.md"))) + 1
    archive_prompt(
        brand_key,
        current,
        base_dir=prompts_dir,
        date=stamp,
        version=version,
        source_eval="mentor_weekly",
        held_out_score=held_out_score,
    )
    commit_prompt(brand_key, new_prompt, base_dir=prompts_dir)

    append_diff_log(
        brand_key,
        {
            "date": stamp,
            "brand_key": brand_key,
            "version": version,
            "golden_dataset_count": n_golden,
            "held_out_score": held_out_score,
            "candidate_score": candidate_score,
            "failure_modes": list(failure_modes or []),
            "prompt_chars": len(new_prompt),
        },
        base_dir=data_dir,
    )

    if tg:
        try:
            tg.send_message(
                f"🎓 Mentor: rewrote {brand_key}/write.md (v{version}, golden={n_golden})"
            )
        except Exception as e:  # pragma: no cover
            log.warning("mentor telegram notify failed: %s", e)

    return 1
