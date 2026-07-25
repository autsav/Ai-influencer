# aeloria/distribution/hook_spec.py
MIN_HOOK_LEN = 20


def validate(brief: dict) -> tuple[bool, str]:
    """Discovery reels require a non-empty hook_spec (first-3s beat).
    All other slot types / audiences: hook_spec optional."""
    is_discovery_reel = (
        brief.get("audience") == "discovery"
        and brief.get("slot_type") == "reel"
    )
    if not is_discovery_reel:
        return True, ""
    hook = (brief.get("hook_spec") or "").strip()
    if not hook:
        return False, "discovery reel requires non-empty hook_spec (first-3s beat)"
    if len(hook) < MIN_HOOK_LEN:
        return False, f"hook_spec too short ({len(hook)} < {MIN_HOOK_LEN}) — describe a first-3s visual+text beat"
    return True, ""