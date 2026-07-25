-- Aeloria platform schema v2 (fresh rebuild; do not mix with v1 bootstrap.sql)

create table if not exists persona_state (
  id uuid primary key default gen_random_uuid(),
  bible_version int not null,
  state jsonb not null default '{}'::jsonb,       -- arc history, poll outcomes, life memory
  updated_at timestamptz not null default now()
);

create table if not exists arcs (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  niche text not null,
  phase text not null check (phase in ('tease','peak','callback','done')),
  started_at timestamptz not null default now(),
  ended_at timestamptz
);

create table if not exists briefs (
  id uuid primary key default gen_random_uuid(),
  arc_id uuid references arcs(id),
  slot_day date not null,
  slot_type text not null check (slot_type in ('reel','static','story')),
  audience text not null check (audience in ('discovery','retention')),
  beat text not null,
  signature text,                                  -- signature-beat tag, null if none
  hook_spec text,                                  -- required when audience='discovery' and slot_type='reel'
  prompt_seed text not null,
  caption_brief text not null,
  platforms text[] not null,
  engine text not null check (engine in ('fal','higgsfield')),
  distribution_plan jsonb,
  content_format text not null default 'reel'
    check (content_format in ('reel','carousel','static','story')),
  series text,                                     -- series slug, null if standalone
  cta_kind text not null default 'none'
    check (cta_kind in ('save','share','comment','none')),
  trend_id uuid references trends(id),             -- set when brief is a trend-jack
  pillar text,                                     -- content pillar (calendar); null pre-calendar
  location text,                                   -- chapter location (calendar); null pre-calendar
  activity text,                                   -- day-in-the-life activity id
  activity_category text,                          -- activity category (no-repeat window + optimizer)
  time_of_day text,                                -- dawn|morning_indoor|midday|golden|dusk|night|artificial
  style_hint text,                                 -- preferred photo style for this activity
  mood text,                                       -- activity mood (biases expression)
  story_thread text,                               -- active storyline id
  story_beat text,                                 -- "<thread>:<beat_index>"
  emotional_beat text,                             -- the feeling driving this post
  narrative_note text,                             -- the micro-anecdote this post advances
  caption_angle text,                              -- the story/insight the caption should tell
  workflow text,                                   -- fal_router WorkflowType; null = default gen path
  status text not null default 'planned'
    check (status in ('planned','generating','generated','failed')),
  created_at timestamptz not null default now()
);

create table if not exists media_assets (
  id uuid primary key default gen_random_uuid(),
  brief_id uuid references briefs(id),
  r2_url text,                                     -- nullable: cost row inserted pre-upload, r2_url set after R2 put
  kind text not null check (kind in ('image','video')),
  engine text not null check (engine in ('fal','higgsfield')),
  gen_params jsonb not null default '{}'::jsonb,
  cost numeric not null default 0,                 -- usd for fal, credits for higgsfield
  face_similarity numeric,                         -- filled by face gate (phase 2)
  created_at timestamptz not null default now()
);

create table if not exists queue (
  id uuid primary key default gen_random_uuid(),
  asset_id uuid not null references media_assets(id),
  brief_id uuid references briefs(id),
  caption text not null,
  platforms text[] not null,
  slot_time timestamptz not null,
  approval text not null default 'pending'
    check (approval in ('pending','approved','rejected','skipped')),
  reject_reason text,
  created_at timestamptz not null default now()
);

create table if not exists posts (
  id uuid primary key default gen_random_uuid(),
  queue_id uuid not null references queue(id),
  brief_id uuid references briefs(id),
  platform text not null check (platform in ('instagram','youtube','tiktok')),
  platform_post_id text not null,
  published_at timestamptz not null default now()
);

create table if not exists metrics (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references posts(id),
  captured_at timestamptz not null default now(),
  snapshot text not null check (snapshot in ('+3h','+48h','nightly')),
  views int, likes int, comments int, shares int, sends int, saves int,
  watch_through numeric,                           -- avg % viewed
  non_follower_reach int,
  follows_attributed int
);

create table if not exists engagements (
  id uuid primary key default gen_random_uuid(),
  kind text not null check (kind in ('reply','comment_out','dm')),
  target text not null,                            -- post id / account handle
  draft text not null,
  source_id text,                                  -- comment/message/post id for dedup
  posted_id text,                                  -- meta api id of posted reply/dm
  approval text not null default 'pending'
    check (approval in ('pending','approved','rejected')),
  posted_at timestamptz,
  digested_at timestamptz,                         -- when shown in a Telegram digest (dedup digests)
  created_at timestamptz not null default now()
);
create unique index if not exists uq_engagements_source
  on engagements (source_id) where source_id is not null;

create table if not exists trends (
  id uuid primary key default gen_random_uuid(),
  platform text not null,
  kind text not null check (kind in ('audio','format','hashtag')),
  ref text not null,
  note text,
  detected_at timestamptz not null default now(),
  expires_at timestamptz
);

create index if not exists idx_media_assets_engine_created on media_assets (engine, created_at);
create index if not exists idx_queue_approval_slot on queue (approval, slot_time);
create index if not exists idx_metrics_post on metrics (post_id);

create table if not exists follower_snapshots (
  id uuid primary key default gen_random_uuid(),
  platform text not null check (platform in ('instagram','youtube','tiktok')),
  captured_at timestamptz not null default now(),
  followers int not null
);
create index if not exists idx_follower_snapshots_platform_captured
  on follower_snapshots (platform, captured_at desc);

create table if not exists platform_credentials (
  id uuid primary key default gen_random_uuid(),
  platform text not null check (platform in ('instagram','youtube','tiktok')),
  access_token text not null,
  expires_at timestamptz,                       -- null = non-expiring
  updated_at timestamptz not null default now(),
  unique (platform)
);

create table if not exists strategy_weights (
  id uuid primary key default gen_random_uuid(),
  current boolean not null default true,
  weights jsonb not null,               -- {format_mix, cta_by_format}
  computed_at timestamptz not null default now(),
  note text
);
create index if not exists idx_strategy_weights_current
  on strategy_weights (current, computed_at desc);

-- ── Fan / DM layer (v2.0) ──────────────────────────────────────────────────────

create table if not exists fans (
  id          uuid primary key default gen_random_uuid(),
  platform    text not null check (platform in ('fanvue','instagram')),
  external_id text not null,          -- fanvue user id or ig handle
  username    text,
  subscription_tier text not null default 'free'
    check (subscription_tier in ('free','premium','vip')),
  engagement_score numeric not null default 0.5,  -- 0–1; higher = more receptive
  preferred_topics text[] not null default '{}',
  last_message_at timestamptz,
  created_at  timestamptz not null default now(),
  unique (platform, external_id)
);

create table if not exists fan_purchases (
  id          uuid primary key default gen_random_uuid(),
  fan_id      uuid not null references fans(id) on delete cascade,
  content_id  text not null,           -- fanvue content/post id
  content_type text not null            check (content_type in ('ppv_photo','ppv_video','subscription')),
  amount_usd  numeric not null default 0,
  purchased_at timestamptz not null default now()
);
create index if not exists idx_fan_purchases_fan on fan_purchases (fan_id);

create table if not exists dm_conversations (
  id          uuid primary key default gen_random_uuid(),
  fan_id      uuid not null references fans(id) on delete cascade,
  role        text not null check (role in ('fan','aeloria')),
  content     text not null,
  sent_at     timestamptz not null default now()
);
create index if not exists idx_dm_conversations_fan_sent on dm_conversations (fan_id, sent_at desc);
