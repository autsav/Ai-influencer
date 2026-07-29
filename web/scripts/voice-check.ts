/**
 * Aeloria voice check — verifies landing-page copy against the persona voice
 * rules in `aeloria/persona/aeloria.yaml` (source of truth).
 *
 * Run:  npx tsx web/scripts/voice-check.ts     (from repo root)
 *       npx tsx scripts/voice-check.ts         (from web/)
 *
 * Flags: --list   print every extracted copy string, grouped by file
 *        --json   machine-readable report
 *
 * Exit 0 = clean (warnings allowed). Exit 1 = at least one error.
 *
 * The persona rules are prose, so they are not mechanically checkable on their
 * own. Each check below is a curated phrase/pattern set bound to the exact
 * persona rule it enforces (`ruleSource`), read live from the YAML. If a
 * persona rule changes or a new one is added, the coverage section reports it
 * as unmapped so the drift is visible instead of silent.
 */
import { existsSync, readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

// ── Paths ──────────────────────────────────────────────────────────────────
// Derived from argv[1] (the script path) so the command works from the repo
// root or from web/, under both CJS and ESM transpilation.
const SCRIPT_DIR = dirname(resolve(process.argv[1] ?? "."));
const WEB_ROOT = resolve(SCRIPT_DIR, "..");
const REPO_ROOT = resolve(WEB_ROOT, "..");
const PERSONA_PATH = resolve(REPO_ROOT, "aeloria/persona/aeloria.yaml");

/**
 * Copy sources. `page.tsx` is composition-only today but is scanned so inline
 * copy can't slip in later. `LeadForm.tsx` owns the CTA label and the
 * success/error strings — the design spec's phase 3 explicitly asks for CTA
 * verification, so it is included alongside the five section components.
 */
const SOURCES = [
  "app/lead/page.tsx",
  "components/lead/Hero.tsx",
  "components/lead/ValueProps.tsx",
  "components/lead/Trust.tsx",
  "components/lead/SignupBlock.tsx",
  "components/lead/Footer.tsx",
  "components/lead/LeadForm.tsx",
];

// ── Persona YAML (minimal reader) ──────────────────────────────────────────
// Deliberately no yaml dependency: the file is a flat map of scalars and
// string lists, and adding a runtime dep to the web app for a dev script
// isn't worth it. Only the three shapes we need are parsed.
interface Persona {
  tone: string;
  captionRules: string[];
  hardRules: string[];
}

function parsePersona(raw: string): Persona {
  const lines = raw.split("\n");
  let tone = "";
  const captionRules: string[] = [];
  const hardRules: string[] = [];
  let bucket: "caption" | "hard" | null = null;

  const stripQuotes = (s: string) =>
    s.replace(/^["'](.*)["']$/, "$1").trim();

  for (const line of lines) {
    if (/^\s*#/.test(line) || line.trim() === "") continue;

    const tone_ = line.match(/^\s{2,}tone:\s*(.+)$/);
    if (tone_) {
      tone = stripQuotes(tone_[1]);
      continue;
    }

    if (/^\s{2,}caption_rules:\s*$/.test(line)) {
      bucket = "caption";
      continue;
    }
    if (/^hard_rules:\s*$/.test(line)) {
      bucket = "hard";
      continue;
    }
    // Any new top-level or 2-space key closes the current list.
    if (/^\s{0,2}[a-z_]+:/.test(line) && !/^\s*-/.test(line)) {
      bucket = null;
      continue;
    }

    const item = line.match(/^\s*-\s+(.+)$/);
    if (item && bucket) {
      const value = stripQuotes(item[1]);
      if (bucket === "caption") captionRules.push(value);
      else hardRules.push(value);
    }
  }

  return { tone, captionRules, hardRules };
}

// ── Copy extractor (TSX text + string literals) ────────────────────────────
// Goal: pull every piece of user-visible copy. Two shapes:
//   1. JSX text nodes — `>hello<`, `> {expr} <`, etc. (best-effort)
//   2. String literals inside data arrays (Signals, cards, items).
// HTML entities (`&rsquo;`, `&mdash;`) get decoded so phrase matching works on
// the final character, not the raw entity.
const ENTITY_DECODE: Record<string, string> = {
  "&rsquo;": "\u2019",
  "&mdash;": "\u2014",
  "&amp;": "&",
  "&lt;": "<",
  "&gt;": ">",
  "&quot;": '"',
  "&apos;": "'",
  "&nbsp;": " ",
};

function decodeEntities(s: string): string {
  return s.replace(/&[a-z]+;|&#\d+;/gi, (m) => ENTITY_DECODE[m] ?? m);
}

interface Extracted {
  file: string;
  text: string;
  /** Best-effort anchor: nearby variable/JSX-context hint. */
  ctx: string;
}

/**
 * Extract every string literal from a source file. Captures both `"..."` and
 * `'...'` (with backslash escapes). Used to seed exact-match phrase checks.
 */
function extractStringLiterals(src: string): { text: string; ctx: string }[] {
  const out: { text: string; ctx: string }[] = [];
  // Double-quoted strings (no template strings; persona rules don't need them).
  const re = /"((?:\\.|[^"\\])*)"/g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) {
    const raw = m[1];
    if (!raw) continue;
    // Skip imports, paths, className soup, variant tags, JSON keys.
    if (looksLikeNoise(raw)) continue;
    out.push({ text: decodeEntities(raw), ctx: "literal" });
  }
  // Single-quoted — same treatment.
  const re2 = /'((?:\\.|[^'\\])*)'/g;
  while ((m = re2.exec(src)) !== null) {
    const raw = m[1];
    if (!raw) continue;
    if (looksLikeNoise(raw)) continue;
    out.push({ text: decodeEntities(raw), ctx: "literal" });
  }
  return out;
}

/**
 * Reject className soup, file paths, imports, href targets, variant keys,
 * React keys, SUFFIX plain numbers, etc. The script is opt-in: only copy-shaped
 * strings survive. Heuristic, not bulletproof — accepted trade-off for a
 * zero-dependency dev script.
 */
function looksLikeNoise(s: string): boolean {
  if (s.length < 2) return true;
  if (/^https?:\/\//.test(s)) return true;
  if (/^[./]/.test(s)) return true;
  if (/^@?[a-z][\w-]*(\/[a-z][\w-]*)+$/.test(s)) return true; // import path
  if (/^[a-z-]+:\d/.test(s)) return true; // variant:width etc.
  if (/^(font|grid|flex|gap-|px-|py-|mx-|my-|w-|h-|text-|bg-|border-|rounded|tracking-|leading-|max-|min-|sm:|md:|lg:|xl:|hover:|focus:|aria-|role=|type=|id=|name=|href|target=|rel=|tabIndex|autoComplete|method|action|alt=|src=)/.test(s)) {
    return true;
  }
  if (/^[a-z]+(?:[-:][a-z0-9]+)+$/.test(s) && !/\s/.test(s)) return true; // classchain
  if (/^[a-z_]+$/.test(s)) return true; // bare identifier
  return false;
}

/**
 * Drop captures that crossed a JSX boundary into code. The naive
 * `>([^<>]+)<` regex matches across `useState<X>(...)` braces too, so the
 * captured chunk ends up containing TypeScript source. Heuristic: any code
 * marker in a multi-line capture is a code snippet, not copy.
 */
function looksLikeCode(s: string): boolean {
  if (s.includes("\n") && s.length > 80) return true;
  if (/[;{}]/.test(s)) return true;
  if (/=>/.test(s)) return true;
  if (
    /\b(?:const|let|var|function|return|if|else|for|while|await|async|import|export|from|class|new|throw|try|catch|typeof|instanceof|status|setStatus|setErrorMsg|res|n?extResponse)\b/.test(
      s,
    )
  ) {
    return true;
  }
  if (/[a-zA-Z_$][\w$]*\s*\(/.test(s)) return true;
  return false;
}

/**
 * Extract JSX text nodes: visible characters between `>` and `<`. The naive
 * `>([^<>]+)<` regex captures multi-line content between tags, so the chunk
 * is split on newlines and each line is checked independently. Short lines
 * (< 8 chars) are dropped — they are usually JSX-continuation fragments.
 */
function extractJsxText(src: string): string[] {
  const out: string[] = [];
  const re = />([^<>]+)</g;
  let m: RegExpExecArray | null;
  while ((m = re.exec(src)) !== null) {
    const raw = m[1];
    if (!raw) continue;
    const cleaned = raw.replace(/\{[^}]*\}/g, "");
    for (const line of cleaned.split("\n")) {
      const t = line.trim();
      if (t.length < 8) continue;
      if (looksLikeCode(t)) continue;
      out.push(decodeEntities(t));
    }
  }
  return out;
}

function extractCopy(filePath: string): Extracted[] {
  const raw = readFileSync(filePath, "utf8");
  const out: Extracted[] = [];
  for (const t of extractJsxText(raw)) out.push({ file: filePath, text: t, ctx: "jsx" });
  for (const { text, ctx } of extractStringLiterals(raw)) {
    out.push({ file: filePath, text, ctx });
  }
  return out;
}

// ── Curated phrase lists ────────────────────────────────────────────────────
// Each entry is bound to a persona rule via `ruleSource` (substring of the
// YAML text). When the YAML rule changes, the linkage breaks loudly in the
// coverage report — not silently.
interface PhraseRule {
  pattern: RegExp;
  reason: string;
  ruleSource: string;
  severity: "error" | "warning";
}

const BANNED_PHRASES: PhraseRule[] = [
  // Hard hype words — never brand-safe.
  { pattern: /\brevolutionary\b/i, reason: "hype word", ruleSource: "never sound like a corporate marketer", severity: "error" },
  { pattern: /\bgroundbreaking\b/i, reason: "hype word", ruleSource: "never sound like a corporate marketer", severity: "error" },
  { pattern: /\bgame[-\s]?changing\b/i, reason: "hype word", ruleSource: "never sound like a corporate marketer", severity: "error" },
  { pattern: /\bunleash(?:es|d)?\s+(?:the\s+)?power\b/i, reason: "hype phrase", ruleSource: "never sound like a corporate marketer", severity: "error" },
  { pattern: /\bcutting[-\s]?edge\b/i, reason: "hype word", ruleSource: "never sound like a corporate marketer", severity: "warning" },
  { pattern: /\bnext[-\s]?level\b/i, reason: "hype word", ruleSource: "never sound like a corporate marketer", severity: "warning" },
  { pattern: /\bunlock\b/i, reason: "hype word", ruleSource: "never sound like a corporate marketer", severity: "warning" },
  { pattern: /\bseamless(?:ly)?\b/i, reason: "hype word", ruleSource: "never sound like a corporate marketer", severity: "warning" },
  { pattern: /\brobust\b/i, reason: "hype word", ruleSource: "never sound like a corporate marketer", severity: "warning" },
  { pattern: /\bsynerg(?:y|ies|ize)\b/i, reason: "corporate jargon", ruleSource: "never sound like a corporate marketer", severity: "error" },
  { pattern: /\bleverage\b/i, reason: "corporate jargon", ruleSource: "never sound like a corporate marketer", severity: "warning" },
  { pattern: /\bempower(?:s|ed|ing)?\b/i, reason: "cause-marketer speak", ruleSource: "never sound like a corporate marketer", severity: "warning" },

  // ChatGPT-isms — generic LLM energy.
  { pattern: /\bin today'?s fast[-\s]?paced world\b/i, reason: "ChatGPT cliché", ruleSource: "never sound like ChatGPT", severity: "error" },
  { pattern: /\bare you tired of\b/i, reason: "ChatGPT cliché", ruleSource: "never sound like ChatGPT", severity: "error" },
  { pattern: /\blook no further\b/i, reason: "ChatGPT cliché", ruleSource: "never sound like ChatGPT", severity: "error" },
  { pattern: /\bdive\s+in\b/i, reason: "ChatGPT cliché", ruleSource: "never sound like ChatGPT", severity: "warning" },
  { pattern: /\bdelve\s+into\b/i, reason: "ChatGPT cliché", ruleSource: "never sound like ChatGPT", severity: "warning" },
  { pattern: /\b(?:it'?s\s+)?not\s+just\s+.{1,40};\s+it'?s\s+/i, reason: "ChatGPT 'X is not just Y, it's Z' construction", ruleSource: "never sound like ChatGPT", severity: "warning" },
  { pattern: /\bwhether you'?re\s+a\s+(?:beginner|expert|professional)\b/i, reason: "ChatGPT inclusivity preamble", ruleSource: "never sound like ChatGPT", severity: "warning" },
  { pattern: /\bthe possibilities are endless\b/i, reason: "ChatGPT cliché", ruleSource: "never sound like ChatGPT", severity: "error" },
  { pattern: /\bat the end of the day\b/i, reason: "ChatGPT cliché", ruleSource: "never sound like ChatGPT", severity: "warning" },
  { pattern: /\bnavigate\s+the\s+(?:complexities|landscape)\b/i, reason: "ChatGPT cliché", ruleSource: "never sound like ChatGPT", severity: "warning" },

  // Corporate-marketer CTAs and structure.
  { pattern: /\bGET\s+STARTED\s+NOW\b/, reason: "shouty CTA", ruleSource: "never sound like a corporate marketer", severity: "error" },
  { pattern: /\bSIGN\s+UP\s+(?:NOW|TODAY|FREE)\b/, reason: "shouty CTA", ruleSource: "never sound like a corporate marketer", severity: "error" },
  { pattern: /\b(?:limited[-\s]?time|act\s+now|don'?t\s+miss\s+out)\b/i, reason: "urgency-scarcity cliché", ruleSource: "never sound like a corporate marketer", severity: "error" },
  { pattern: /!/, reason: "shouty punctuation (spec asks for confident, not loud)", ruleSource: "never sound like a corporate marketer", severity: "warning" },
];

/**
 * Preferred phrases — drawn from the persona's own voice. Inline hits are
 * printed as positive credit, never as errors. The first match per copy
 * string is enough, so the report doesn't drown in positives.
 */
const PREFERRED_PHRASES: { pattern: RegExp; reason: string }[] = [
  { pattern: /\bI\b/, reason: "first-person — sounds like a person, not a brand" },
  { pattern: /\bI'?ve been testing\b/i, reason: "matches persona: 'I've been testing this all week'" },
  { pattern: /\bthis surprised me\b/i, reason: "matches persona: 'This surprised me'" },
  { pattern: /\bI'?m still experimenting\b/i, reason: "matches persona: 'I'm still experimenting'" },
  { pattern: /\bSend me the Blueprint\b/i, reason: "matches persona CTA shape (vs. 'GET STARTED NOW')" },
  { pattern: /\bdisclosed\b/i, reason: "matches persona hard_rules: AI-generated, disclosed in bio" },
];

// ── Findings + checks ──────────────────────────────────────────────────────
type Severity = "error" | "warning";

interface Finding {
  file: string;
  text: string;
  reason: string;
  ruleSource: string;
  severity: Severity;
}

interface Positive {
  file: string;
  text: string;
  reason: string;
}

/**
 * Hard-rule derived checks. These link directly to YAML text, not curated
 * phrases — so they break if the YAML text changes.
 */
interface HardRuleCheck {
  pattern: RegExp;
  reason: string;
  ruleSource: string;
}

const HARD_RULE_CHECKS: HardRuleCheck[] = [
  {
    // Unverifiable numeric claims like "2,400+ owners" with no citation.
    // Persona refuses unverifiable claims.
    pattern: /\b\d{1,3}(?:,\d{3})+(?:\+|,\d{3})?\b|\b\d+\s*[x×]\s+(?:more|less|higher|faster)\b/i,
    reason: "specific numeric claim — must be verifiable or replaced with a softer hedge",
    ruleSource: "never make unverifiable claims",
  },
  {
    // "autopilot" / "while you sleep" framing — borderline corporate-marketer
    // when combined with a numeric claim.
    pattern: /\b(?:on\s+)?autopilot\b/i,
    reason: "buzzword — replace with concrete behaviour ('runs every hour', 'replies within minutes')",
    ruleSource: "never sound like a corporate marketer",
  },
  {
    // Claims to test "every" tool — impossible absolute.
    pattern: /\b(?:test(?:s|ed)?\s+every|the\s+best|100%\s+(?:free|safe|guaranteed))\b/i,
    reason: "absolute claim — use a hedged form ('I test what I share', 'I can't vouch for everything')",
    ruleSource: "never make unverifiable claims",
  },
];

// Tracks which persona rules we've actually mapped to a check. Anything left
// out is surfaced as "unmapped" below — the drift signal.
function coveredRuleSources(): Set<string> {
  const covered = new Set<string>();
  for (const r of BANNED_PHRASES) covered.add(r.ruleSource);
  for (const r of HARD_RULE_CHECKS) covered.add(r.ruleSource);
  return covered;
}

function runChecks(copy: Extracted[], persona: Persona): {
  findings: Finding[];
  positives: Positive[];
  unmapped: string[];
} {
  const findings: Finding[] = [];
  const positives: Positive[] = [];
  const seenPositive = new Set<string>();

  for (const c of copy) {
    for (const r of BANNED_PHRASES) {
      if (r.pattern.test(c.text)) {
        findings.push({
          file: rel(c.file),
          text: c.text,
          reason: r.reason,
          ruleSource: r.ruleSource,
          severity: r.severity,
        });
      }
    }
    for (const r of HARD_RULE_CHECKS) {
      if (r.pattern.test(c.text)) {
        findings.push({
          file: rel(c.file),
          text: c.text,
          reason: r.reason,
          ruleSource: r.ruleSource,
          severity: "error",
        });
      }
    }
    for (const p of PREFERRED_PHRASES) {
      if (p.pattern.test(c.text)) {
        const key = `${c.file}::${p.reason}`;
        if (!seenPositive.has(key)) {
          seenPositive.add(key);
          positives.push({ file: rel(c.file), text: c.text, reason: p.reason });
        }
      }
    }
  }

  // Unmapped rule surfacing — a persona rule with no mechanical check
  // attached. Could be a maintainer TODO ("add a check for this rule") or
  // a sign the rule is genuinely prose-only (e.g. "never political").
  const covered = coveredRuleSources();
  const allRules = [
    ...persona.captionRules.map((r) => ({ kind: "caption", text: r })),
    ...persona.hardRules.map((r) => ({ kind: "hard", text: r })),
  ];
  const unmapped = allRules
    .filter((r) => !covered.has(r.text))
    .map((r) => `[${r.kind}] ${r.text}`);

  return { findings, positives, unmapped };
}

function rel(p: string): string {
  return p.startsWith(WEB_ROOT) ? p.slice(WEB_ROOT.length + 1) : p;
}

// ── Driver ─────────────────────────────────────────────────────────────────
function main(): void {
  const args = new Set(process.argv.slice(2));
  const wantList = args.has("--list");
  const wantJson = args.has("--json");

  if (!existsSync(PERSONA_PATH)) {
    console.error(`voice-check: persona file not found at ${PERSONA_PATH}`);
    process.exit(2);
  }
  const persona = parsePersona(readFileSync(PERSONA_PATH, "utf8"));

  const allCopy: Extracted[] = [];
  for (const src of SOURCES) {
    const full = join(WEB_ROOT, src);
    if (!existsSync(full)) {
      console.error(`voice-check: missing source ${src}`);
      process.exit(2);
    }
    allCopy.push(...extractCopy(full));
  }

  if (wantList) {
    const by = new Map<string, string[]>();
    for (const c of allCopy) {
      const arr = by.get(rel(c.file)) ?? [];
      arr.push(c.text);
      by.set(rel(c.file), arr);
    }
    for (const [file, lines] of by) {
      console.log(`\n— ${file}`);
      for (const l of lines) console.log(`   ${l}`);
    }
    return;
  }

  const { findings, positives, unmapped } = runChecks(allCopy, persona);

  // Rule-coverage report — never silent. Tell the operator which persona
  // rules have no mechanical check behind them.
  const covered = coveredRuleSources();
  const totalRules = persona.captionRules.length + persona.hardRules.length;
  const coveredCount = Math.min(covered.size, totalRules);

  const report = {
    persona: { tone: persona.tone, ruleCount: totalRules, coveredCount },
    findings,
    positives,
    unmapped,
    fileCount: SOURCES.length,
    stringCount: allCopy.length,
  };

  if (wantJson) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    const errors = findings.filter((f) => f.severity === "error");
    const warnings = findings.filter((f) => f.severity === "warning");

    console.log(`voice-check · ${SOURCES.length} files · ${allCopy.length} copy strings`);
    console.log(`persona tone: ${persona.tone || "(missing)"}`);
    console.log(`coverage: ${coveredCount}/${totalRules} persona rules mapped to a check`);
    if (unmapped.length) {
      console.log(`unmapped persona rules (prose-only — review manually):`);
      for (const u of unmapped) console.log(`  - ${u}`);
    }

    if (findings.length === 0) {
      console.log(`\n✓ no voice violations`);
    } else {
      if (errors.length) {
        console.log(`\n✗ ${errors.length} error(s):`);
        for (const f of errors) {
          console.log(`  - ${f.file}: ${f.text}`);
          console.log(`      reason: ${f.reason}`);
          console.log(`      rule:   ${f.ruleSource}`);
        }
      }
      if (warnings.length) {
        console.log(`\n! ${warnings.length} warning(s):`);
        for (const f of warnings) {
          console.log(`  - ${f.file}: ${f.text}`);
          console.log(`      reason: ${f.reason}`);
          console.log(`      rule:   ${f.ruleSource}`);
        }
      }
    }

    if (positives.length) {
      console.log(`\n✓ ${positives.length} persona-aligned phrase(s):`);
      for (const p of positives) {
        console.log(`  - ${p.file}: ${p.text.slice(0, 70)}${p.text.length > 70 ? "…" : ""}  (${p.reason})`);
      }
    }
  }

  process.exit(findings.some((f) => f.severity === "error") ? 1 : 0);
}

main();

