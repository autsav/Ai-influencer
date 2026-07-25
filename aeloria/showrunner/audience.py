"""Discovery/retention router. Each slot is tagged discovery (hook-first, to
strangers) or retention (slice-of-life, to existing followers). The ratio
shifts toward retention as the follower count grows."""


def ratio(follower_count: int) -> tuple[float, float]:
    """Return (discovery, retention) proportions summing to 1.0.

    Early (<5k): 0.60 discovery / 0.40 retention. Each +1k followers shifts
    -0.02 from discovery to retention, floored at 0.40 / 0.60."""
    shift = 0.02 * (follower_count // 1000)
    discovery = max(0.40, 0.60 - shift)
    retention = 1.0 - discovery
    return round(discovery, 4), round(retention, 4)


def assign_audiences(n_slots: int, follower_count: int) -> list[str]:
    """Distribute `n_slots` into discovery/retention tags matching `ratio`,
    rounded. Discovery slots come first (they are the growth engine)."""
    d_prop, _ = ratio(follower_count)
    n_discovery = round(n_slots * d_prop)
    n_discovery = max(0, min(n_slots, n_discovery))
    return ["discovery"] * n_discovery + ["retention"] * (n_slots - n_discovery)