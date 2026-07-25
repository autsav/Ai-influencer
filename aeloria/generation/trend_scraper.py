"""
Trend scraping & hook generation — Stage 2 of the AI Influencer Pipeline.

Scrapes trending content ideas from public sources and generates viral hooks
using the LLM router (Claude → Ollama → MiniMax fallback).
"""
from __future__ import annotations

import json
import httpx
from datetime import datetime
from typing import Optional
from pathlib import Path

from aeloria.llm_router import llm_generate, llm_generate_json


# ── Trend Sources ─────────────────────────────────────────────────────────────

def get_reddit_trends(subreddit: str = "InstagramBusiness", limit: int = 10) -> list[dict]:
    """Scrape trending posts from a subreddit (public JSON API, no auth needed)."""
    try:
        resp = httpx.get(
            f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}",
            headers={"User-Agent": "AeloriaBot/1.0"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        posts = []
        for child in data["data"]["children"]:
            post = child["data"]
            posts.append({
                "title": post["title"],
                "score": post["score"],
                "url": f"https://reddit.com{post['permalink']}",
                "created": datetime.fromtimestamp(post["created_utc"]).isoformat(),
            })
        return posts[:limit]
    except Exception as e:
        print(f"[trends] Reddit failed: {e}")
        return []


def get_pinterest_trends(query: str = "wellness influencer") -> list[str]:
    """Get trend ideas via LLM (simulated scraping — uses model knowledge)."""
    prompt = f"""List 10 trending content ideas for an Instagram influencer in the '{query}' niche.
Focus on what's trending in 2026 — viral formats, hooks, and content types.
Return as a JSON array of strings, each a content idea.
No markdown, just the JSON array."""
    
    try:
        ideas = llm_generate_json(prompt, timeout=30)
        if isinstance(ideas, list):
            return ideas[:10]
        return ideas.get("ideas", [])[:10]
    except Exception as e:
        print(f"[trends] LLM trends failed: {e}")
        return []


# ── Hook Generation ──────────────────────────────────────────────────────────

HOOK_TEMPLATES = [
    "POV: you finally found {concept}",
    "Nobody talks about {concept}",
    "The {concept} pipeline no one teaches",
    "I tried {concept} so you don't have to",
    "Stop scrolling if you're into {concept}",
    "This is your sign to try {concept}",
    "Why {concept} hits different at 25",
    "The truth about {concept} nobody tells you",
]


def generate_hooks(content_idea: str, count: int = 5) -> list[str]:
    """Generate viral hooks for a content idea using LLM router."""
    prompt = f"""Generate {count} viral Instagram hooks for content about: "{content_idea}"

Rules:
- First line must be punchy (not a question, not a platitude)
- Each hook must be under 10 words
- Use contrarian or surprising angles
- No hashtags in hooks
- Return as a JSON array of strings

Content idea: {content_idea}"""
    
    try:
        hooks = llm_generate_json(prompt, timeout=30)
        if isinstance(hooks, list):
            return hooks[:count]
        return hooks.get("hooks", [])[:count]
    except Exception as e:
        print(f"[trends] Hook generation failed: {e}")
        # Fallback: use templates
        return [t.format(concept=content_idea.lower()) for t in HOOK_TEMPLATES[:count]]


# ── Full trend pipeline ───────────────────────────────────────────────────────

def scrape_and_generate(niches: list[str] | None = None) -> dict:
    """
    Full trend pipeline: scrape trends → generate hooks → return content plan.
    """
    niches = niches or ["wellness", "slow living", "nature", "forest life"]
    
    print("[trends] Scraping trends...")
    all_ideas = []
    for niche in niches:
        ideas = get_pinterest_trends(niche)
        all_ideas.extend(ideas)
    
    # Deduplicate
    seen = set()
    unique_ideas = []
    for idea in all_ideas:
        key = idea.lower().strip()
        if key not in seen:
            seen.add(key)
            unique_ideas.append(idea)
    
    print(f"[trends] Found {len(unique_ideas)} content ideas")
    
    # Generate hooks for top 5 ideas
    results = []
    for idea in unique_ideas[:5]:
        hooks = generate_hooks(idea, count=3)
        results.append({
            "content_idea": idea,
            "hooks": hooks,
        })
    
    return {
        "scraped_at": datetime.now().isoformat(),
        "niches": niches,
        "ideas_found": len(unique_ideas),
        "content_plan": results,
    }


if __name__ == "__main__":
    import json
    plan = scrape_and_generate()
    print(json.dumps(plan, indent=2))