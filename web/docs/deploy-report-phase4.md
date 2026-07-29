# Phase 4 Deploy Report — `/lead`

**Date:** 2026-07-29
**Branch:** `feat/aeloria-landing-phase1`
**Spec:** `~/Documents/ai-influencer-v2/docs/superpowers/specs/2026-07-29-aeloria-landing-design.md`
**Status:** ✅ All Phase 4 targets met. **NOT deployed.** Phase 5 (env vars + `/disclosure` + real PDF) gates the Railway push.

## TL;DR

| Target | Required | Mobile | Desktop |
|---|---|---|---|
| Performance | > 90 | **99** | **100** |
| Accessibility | > 95 | **100** | **100** |
| SEO | > 95 | **100** | **100** |
| pa11y WCAG AA | 0 errors | **0** | **0** |
| Mobile screenshot | 375px | ✅ rendered | n/a |
| Desktop screenshot | 1280px | n/a | ✅ rendered |
| Build / Lint / Voice | exit 0 | ✅ all pass | ✅ all pass |

## 1. Lighthouse

Run from `web/` with `npm run start` on port 3000.

```bash
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
npx lighthouse http://localhost:3000/lead \
  --form-factor=mobile \
  --only-categories=performance,accessibility,seo \
  --output=json --output-path=/tmp/lh-mobile.json \
  --chrome-flags="--headless --no-sandbox --disable-gpu" --quiet
```

### Mobile (`/tmp/lh-mobile.json`)
```json
{
  "performance":     99,
  "accessibility":   100,
  "seo":             100,
  "largest-contentful-paint": "1.9 s",
  "first-contentful-paint":   "0.9 s",
  "speed-index":              "0.9 s",
  "total-blocking-time":      "70 ms",
  "cumulative-layout-shift":  "0"
}
```

### Desktop (`/tmp/lh-desktop.json`)
```json
{
  "performance":     100,
  "accessibility":   100,
  "seo":             100,
  "largest-contentful-paint": "0.5 s",
  "first-contentful-paint":   "0.3 s",
  "speed-index":              "0.3 s",
  "total-blocking-time":      "0 ms",
  "cumulative-layout-shift":  "0"
}
```

**Notes:**
- Mobile LCP 1.9s is solid for a content page with custom Google Fonts (Crimson Pro + Inter). No CLS, no layout shift.
- Desktop hits perfect 100/100/100.
- Both runs pass all three Phase 4 score thresholds with margin.

## 2. Screenshots

Playwright + headless Chromium (ms-playwright/chromium-headless-shell-1234). Saved to `web/scripts/screenshots/`.

| Viewport | Path | Width × Height |
|---|---|---|
| Mobile | `web/scripts/screenshots/lead-mobile.png` | 375 × 812 (full page: 375 × 2998) |
| Desktop | `web/scripts/screenshots/lead-desktop.png` | 1280 × 800 (full page: 1280 × 2140) |

Capture script: `web/scripts/screenshots-lead.ts` (idempotent, re-runnable).

**Visual diff vs. spec §4:**
- ✅ Hero: parchment bg, terracotta eyebrow, serif headline (Crimson Pro), ink CTA button
- ✅ Value Props: 3-column grid desktop, single column mobile, ivory cards with warm hairline, no shadows
- ✅ Trust block: warm sand band, vertical terracotta rules between signals
- ✅ SignupBlock: terracotta CTA button (now AA-compliant), eyebrow + serif h2 + form repeat
- ✅ Footer: wordmark + inline nav + disclosure link on warmer sand band

## 3. pa11y (WCAG 2 AA)

Run: `npx pa11y --reporter json --standard WCAG2AA http://localhost:3000/lead`

### First run — 5 failures
1. Hero eyebrow "From Aeloria · 24-year-old AI entrepreneur" — `text-terracotta` (#c96442) on parchment: **3.54:1** ❌
2. SignupBlock eyebrow "Get the Blueprint" — same terracotta on parchment: **3.54:1** ❌
3. SignupBlock submit button — `#c96442` bg + white text: **3.9:1** ❌
4. Footer "AI entrepreneur · UK" — `text-ink-muted` (#6b6b6b) on sand: **4.26:1** ❌
5. Footer "Made with AI, disclosed honestly." — `text-ink-muted` on sand: **4.26:1** ❌

### Fixes applied
- `tailwind.config.ts` → `ink.muted` darkened `#6b6b6b` → `#595959` (6.2:1 parchment, 5.4:1 sand — passes AA)
- `components/ui/Button.tsx` → `terracotta` variant bg changed `bg-terracotta` → `bg-terracotta-deep` (#a4502f) → 5.9:1 with white
- `components/lead/Hero.tsx`, `Trust.tsx`, `SignupBlock.tsx` → eyebrow text `text-terracotta` → `text-terracotta-deep` (#a4502f on parchment = 5.4:1)

**Spec deviation:** Phase 4 spec §4 called for the SignupBlock button to use `terracotta bg #c96442`. Swapped to `#a4502f` (`terracotta-deep`) for AA compliance. Visual change is minor (slightly deeper rust), design intent preserved. Documented here for Phase 5 follow-up if Hermes wants to revisit.

### Re-run after fixes — `[]`
```json
[]
```
Exit 0. Zero WCAG AA failures.

## 4. Build / Lint / Voice

| Check | Command | Exit |
|---|---|---|
| Build | `npm run build` | **0** |
| Lint | `npm run lint` | **0** (1 unrelated warning in `components/jobs/JobCard.tsx` — pre-existing, outside `/lead`) |
| Voice | `npx tsx scripts/voice-check.ts` | **0** — `✓ no voice violations` |

## 5. Issues Found & Resolution

| # | Issue | Severity | Resolution |
|---|---|---|---|
| 1 | Terracotta eyebrow text 3.54:1 contrast on parchment | WCAG AA fail | ✅ **Fixed** — switched to `text-terracotta-deep` |
| 2 | SignupBlock submit button 3.9:1 contrast (white on `#c96442`) | WCAG AA fail | ✅ **Fixed** — switched to `bg-terracotta-deep` (#a4502f, 5.9:1) |
| 3 | Footer `ink-muted` microcopy 4.26:1 contrast on sand | WCAG AA fail | ✅ **Fixed** — `ink.muted` token darkened to #595959 |
| 4 | Pre-existing `<img>` lint warning in `components/jobs/JobCard.tsx` | Warning only | 📋 **Deferred** — outside `/lead` scope, file belongs to dashboard, not landing |
| 5 | Next.js inferred workspace root warning | Informational | 📋 **Deferred** — workspace-level config, not blocking |
| 6 | `next lint` deprecation warning | Informational | 📋 **Deferred** — Next 16 migration task |
| 7 | `/disclosure` page not yet implemented | Spec §4 mandates | 📋 **Phase 5** — gates actual deploy per spec verification checklist |
| 8 | `public/blueprint.pdf` not in repo | Spec §7 verification item | 📋 **Phase 5** — needs real PDF before going live |
| 9 | `RESEND_API_KEY` + `PLAUSIBLE_DOMAIN` env vars unset | Spec §7 verification item | 📋 **Phase 5** — Railway env setup |

## 6. What's NOT done (intentional — Phase 5 gate)

Per spec §6, Phase 4 is verification + deploy **prep**. The following stay pending until Phase 5 confirms env + disclosure + real PDF:

- ❌ No `railway up` / no push to `feat/aeloria-landing-phase1`
- ❌ No `/disclosure` page content
- ❌ No real `public/blueprint.pdf`
- ❌ No Resend audience count query (currently "thousands of owners" placeholder)
- ❌ No Railway env vars

## 7. Artifacts

```
web/docs/deploy-report-phase4.md             ← this file
web/scripts/screenshots-lead.ts              ← capture script (re-runnable)
web/scripts/screenshots/lead-mobile.png      ← 375px full-page
web/scripts/screenshots/lead-desktop.png     ← 1280px full-page
/tmp/lh-mobile.json                          ← Lighthouse mobile JSON
/tmp/lh-desktop.json                         ← Lighthouse desktop JSON
/tmp/pa11y.json                              ← first run (5 failures, fixed)
/tmp/pa11y2.json                             ← final run (0 failures)
```

## 8. Phase 5 hand-off

When ready to deploy:
1. Implement `app/disclosure/page.tsx` (spec §4 Section 5)
2. Drop real PDF into `web/public/blueprint.pdf`
3. Set `RESEND_API_KEY` + `PLAUSIBLE_DOMAIN` in Railway env
4. Query Resend audience API for real subscriber count → swap "thousands" placeholder
5. `railway up` from `web/`
6. Post-deploy: re-run Lighthouse + pa11y on the live URL, attach to final report
