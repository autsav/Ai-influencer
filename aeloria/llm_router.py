"""
Model fallback wrapper — automatic LLM switching when rate limits hit.

Priority ladder:
1. Claude Code CLI (primary)
2. Ollama GLM (fallback 1)
3. MiniMax API (fallback 2)

Usage:
    from aeloria.llm_router import llm_generate
    text = llm_generate("Write a caption for this image")
"""
from __future__ import annotations

import os
import subprocess
import json
import httpx
from typing import Optional


def _try_claude_code(prompt: str, timeout: int = 60) -> Optional[str]:
    """Primary: Claude Code CLI."""
    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"},
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        # Check for rate limit
        stderr = result.stderr.lower()
        if "429" in stderr or "quota" in stderr or "credit" in stderr or "rate limit" in stderr:
            print("[llm_router] Claude Code rate limited — falling through")
            return None
        return None
    except Exception as e:
        print(f"[llm_router] Claude Code failed: {e}")
        return None


def _try_ollama(prompt: str, model: str = "glm-5.2:cloud", timeout: int = 60) -> Optional[str]:
    """Fallback 1: Ollama GLM."""
    try:
        resp = httpx.post(
            "http://localhost:11434/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[llm_router] Ollama failed: {e}")
        return None


def _try_minimax(prompt: str, timeout: int = 60) -> Optional[str]:
    """Fallback 2: MiniMax API."""
    api_key = os.environ.get("MINIMAX_API_KEY", "")
    if not api_key:
        # Try .env
        from pathlib import Path
        env_path = Path(__file__).resolve().parents[2] / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("MINIMAX_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("[llm_router] MiniMax: no API key")
        return None
    try:
        resp = httpx.post(
            "https://api.minimax.io/v1/text/chatcompletion_v2",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "MiniMax-M2.7",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 2000,
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[llm_router] MiniMax failed: {e}")
        return None


def llm_generate(prompt: str, timeout: int = 60) -> str:
    """
    Generate text using the model fallback ladder.
    Returns the first successful response, or raises RuntimeError if all fail.
    """
    # Try each in order
    for name, fn in [("Claude Code", _try_claude_code), ("Ollama", _try_ollama), ("MiniMax", _try_minimax)]:
        result = fn(prompt, timeout=timeout)
        if result:
            print(f"[llm_router] ✅ {name} responded")
            return result
        print(f"[llm_router] ❌ {name} failed — trying next")
    
    raise RuntimeError("All LLM providers failed")


def llm_generate_json(prompt: str, timeout: int = 60) -> dict:
    """Generate and parse JSON from the model."""
    prompt_with_format = f"{prompt}\n\nRespond with valid JSON only, no markdown."
    text = llm_generate(prompt_with_format, timeout=timeout)
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0] if "```" in text else text
    return json.loads(text.strip())