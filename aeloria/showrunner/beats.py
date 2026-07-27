"""Deterministic beat library. Each entry is {beat, prompt_seed, caption_brief};
the beat sheet rotates by week_index so week-over-week varies without an LLM.
`caption_brief` follows the persona voice (AI entrepreneur, first-line hook).

Niches are short keys (the showrunner stores these as the arc `niche`):
  core      = AI automation for business (workflows, tools, case studies)
  secondary = founder lifestyle (building, testing, learning, remote work)
  arcs      = future of business (jobs AI replaces/creates, industry shifts)
"""

_E = lambda beat, prompt_seed, caption_brief: {  # noqa: E731
    "beat": beat, "prompt_seed": prompt_seed, "caption_brief": caption_brief,
}

BEATS = {
    "core": {
        "tease": [
            _E("desk workflow morning",
               "aeloria at her clean desk with a MacBook showing an AI workflow, morning light, coffee beside it",
               "you're wasting 6 hours every week on tasks an AI could do while you sleep"),
            _E("coffee shop build",
               "aeloria working on a laptop at a café corner table, workflow on screen, flat white, natural light",
               "I built this client automation over one coffee — it saved them 18 hours a week"),
        ],
        "peak": [
            _E("building n8n workflow",
               "aeloria building an automation in a workflow builder on screen, deep focus, dual monitors, warm desk light",
               "this AI workflow replaced 3 tools and saved £420/month — here's the full breakdown"),
            _E("dashboard results",
               "aeloria looking at analytics on her laptop, satisfied half-smile, coworking space, bright desk",
               "this automation replied to 247 customers while I slept — bookings up 37%"),
            _E("tool testing",
               "aeloria testing a new AI tool on her laptop, leaning in, curious expression, home office",
               "I tested 18 AI tools this week so you don't have to — only 3 were worth keeping"),
        ],
        "callback": [
            _E("workflow callback",
               "aeloria back at her desk reviewing the workflow results on screen, satisfied, evening light",
               "same workflow, 3 months later — it's saved 240 hours total now"),
        ],
    },
    "secondary": {
        "tease": [
            _E("whiteboard sketch",
               "aeloria standing at a whiteboard sketching an automation flow, marker in hand, modern office",
               "every business has one bottleneck — AI removes it. here's how I find them"),
        ],
        "peak": [
            _E("city walk coffee",
               "aeloria walking through the city with a coffee, earbuds in, purposeful morning stride, golden hour",
               "AI creates freedom — I built my whole business from a laptop and a notebook"),
            _E("reading notebook",
               "aeloria reading at a café table with a notebook open, coffee gone cold, absorbed, warm light",
               "the best AI workflow I built this month came from a book, not a tool"),
        ],
        "callback": [
            _E("remote work sunset",
               "aeloria working on a rooftop terrace with a city view, laptop open, evening light, peaceful",
               "this is the whole point — AI gave me the freedom to work from anywhere"),
        ],
    },
    "arcs": {
        "tease": [
            _E("conference floor",
               "aeloria at a tech conference walking the exhibition floor, curious, badge around neck, bright lights",
               "just spotted 4 AI tools at this conference that nobody's talking about yet"),
        ],
        "peak": [
            _E("airport work",
               "aeloria working on her laptop at an airport gate, boarding pass beside it, bright terminal light",
               "building an AI product from the airport — the tools are so good now you can ship from anywhere"),
            _E("client transformation",
               "aeloria presenting a before/after dashboard to a client on her laptop, coworking meeting room",
               "redesigned a law firm with AI — document review time down 70%, they took 2 new cases"),
        ],
        "callback": [
            _E("year in review",
               "aeloria at her desk reviewing a year of metrics on screen, satisfied, warm lamp light",
               "12 months of AI automation — here's what actually worked and what was a waste of time"),
        ],
    },
}

_VALID_PHASES = ("tease", "peak", "callback")


def beat_for(niche: str, phase: str, week_index: int) -> dict:
    """Return the beat entry for niche×phase, rotating by week_index. Raises
    ValueError on unknown niche or terminal/unknown phase (caller never asks
    for `done` — there are no beats for a completed arc)."""
    if niche not in BEATS:
        raise ValueError(f"unknown niche: {niche!r}")
    if phase not in _VALID_PHASES:
        raise ValueError(f"unknown or terminal phase: {phase!r}")
    entries = BEATS[niche][phase]
    return dict(entries[week_index % len(entries)])


# ---- Pillar library (Phase: 360-day calendar) ----------------------------
# Subjects are LOCATION-NEUTRAL: beat_for_chapter places them in a location +
# season. Never bake a specific city/office into a subject here.
PILLAR_BEATS = {
    "ai_workflows": [
        {"beat": "building workflow", "subject": "aeloria building an automation workflow on her laptop, focused, typing, warm desk light",
         "caption_brief": "this AI workflow replaced 3 tools and saved £420/month — here's how"},
        {"beat": "workflow result", "subject": "aeloria looking at workflow results on screen, satisfied, leaning back",
         "caption_brief": "this automation replied to 247 customers while I slept — here's the result"},
        {"beat": "whiteboard planning", "subject": "aeloria sketching a workflow on a whiteboard, marker in hand, focused",
         "caption_brief": "every business has one bottleneck — AI removes it. here's how I find them"},
    ],
    "ai_tools": [
        {"beat": "testing tools", "subject": "aeloria testing a new AI tool on her laptop, leaning in, curious, home office",
         "caption_brief": "I tested 18 AI tools this week — only 3 were worth keeping"},
        {"beat": "tool comparison", "subject": "aeloria comparing two AI tools side by side on her screen, evaluating, notebook open",
         "caption_brief": "free vs paid — I tested both so you don't have to waste money on the wrong one"},
        {"beat": "hidden gem", "subject": "aeloria smiling at a surprising result on her laptop, genuinely impressed",
         "caption_brief": "this AI tool nobody's talking about just saved me 15 hours this week"},
    ],
    "case_studies": [
        {"beat": "client audit", "subject": "aeloria reviewing a client's business process on her laptop, analyzing, focused",
         "caption_brief": "this restaurant was missing calls during dinner service — AI fixed it in one week"},
        {"beat": "client results", "subject": "aeloria showing a before/after dashboard to the camera, proud, coworking space",
         "caption_brief": "redesigned a law firm with AI — document review time down 70%, they took 2 new cases"},
        {"beat": "client transformation", "subject": "aeloria presenting results on a call, gesturing, engaged, home office",
         "caption_brief": "how a gym used AI to triple lead generation without hiring another staff member"},
    ],
    "founder_lifestyle": [
        {"beat": "morning desk", "subject": "aeloria at her clean desk with a MacBook, coffee, morning light, starting the day",
         "caption_brief": "this workflow saves me 6 hours every day — here's my morning build routine"},
        {"beat": "coffee shop work", "subject": "aeloria working at a café corner table, laptop open, flat white, natural light",
         "caption_brief": "built this client workflow over one coffee — the tools are that good now"},
        {"beat": "remote work", "subject": "aeloria working on a rooftop terrace with a city view, laptop, evening light",
         "caption_brief": "AI creates freedom — I built my whole business from a laptop and a notebook"},
    ],
    "future_of_business": [
        {"beat": "contemplating", "subject": "aeloria looking out a window, thinking, notebook in hand, city view",
         "caption_brief": "5 businesses that will disappear in 5 years because of AI — is yours one of them?"},
        {"beat": "reading", "subject": "aeloria reading at her desk, book open, highlighter, thoughtful expression",
         "caption_brief": "AI won't replace business owners — owners who use AI will replace those who don't"},
        {"beat": "whiteboard future", "subject": "aeloria sketching industry trends on a whiteboard, marker, analytical",
         "caption_brief": "3 jobs AI will create in the next 2 years that don't exist yet — prepare now"},
    ],
}

# Aspirational, specific backgrounds, editorial-master style.
LOCATION_SCENE = {
    "london_home": "in her minimal home office — clean white desk, MacBook, warm desk lamp, one plant, soft depth of field",
    "london_coworking": "in a modern coworking space — bright, white desks, plants, other founders working, natural light",
    "conference": "at a modern tech conference — bright lights, booths, crowd of founders and developers, energetic atmosphere",
    "remote_travel": "working remotely — a rooftop terrace or café with a city view, golden hour, modern and bright",
}

SEASON_MOOD = {
    "deep_winter": "cold clear winter light, crisp and sharp",
    "late_winter": "pale late-winter light, moody and focused",
    "early_spring": "cool spring light, fresh and energized",
    "spring": "fresh bright spring light, clean and modern",
    "late_spring": "warm golden late-spring light, optimistic",
    "early_summer": "long soft early-summer light, bright and open",
    "deep_summer": "hazy warm midsummer light, relaxed and warm",
    "late_summer": "golden late-summer light, warm and productive",
    "early_autumn": "amber early-autumn light, focused and cozy",
    "autumn": "moody grey autumn light, atmospheric and cinematic",
    "late_autumn": "muted late-autumn light, warm and intimate",
    "winter": "cozy low winter light, soft and warm indoors",
}

_NEUTRAL_SCENE = "in a modern workspace"
_NEUTRAL_MOOD = "soft natural light"


def beat_for_chapter(pillar: str, location: str, season: str, rotation_index: int) -> dict:
    """Assemble a beat for a calendar chapter: a location-neutral pillar subject
    placed into a location + season. Unknown pillar -> ai_workflows; unknown
    location/season -> neutral descriptor. Never raises."""
    entries = PILLAR_BEATS.get(pillar) or PILLAR_BEATS["ai_workflows"]
    base = entries[rotation_index % len(entries)]
    scene = LOCATION_SCENE.get(location, _NEUTRAL_SCENE)
    mood = SEASON_MOOD.get(season, _NEUTRAL_MOOD)
    return {
        "beat": base["beat"],
        "prompt_seed": f"{base['subject']} {scene}, {mood}",
        "caption_brief": base["caption_brief"],
    }