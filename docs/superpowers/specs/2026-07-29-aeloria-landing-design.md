# Aeloria Landing Page — Design Spec

**Date:** 2026-07-29
**Status:** Approved (brainstorming gates passed)
**Repo:** `~/Documents/ai-influencer-v2/web`
**Author:** Hermes (brainstorming) → claude-minimax (implementation)

## 1. Purpose

Lead-capture landing page for the Aeloria AI influencer persona. Visitors exchange an email for the existing AI Workflow Blueprint PDF. Drives traffic from cross-platform sources (Instagram bio, TikTok, LinkedIn) into a owned audience (Resend list).

## 2. Audience

Time-poor business owners (SMBs, 1–50 people) drowning in repetitive work. Want AI that saves hours — not AI theory. Geography: UK, US, CA, AU, SG.

## 3. Brand Aesthetic

Claude/Anthropic-style: warm parchment canvas (#f5f4ed), terracotta accent (#c96442), Anthropic Serif headlines (Georgia fallback), warm-only neutrals. Rationale: matches Aeloria's existing voice ("earthy, un-tech, thoughtful companion") and differentiates from generic Stripe/Linear AI clones.

## 4. Page Structure (5 sections)

### Section 1 — Hero
- **Eyebrow:** "From Aeloria · 24-year-old AI entrepreneur"
- **Headline (serif, 64px):** "I save 15 hours a week with AI. Here's the blueprint."
- **Subhead:** "A free 7-page guide to the AI workflows I actually use to run my business. Built for owners who'd rather save time than learn theory."
- **Form:** email input + dark button "Send me the Blueprint"
- **Microcopy:** "No spam. Unsubscribe in one click. 2,400+ business owners already get this." (placeholder count)
- **Background:** warm parchment (#f5f4ed). Form button: charcoal (#171717). Accents: terracotta.

### Section 2 — Value Props (3 cards)
Three concrete outcomes. Each: icon + outcome headline + one-sentence "how."

1. **Save 15 hours/week** — Workflows that reply to leads, file invoices, and update your CRM while you sleep.
2. **Replace 6 apps with 1** — One AI assistant that handles email, scheduling, research, and reporting — for the price of a coffee.
3. **3× more leads, same budget** — Automated outreach and follow-up that runs on autopilot — without sounding like a robot.

**Layout:** 3-column grid desktop, single column mobile. Cards on `--surface-ivory` (#faf9f5) with 1px warm border (#f0eee6). No shadows.

**Section header above:** "Built for owners who'd rather save time than learn theory." Serif, 32px, small terracotta underline accent.

### Section 3 — Social Proof (artifact-proof, no fake testimonials)
Three trust signals matching Aeloria's existing content pillars:

1. "Featured in my AI Workflow Blueprint — the PDF 2,400+ business owners have downloaded." (number placeholder)
2. "I test every workflow in my own business before sharing. If it doesn't save me hours, it doesn't make the guide."
3. "Disclosed AI persona — full transparency about what's human and what's automated."

**Visual:** Single warm-cream block. Small "Trust" eyebrow. Three lines stacked with a thin terracotta vertical rule between each. No avatars, no fake names.

### Section 4 — Email Signup Block (second touch)
Same form as Hero, framed by proof.

- **Eyebrow:** "Get the Blueprint"
- **Headline (serif, 48px):** "Stop reading about AI. Start using it."
- **Subhead:** "Free 7-page guide. Delivered in 60 seconds. Built for SMB owners who want hours back, not homework."
- **Form:** email + "Send me the Blueprint" button (terracotta bg #c96442, white text)
- **Microcopy:** "Used by 2,400+ owners · UK · US · CA · AU · SG"

**Why twice:** Lead-capture pages convert better with CTA both above-the-fold AND after proof. Visitors who scroll past the Hero get a second chance warmed up by value props + trust.

### Section 5 — Footer (minimal)
- **Left:** "Aeloria" wordmark + "AI entrepreneur · UK"
- **Center:** inline links — About · Instagram · Newsletter Archive · Disclosure
- **Right:** "Made with AI, disclosed honestly."

**Disclosure page required.** Aeloria is an AI persona. `/disclosure` must explain exactly what's human (strategy, voice, curation) and what's automated (image generation, some caption drafting). Brand-trust asset, not legal cover.

**Background:** Same parchment. Footer on slightly warmer band (`--warm-sand` #e8e6dc).

## 5. Tech & Build Plan

**Stack:**
- Next.js 15 app router (existing project — `web/app/`)
- Tailwind CSS with custom theme tokens (Claude palette)
- Form POST → `/api/lead` → Resend API (free tier, 100 emails/day) → audience list
- No CMS, no DB
- Privacy-first analytics: Plausible or Vercel Analytics
- Mobile-first, single column `< 768px`, 3-column grid otherwise

**File map:**
```
web/
  app/
    lead/
      page.tsx              # the landing page
      layout.tsx            # minimal metadata + fonts
    api/
      lead/
        route.ts            # POST → Resend
    disclosure/
      page.tsx              # AI persona transparency
  components/
    lead/
      Hero.tsx
      ValueProps.tsx
      Trust.tsx
      SignupBlock.tsx
      Footer.tsx
    ui/
      Button.tsx
      EmailField.tsx
  lib/
    resend.ts               # server-side email send helper
  public/
    blueprint.pdf           # existing 7-day lead magnet
```

## 6. Implementation Phases

Each phase = one claude-minimax session per `project-manager-delegation` skill.

**Phase 1 — Visual scaffold (no form submission)**
- Scaffold `lead/page.tsx` with 5 sections
- Theme tokens: Claude palette in `tailwind.config.ts`
- 5 section components + 2 UI primitives
- Fonts: Google Fonts `Crimson Pro` (serif fallback for Anthropic Serif) + `Inter` (sans)
- Output: page renders, looks correct, form is `console.log` only
- **Do NOT** touch `/api/lead` yet

**Phase 2 — Form submission + Resend**
- `/api/lead/route.ts` POST handler
- Resend integration via `lib/resend.ts`
- Honeypot field (`website` — hidden, must be empty)
- Rate limit: 5 POSTs per IP per hour (in-memory or upstash)
- Success state in UI (replace form with "Check your inbox.")
- Error state: friendly message, never expose internals

**Phase 3 — Copy + voice verification**
- Pull `aeloria/persona/aeloria.yaml` voice rules into a voice-check script
- Run script against landing copy; flag any tone violations
- Verify CTAs match the voice ("Send me the Blueprint" not "GET STARTED NOW")

**Phase 4 — Lighthouse + deploy**
- Lighthouse pass: perf > 90 mobile, a11y > 95, SEO > 95
- Mobile test on real device via browser_vision
- Deploy to Railway (`web/railway.toml` already exists per CLAUDE.md)
- Set env: `RESEND_API_KEY`, `PLAUSIBLE_DOMAIN`

## 7. Verification Checklist (before launch)

- [ ] **"2,400+" subscriber count replaced with real number** — query Resend audience API
- [ ] **`public/blueprint.pdf` exists and downloads** — file size sanity check
- [ ] **`web/.env.local` has `RESEND_API_KEY`** — local test
- [ ] **Railway env has `RESEND_API_KEY` + `PLAUSIBLE_DOMAIN`** — deploy-time
- [ ] **`/disclosure` page exists and is linked from footer** — manual click test
- [ ] **Form tested:** empty → friendly error; valid → success state
- [ ] **Honeypot:** filled form is silently dropped (no email sent)
- [ ] **Lighthouse:** perf > 90 mobile, a11y > 95, SEO > 95
- [ ] **Mobile:** renders correctly at 375px width (browser_vision)
- [ ] **Voice check:** no tone violations per `aeloria/persona/aeloria.yaml`

## 8. Out of Scope (deliberate)

- A/B testing framework (add later once we have traffic baseline)
- Multi-language (English-only for v1; Aeloria's primary markets all read English)
- Blog/CMS (separate project — `web/app/blog/` if needed later)
- Auth / paid products (separate project — `gumroad-products` in `/Users/utsab1/Documents/gumroad-products/`)
- Comments / community (Discord if needed; not now)

## 9. References

- `~/Documents/ai-influencer-v2/CLAUDE.md` — Aeloria v4.0 SOP
- `~/Documents/ai-influencer-v2/aeloria/persona/aeloria.yaml` — voice rules (source of truth)
- `~/Documents/ai-influencer-v2/docs/instagram-lead-magnet-funnel-setup.md` — existing ManyChat funnel (cross-link)
- `~/Documents/ai-influencer-v2/docs/lead-magnet-ai-workflow-blueprint.md` — the PDF content
- Hermes skill: `popular-web-designs/templates/claude.md` — design tokens (source of truth for palette)
- Hermes skill: `claude-design` — design process companion
- Hermes skill: `project-manager-delegation` — per-phase delegation rules
- Hermes skill: `skill-discovery` — meta-skill that drove this brainstorm
