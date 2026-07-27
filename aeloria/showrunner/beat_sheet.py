"""Weekly beat sheet builder (rule-based, $0). Creates one arc + one brief per
day for the horizon, idempotently. Reels are discovery (hook-first, carry a
hook_spec the 3a gate accepts); statics are retention. Signatures fire every
7 days. week_index rotates beats so week-over-week varies without an LLM."""
import hashlib
from datetime import timedelta

from aeloria.config import get_settings
from aeloria.showrunner import beats
from aeloria.showrunner.arcs import advance_arc, create_arc, phase_for_slot
from aeloria.showrunner.activities import choose_activity, load_activities, load_cast, time_phrase
from aeloria.showrunner.briefing import enrich_brief
from aeloria.showrunner.calendar import active_chapter, active_moment, pillar_cycle
from aeloria.showrunner.series import load_series
from aeloria.showrunner.signature import signature_for_day
from aeloria.showrunner.storylines import active_storyline, load_storylines

# v1: the showrunner seeds the core-niche beat sheet. Secondary/arcs niches
# are future work (the beat library already supports them).
DEFAULT_NICHE = "core"
# Identity-preserving fal workflow for all image posts (fal_router.WorkflowType).
# Non-LoRA workflows (kontext/nano-banana/flux-pro) can't carry Aeloria's LoRA.
IMAGE_WORKFLOW = "IDENTITY_LOCKED_LORA"

# CTA per (content_format, audience). Carousels chase saves; discovery reels
# chase comments; retention statics stay CTA-free.
_CTA_BY_FORMAT = {"carousel": "save", "reel": "comment", "static": "none"}


def cta_for(content_format: str, audience: str) -> str:
    return _CTA_BY_FORMAT.get(content_format, "none")


def _effective_cta(content_format, audience, weights) -> str:
    if weights and weights.get("cta_by_format", {}).get(content_format):
        return weights["cta_by_format"][content_format]
    return cta_for(content_format, audience)


def _mix_cycle(weekly_mix: dict) -> list[str]:
    """Expand a weekly mix like {reel:5,carousel:3,static:2} into the base
    interleaved format cycle (round-robin so formats spread out), e.g.
    [reel,carousel,static,reel,carousel,static,reel,carousel,reel,reel]."""
    ordered = []
    buckets = {f: [f] * int(weekly_mix.get(f, 0)) for f in ("reel", "carousel", "static")}
    while any(buckets.values()):
        for f in ("reel", "carousel", "static"):
            if buckets[f]:
                ordered.append(buckets[f].pop())
    if not ordered:
        ordered = ["reel"]
    return ordered


def build_hook_spec(prompt_seed: str) -> str:
    """First-3s visual+text hook for a discovery reel — the 'still, then alive'
    format from the persona wedge. Must pass hook_spec.validate (>=20 chars)."""
    return (
        f"Still, then alive: hold 3s on {prompt_seed}, "
        f"then match-cut to motion on the beat."
    )


def _epoch_day(existing: list[dict], start_date):
    """Global day-0 for signature cadence: the earliest brief ever planned (or
    `start_date` on a fresh db). Anchoring day indices here lets the rotation
    bootstrap under rolling daily runs at horizon 7, where each run only adds
    one new day (a start_date-relative index would never reach day 7)."""
    if not existing:
        return start_date
    earliest = min(_parse_day(r["slot_day"]) for r in existing)
    return min(earliest, start_date)


def _last_signature(existing: list[dict], epoch) -> tuple[int | None, int]:
    rows = [r for r in existing if r.get("signature")]
    if not rows:
        return None, 0
    rows.sort(key=lambda r: str(r["slot_day"]))
    last_day = _parse_day(rows[-1]["slot_day"])
    return (last_day - epoch).days, len(rows)


def _active_arc(db, niche: str) -> dict | None:
    rows = db.select("arcs", {"niche": niche})
    for r in reversed(rows):
        if r.get("phase") != "done":
            return r
    return None


def _parse_day(slot_day) -> "object":
    from datetime import date
    if isinstance(slot_day, date):
        return slot_day
    return date.fromisoformat(str(slot_day)[:10])


def build_week(persona, db, start_date, days: int = 7, follower_count: int = 0,
                settings=None) -> list[dict]:
    """Idempotently create arcs + briefs for `days` starting at `start_date`.
    Returns the brief rows inserted this call (empty if every day already has a
    brief). `persona` selects the niche in future versions; v1 uses core."""
    settings = settings or get_settings()
    weights = db.current_strategy_weights()
    weekly_mix = weights.get("format_mix") if (weights and weights.get("format_mix")) else settings.showrunner_weekly_mix
    mix_cycle = _mix_cycle(weekly_mix)
    series_defs = load_series()
    activities = load_activities()
    storylines = load_storylines()
    cast = load_cast()

    # select_all: idempotency + week_index + signature epoch need every brief,
    # not the first 100 (the plain select() cap).
    existing = db.select_all("briefs", order="slot_day")
    existing_days = {str(r["slot_day"]) for r in existing}
    week_index = len(existing) // 7
    epoch = _epoch_day(existing, start_date)
    last_sig_day, sigs_emitted = _last_signature(existing, epoch)

    niche = DEFAULT_NICHE
    arc = _active_arc(db, niche)
    if arc is None:
        arc = create_arc(db, f"{niche} week {week_index + 1}", niche)
    slot_index_in_arc = sum(1 for r in existing if r.get("arc_id") == arc["id"])
    current_phase = arc.get("phase", "tease")

    created = []
    for d in range(days):
        day = start_date + timedelta(days=d)
        day_str = str(day)
        if day_str in existing_days:
            continue  # idempotent: a brief already exists for this day

        chapter = active_chapter(day)
        location = chapter.get("location", "london_home")
        season = chapter.get("season", "")
        is_home = location == "london_home"

        moment = active_moment(day, chapter)
        if moment:
            content_format = "reel"
            slot_type = "reel"
            audience = "discovery"
            pillar = "travel" if not is_home else pillar_cycle(chapter)[0]
            note = moment.get("note") or moment.get("tag", "")
            tag_h = moment.get("tag", "").replace("_", " ")
            scene = beats.LOCATION_SCENE.get(location, "")
            mood = beats.SEASON_MOOD.get(season, "")
            prompt_seed = f"aeloria hero moment: {tag_h} — {note} {scene}, {mood}".strip()
            hook_spec = build_hook_spec(prompt_seed)
            series_slug = chapter.get("series")
            row = {
                "arc_id": arc["id"], "slot_day": day_str, "slot_type": slot_type,
                "content_format": content_format, "series": series_slug,
                "cta_kind": "comment", "audience": audience,
                "beat": f"moment: {moment.get('tag', '')}", "signature": None,
                "hook_spec": hook_spec, "prompt_seed": prompt_seed,
                "caption_brief": f"a hero post for {tag_h}: {note}",
                "platforms": ["instagram"], "engine": "fal", "distribution_plan": None,
                "pillar": pillar, "location": location, "workflow": IMAGE_WORKFLOW,
                "status": "planned",
            }
            created.append(db.insert("briefs", row))
            slot_index_in_arc += 1
            # Intentional: skip phase_for_slot/advance_arc on a moment day — the
            # arc phase self-heals on the next non-moment day; a moment day just
            # doesn't advance the tease->peak->callback narrative.
            continue  # moment day handled — skip normal generation

        content_format = mix_cycle[(len(existing) + d) % len(mix_cycle)]
        slot_type = "reel" if content_format == "reel" else ("static" if content_format in ("carousel", "static") else content_format)
        audience = "discovery" if content_format == "reel" else "retention"

        phase = phase_for_slot(slot_index_in_arc)
        if phase == "done":
            advance_arc(db, arc["id"], "done")
            arc = create_arc(db, f"{niche} week {week_index + 1} cont", niche)
            slot_index_in_arc = 0
            phase = "tease"
            current_phase = "tease"
        if phase != current_phase:
            advance_arc(db, arc["id"], phase)
            current_phase = phase

        h = int(hashlib.md5(f"{day_str}-{len(existing)}".encode()).hexdigest(), 16)
        style_hint = mood = activity_id = activity_cat = time_of_day = None
        if activities:
            plan = choose_activity(activities, cast, chapter, existing + created, content_format, h)
            pillar = plan["pillar"]
            activity_id, activity_cat = plan["activity"], plan["category"]
            style_hint, mood, time_of_day = plan["style_hint"], plan["mood"], plan["time_of_day"]
            # Indoor activities already describe their interior via `setting`; the
            # outdoor LOCATION_SCENE (streets/café/conference) would contradict them.
            loc_scene = "" if plan["indoor"] else beats.LOCATION_SCENE.get(location, "")
            lead = f"{plan['subject']} {loc_scene}".rstrip() if loc_scene else plan["subject"]
            scene = f"{lead} in {plan['setting']}, {time_phrase(time_of_day)}"
            season_mood = beats.SEASON_MOOD.get(season, "")
            if season_mood:
                scene += f", {season_mood}"
            if plan["cast_element"]:
                scene += f", with {plan['cast_element']}"
            beat = {"beat": activity_id, "prompt_seed": scene,
                    "caption_brief": f"{plan['category']} moment: {plan['subject']}"}
        else:
            pillars = pillar_cycle(chapter)
            pillar = pillars[(len(existing) + d) % len(pillars)]
            beat = beats.beat_for_chapter(pillar, location, season, len(existing) + d)

        abs_day = (day - epoch).days
        sig = signature_for_day(abs_day, last_sig_day, sigs_emitted) if is_home else None
        if sig:
            beat = {
                "beat": sig,
                "prompt_seed": f"{sig}, signature aeloria beat",
                "caption_brief": f"{sig} — a signature aeloria moment",
            }
            # The signature scene replaces the chosen activity entirely: null the
            # activity fields so it renders in its default pillar style/expression
            # and the discarded activity never pollutes the recency/signal window.
            activity_id = activity_cat = time_of_day = style_hint = mood = None

        story = active_storyline(storylines, chapter, (day - epoch).days) if not sig else None
        story_thread = story["thread"] if story else None
        story_beat = f"{story['thread']}:{story['beat_index']}" if story else None
        emotional_beat = story["emotion"] if story else None
        narrative_note = story["note"] if story else None
        caption_angle = story["note"] if story else None

        if story and not sig:
            new_seed, new_cb, caption_angle = enrich_brief(
                beat["prompt_seed"], beat["caption_brief"], emotional_beat, narrative_note,
                persona, settings)
            beat = {**beat, "prompt_seed": new_seed, "caption_brief": new_cb}

        hook_spec = (
            build_hook_spec(beat["prompt_seed"])
            if audience == "discovery" and slot_type == "reel"
            else None
        )

        if content_format == "reel":
            series_slug = chapter.get("series")
        else:
            matched_series = next(
                (s for s in series_defs if s.get("content_format") == content_format), None)
            series_slug = matched_series["slug"] if matched_series else None

        row = {
            "arc_id": arc["id"], "slot_day": day_str, "slot_type": slot_type,
            "content_format": content_format, "series": series_slug,
            "cta_kind": _effective_cta(content_format, audience, weights),
            "audience": audience, "beat": beat["beat"], "signature": sig,
            "hook_spec": hook_spec, "prompt_seed": beat["prompt_seed"],
            "caption_brief": beat["caption_brief"], "platforms": ["instagram"],
            "engine": "fal", "distribution_plan": None,
            "pillar": pillar, "location": location,
            "activity": activity_id, "activity_category": activity_cat,
            "time_of_day": time_of_day, "style_hint": style_hint, "mood": mood,
            "workflow": IMAGE_WORKFLOW, "status": "planned",
            "story_thread": story_thread, "story_beat": story_beat,
            "emotional_beat": emotional_beat, "narrative_note": narrative_note,
            "caption_angle": caption_angle,
        }
        created.append(db.insert("briefs", row))
        slot_index_in_arc += 1
        if sig:
            last_sig_day = abs_day
            sigs_emitted += 1

    return created
