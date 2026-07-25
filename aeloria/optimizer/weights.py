"""Turn per-dimension lift scores into bounded strategy weights. Each format_mix
count moves at most ±max_delta per update; the total is preserved so the weekly
cadence stays put. cta_by_format carries through (richer CTA learning is future
work). One lucky viral post can't swing the strategy — that's the point."""

DEFAULT_WEIGHTS = {
    "format_mix": {"reel": 5, "carousel": 3, "static": 2},
    "cta_by_format": {"reel": "comment", "carousel": "save", "static": "none"},
}


def _clamp(x, lo, hi):
    return max(lo, min(hi, x))


def _bounded_count(count, lift, max_delta):
    """New raw count for a format: scale by (1 + clamped(lift-1)), never below 0."""
    frac = _clamp(lift - 1.0, -max_delta, max_delta)
    return max(0.0, count * (1.0 + frac))


def update_weights(scores, current, max_delta) -> dict:
    cur = current or DEFAULT_WEIGHTS
    fmix = dict(cur.get("format_mix", DEFAULT_WEIGHTS["format_mix"]))
    total = sum(fmix.values()) or 1
    fdims = (scores.get("dimensions", {}) or {}).get("content_format", {})

    raw = {f: _bounded_count(c, fdims.get(f, {}).get("lift", 1.0), max_delta) for f, c in fmix.items()}
    rsum = sum(raw.values()) or 1.0
    scaled = {f: raw[f] * total / rsum for f in raw}
    new_mix = {f: int(round(v)) for f, v in scaled.items()}

    # Preserve the total exactly by nudging the largest-scaled format.
    drift = total - sum(new_mix.values())
    if drift != 0 and new_mix:
        f = max(scaled, key=scaled.get)
        new_mix[f] = max(0, new_mix[f] + drift)

    cta = dict(cur.get("cta_by_format", DEFAULT_WEIGHTS["cta_by_format"]))
    return {"format_mix": new_mix, "cta_by_format": cta}
