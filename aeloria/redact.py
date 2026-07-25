"""Redact secrets (access tokens) from strings before logging or external send."""
import re

_SECRET_PATTERNS = [
    (re.compile(r"access_token=[^&\s]+"), "access_token=REDACTED"),
    (re.compile(r"fb_exchange_token=[^&\s]+"), "fb_exchange_token=REDACTED"),
    (re.compile(r"Bearer [A-Za-z0-9._\-]+"), "Bearer REDACTED"),
]


def redact(text: str) -> str:
    """Replace access_token=, fb_exchange_token=, and Bearer <tok> values with REDACTED."""
    for pat, repl in _SECRET_PATTERNS:
        text = pat.sub(repl, text)
    return text