#!/usr/bin/env python3
"""Analytics feedback loop — reads performance metrics, LLM analyzes, updates prompt queue.

Reads a structured performance log (CSV or JSON) with metrics like views, retention,
engagement, saves, shares. The LLM analyzes top-performing entries and outputs
updated prompt templates and content ideas into queue/scheduled_prompts.json.

Usage:
    python scripts/analytics_loop.py --metrics data/performance.json
    python scripts/analytics_loop.py --metrics data/performance.csv --top-n 5
    python scripts/analytics_loop.py --metrics data/performance.json --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

QUEUE_FILE = Path("queue/scheduled_prompts.json")

ANALYSIS_PROMPT = """You are a social media strategist for an AI influencer account.
Analyze the following performance data and identify what's working.

Performance data (top {top_n} posts by engagement rate):
{metrics_text}

Analyze:
1. What scenes/locations perform best?
2. What poses or camera angles drive higher retention?
3. What wardrobe styles get more saves?
4. What time of day or lighting correlates with higher engagement?
5. Are there patterns in the top vs bottom performers?

Based on your analysis, generate {num_ideas} new content ideas as JSON with this structure:
[
  {{
    "scene": "specific scene description",
    "wardrobe": "detailed outfit",
    "pose": "specific pose description",
    "camera_angle": "creative camera angle",
    "predicted_engagement": "high|medium|low",
    "rationale": "why this should work based on the data"
  }}
]

Output ONLY the JSON array, no commentary."""


def load_metrics_csv(path: str) -> list[dict]:
    """Load performance metrics from CSV."""
    with open(path) as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_metrics_json(path: str) -> list[dict]:
    """Load performance metrics from JSON array."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "posts" in data:
        return data["posts"]
    return [data]


def load_metrics(path: str) -> list[dict]:
    """Auto-detect format and load."""
    if path.endswith(".csv"):
        return load_metrics_csv(path)
    return load_metrics_json(path)


def calculate_engagement_rate(post: dict) -> float:
    """Calculate engagement rate from available metrics."""
    views = float(post.get("views", post.get("impressions", 0)) or 0)
    if views == 0:
        return 0.0
    likes = float(post.get("likes", 0) or 0)
    comments = float(post.get("comments", 0) or 0)
    shares = float(post.get("shares", 0) or 0)
    saves = float(post.get("saves", 0) or 0)
    return (likes + comments + shares + saves) / views


def rank_posts(posts: list[dict], top_n: int = 10) -> list[dict]:
    """Rank posts by engagement rate, return top N with computed rates."""
    for post in posts:
        post["engagement_rate"] = calculate_engagement_rate(post)
    posts.sort(key=lambda p: p["engagement_rate"], reverse=True)
    return posts[:top_n]


def metrics_to_text(posts: list[dict]) -> str:
    """Convert metrics dicts to readable text for LLM prompt."""
    lines = []
    for i, post in enumerate(posts, 1):
        lines.append(f"Post {i}:")
        for key in ["scene", "wardrobe", "pose", "camera_angle", "location",
                     "views", "likes", "comments", "shares", "saves",
                     "retention", "engagement_rate", "time_posted"]:
            if key in post and post[key]:
                lines.append(f"  {key}: {post[key]}")
        lines.append("")
    return "\n".join(lines)


def analyze_with_llm(metrics_text: str, top_n: int, num_ideas: int) -> list[dict]:
    """Send metrics to LLM for analysis and content idea generation."""
    prompt = ANALYSIS_PROMPT.format(top_n=top_n, metrics_text=metrics_text, num_ideas=num_ideas)

    # Try LLM router (Claude → Ollama → MiniMax)
    try:
        from aeloria.llm_router import llm_generate
        response = llm_generate(prompt)
        if response:
            # Extract JSON array from response
            return _extract_json_array(response)
    except Exception as e:
        logger.warning("LLM router failed: %s — using fallback", e)

    # Fallback: generate simple ideas from top-performing patterns
    return _fallback_ideas(metrics_text, num_ideas)


def _extract_json_array(text: str) -> list[dict]:
    """Extract JSON array from LLM response text."""
    # Try to find JSON array in the text
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    logger.warning("Could not extract JSON from LLM response")
    return []


def _fallback_ideas(metrics_text: str, num_ideas: int) -> list[dict]:
    """Generate simple ideas without LLM (fallback)."""
    templates = [
        {"scene": "sitting at a London café, morning light", "wardrobe": "cream knit sweater",
         "pose": "looking at camera, warm half-smile", "camera_angle": "eye-level 50mm",
         "predicted_engagement": "medium", "rationale": "café content historically performs well"},
        {"scene": "walking through Covent Garden market", "wardrobe": "linen shirt and jeans",
         "pose": "mid-stride, looking back over shoulder", "camera_angle": "three-quarter candid",
         "predicted_engagement": "high", "rationale": "street style + movement drives saves"},
        {"scene": "sitting on a park bench in autumn", "wardrobe": "oversized scarf and boots",
         "pose": "hands around a coffee cup", "camera_angle": "shallow DOF, 85mm",
         "predicted_engagement": "medium", "rationale": "seasonal + cozy aesthetic"},
    ]
    return templates[:num_ideas]


def add_ideas_to_queue(ideas: list[dict]) -> int:
    """Add generated content ideas to the scheduled prompts queue."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if QUEUE_FILE.exists():
        queue = json.loads(QUEUE_FILE.read_text())
    else:
        queue = []

    added = 0
    for idea in ideas:
        entry = {
            "id": f"idea_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{added}",
            "prompt": idea.get("scene", ""),
            "scene": idea.get("scene", ""),
            "wardrobe": idea.get("wardrobe", ""),
            "pose": idea.get("pose", ""),
            "camera_angle": idea.get("camera_angle", ""),
            "status": "pending",
            "predicted_engagement": idea.get("predicted_engagement", "medium"),
            "rationale": idea.get("rationale", ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        queue.append(entry)
        added += 1

    QUEUE_FILE.write_text(json.dumps(queue, indent=2))
    logger.info("Added %d ideas to queue → %s", added, QUEUE_FILE)
    return added


def main():
    parser = argparse.ArgumentParser(description="Analytics feedback loop")
    parser.add_argument("--metrics", "-m", required=True, help="Path to performance metrics (CSV/JSON)")
    parser.add_argument("--top-n", "-n", type=int, default=10, help="Number of top posts to analyze")
    parser.add_argument("--ideas", type=int, default=5, help="Number of new content ideas to generate")
    parser.add_argument("--dry-run", action="store_true", help="Analyze without adding to queue")
    args = parser.parse_args()

    # Load and rank metrics
    posts = load_metrics(args.metrics)
    if not posts:
        logger.error("No metrics found in %s", args.metrics)
        sys.exit(1)

    top_posts = rank_posts(posts, args.top_n)
    logger.info("Ranked %d posts, top engagement: %.4f", len(posts), top_posts[0]["engagement_rate"])

    # Format for LLM
    metrics_text = metrics_to_text(top_posts)

    # Analyze with LLM
    logger.info("Sending %d top posts to LLM for analysis...", len(top_posts))
    ideas = analyze_with_llm(metrics_text, args.top_n, args.ideas)

    if not ideas:
        logger.warning("No ideas generated")
        sys.exit(1)

    logger.info("Generated %d content ideas", len(ideas))
    for i, idea in enumerate(ideas, 1):
        logger.info("  %d. %s (%s)", i, idea.get("scene", "?")[:60], idea.get("predicted_engagement", "?"))

    # Add to queue
    if args.dry_run:
        logger.info("Dry run — not adding to queue")
        print(json.dumps(ideas, indent=2))
    else:
        added = add_ideas_to_queue(ideas)
        print(json.dumps({"added_to_queue": added, "ideas": ideas}, indent=2))


if __name__ == "__main__":
    main()