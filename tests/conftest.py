import os
import sys
from pathlib import Path

# Test isolation: the LLM opt-in flags (briefing / growth-analyst) may be enabled in
# .env for production, but tests must never trigger real Anthropic calls. Env vars
# override .env in pydantic Settings, so force them off for the whole test process.
os.environ["BRIEFING_ENABLED"] = "false"
os.environ["OPTIMIZER_ANALYST_ENABLED"] = "false"

# Add repo root to sys.path so pytest can find aeloria
repo_root = Path(__file__).parent.parent
sys.path.insert(0, str(repo_root))
