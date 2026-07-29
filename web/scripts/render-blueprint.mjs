/**
 * Aeloria — render the "AI Workflow Automation Blueprint" lead-magnet PDF.
 *
 * Reads the source markdown at docs/lead-magnet-ai-workflow-blueprint.md,
 * shapes the 10 source sections into a 7-page Claude-aesthetic booklet
 * (parchment bg, terracotta accent, Crimson Pro serif), then renders via
 * headless Chromium (Playwright) to web/public/blueprint.pdf.
 *
 * Run:    node web/scripts/render-blueprint.mjs
 * Output: web/public/blueprint.pdf  (target: exactly 7 pages, ≥ 50 KB)
 *
 * The script is zero-dep beyond playwright. It is a build-time tool, not
 * shipped to the browser — Next.js bundles the resulting PDF as a static
 * asset in /public.
 */

import { chromium } from "playwright";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const REPO_ROOT = resolve(dirname(new URL(import.meta.url).pathname), "..", "..");
const SOURCE_MD = resolve(
  REPO_ROOT,
  "docs/lead-magnet-ai-workflow-blueprint.md",
);
const OUT_PDF = resolve(REPO_ROOT, "web/public/blueprint.pdf");

// ── Markdown → sections ────────────────────────────────────────────────────
// Source file is split by `---` on its own line. We keep the raw body of each
// block as a string; per-page shaping is done by hand below (the markdown
// itself is descriptive, not a final layout spec).
function loadSections(path) {
  const raw = readFileSync(path, "utf8");
  return raw
    .split(/^---\s*$/m)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

const sections = loadSections(SOURCE_MD);

// Minimal markdown → HTML for the shapes that appear in this file:
//   `## H` → <h2>, `### H` → <h3>, `**x**` → <strong>, `*x*` → <em>,
//   `- x` → <li>, blank line → block break, numbered list → <ol>.
// Tables aren't auto-rendered — My Stack is rewritten as a hand-built
// <table> in the P5 builder below so the columns line up reliably in PDF.
function md(text) {
  const lines = text.split("\n");
  const out = [];
  let inUl = false;
  let inOl = false;
  const flushLists = () => {
    if (inUl) {
      out.push("</ul>");
      inUl = false;
    }
    if (inOl) {
      out.push("</ol>");
      inOl = false;
    }
  };
  const inline = (s) =>
    s
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");

  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line === "") {
      flushLists();
      continue;
    }
    let m;
    if ((m = line.match(/^###\s+(.+)$/))) {
      flushLists();
      out.push(`<h3>${inline(m[1])}</h3>`);
      continue;
    }
    if ((m = line.match(/^##\s+(.+)$/))) {
      flushLists();
      out.push(`<h2>${inline(m[1])}</h2>`);
      continue;
    }
    if ((m = line.match(/^(\d+)\.\s+(.+)$/))) {
      if (inUl) {
        out.push("</ul>");
        inUl = false;
      }
      if (!inOl) {
        out.push("<ol>");
        inOl = true;
      }
      out.push(`<li>${inline(m[2])}</li>`);
      continue;
    }
    if ((m = line.match(/^-\s+(.+)$/))) {
      if (inOl) {
        out.push("</ol>");
        inOl = false;
      }
      if (!inUl) {
        out.push("<ul>");
        inUl = true;
      }
      out.push(`<li>${inline(m[1])}</li>`);
      continue;
    }
    flushLists();
    out.push(`<p>${inline(line)}</p>`);
  }
  flushLists();
  return out.join("\n");
}

// Pull a section by its `## Page N — Title` heading text so we don't depend
// on index position if the source file is re-ordered later.
function findSection(predicate) {
  const idx = sections.findIndex((s) => predicate(s));
  if (idx < 0) throw new Error(`section not found: ${predicate.toString()}`);
  // Drop the `## Page N — Title` header from the body — page title is set by
  // the per-page builder so the visual style matches the cover.
  return sections[idx]
    .split("\n")
    .filter((l) => !/^##\s+Page\s+\d+\s+—/.test(l))
    .join("\n")
    .trim();
}

const sCover = findSection((s) => /^##\s+Page\s+1\s+—\s+Cover/m.test(s));
const sProblem = findSection((s) => /^##\s+Page\s+2\s+—\s+The Problem/m.test(s));
const sLies = findSection((s) => /^##\s+Page\s+3\s+—\s+The 5 Lies/m.test(s));
const sFirst = findSection((s) => /^##\s+Page\s+4\s+—\s+Your First Automation/m.test(s));
const sCore = findSection((s) => /^##\s+Page\s+5\s+—\s+The 5 Core Automations/m.test(s));
const sStack = findSection((s) => /^##\s+Page\s+6\s+—\s+My Stack/m.test(s));
const sMistakes = findSection((s) => /^##\s+Page\s+7\s+—\s+The 3 Mistakes/m.test(s));
const sSprint = findSection((s) => /^##\s+Page\s+8\s+—\s+Your 5-Day Setup Sprint/m.test(s));
const sShift = findSection((s) => /^##\s+Page\s+9\s+—\s+The Shift/m.test(s));
const sWhatsNext = findSection((s) => /^##\s+Page\s+10\s+—\s+What's Next/m.test(s));

// ── Per-page builders ───────────────────────────────────────────────────────
// Each page is wrapped in `<section class="page">` with explicit
// `page-break-after: always` so Chromium produces exactly 7 leaves.

function pageCover() {
  // Source block carries its own content lines; the visual title/subtitle/
  // footer are styled here so the cover reads as a single editorial moment.
  return `
    <section class="page cover">
      <div class="cover-eyebrow">FREE GUIDE</div>
      <h1 class="cover-title">The AI Workflow<br/>Automation Blueprint</h1>
      <p class="cover-sub">Stop doing everything yourself.<br/>Build systems that run while you sleep.</p>
      <div class="cover-foot">By Aeloria&nbsp;&nbsp;·&nbsp;&nbsp;aeloria.ai</div>
    </section>`;
}

function pageProblem() {
  // Source repeats the title in bold beneath the H2; strip the redundant
  // <p><strong>…</strong></p> line so the page doesn't echo the heading.
  const body = sProblem
    .split("\n")
    .filter((l) => !/^\*\*You're not working\. You're drowning\.\*\*\s*$/.test(l))
    .join("\n")
    .trim();
  return `
    <section class="page">
      <div class="page-eyebrow">THE PROBLEM</div>
      <h2>You're not working.<br/>You're drowning.</h2>
      ${md(body)}
    </section>`;
}

function pageLies() {
  return `
    <section class="page">
      <div class="page-eyebrow">WHAT YOU'VE BEEN TOLD</div>
      <h2>The 5 Lies About AI Entrepreneurship</h2>
      ${md(sLies)}
    </section>`;
}

function pageFirstAutomation() {
  return `
    <section class="page">
      <div class="page-eyebrow">START HERE</div>
      <h2>Your First Automation<br/><span class="muted-h">in 30 minutes</span></h2>
      ${md(sFirst)}
    </section>`;
}

function pageCoreAndStack() {
  // My Stack table — built by hand so column widths are predictable in print.
  // Source rows are the ground truth; no values are invented.
  const stackRows = [
    ["AI assistant", "ChatGPT / Claude", "$20/mo"],
    ["Scheduling", "Calendly", "Free"],
    ["Email", "Gmail (personal) + HEY (business)", "$3/mo"],
    ["Automation", "Make.com", "Free–15/mo"],
    ["CRM", "Google Sheets (yes, really)", "Free"],
    ["Content scheduling", "Buffer", "$0–15/mo"],
    ["Contracts/invoicing", "Shopify Pay or Stripe", "Free"],
  ];
  const stackTable = `
    <h3 class="section-h">My Stack — What I Actually Use</h3>
    <table class="stack">
      <thead>
        <tr><th>Task</th><th>Tool</th><th>Cost</th></tr>
      </thead>
      <tbody>
        ${stackRows
          .map(
            ([task, tool, cost]) =>
              `<tr><td>${task}</td><td>${tool}</td><td>${cost}</td></tr>`,
          )
          .join("")}
      </tbody>
    </table>
    <p class="aside"><em>You don't need 47 tools. You need 5 that talk to each other.</em></p>`;
  return `
    <section class="page">
      <div class="page-eyebrow">THE WORKHORSE LIST</div>
      <h2>The 5 Core Automations<br/>Every Solopreneur Needs</h2>
      ${md(sCore)}
      ${stackTable}
    </section>`;
}

function pageMistakesAndSprint() {
  return `
    <section class="page">
      <div class="page-eyebrow">WHAT BREAKS &amp; HOW TO SHIP</div>
      <h2>The 3 Mistakes That Kill Automations</h2>
      ${md(sMistakes)}
      <hr class="rule"/>
      <h3 class="section-h">Your 5-Day Setup Sprint</h3>
      ${md(sSprint)}
    </section>`;
}

function pageShiftAndCTA() {
  return `
    <section class="page">
      <div class="page-eyebrow">THE SHIFT</div>
      <h2>Most people think <em>"I need to do more."</em></h2>
      ${md(sShift)}
      <hr class="rule"/>
      <h3 class="section-h">What's Next</h3>
      ${md(sWhatsNext)}
      <div class="cta">
        <strong>Comment <span class="accent">WORKFLOW</span> on any of my Instagram posts</strong>
        — I'll send you the exact template I use for my client onboarding automation.
      </div>
    </section>`;
}

// ── CSS ────────────────────────────────────────────────────────────────────
// Aesthetic matches the Claude-style warm palette already wired into
// web/tailwind.config.ts (parchment / terracotta / ink). No new tokens.
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Crimson+Pro:ital,wght@0,400;0,500;0,600;0,700;1,400;1,600&display=swap');

  :root {
    --parchment: #f5f4ed;
    --parchment-ivory: #faf9f5;
    --parchment-sand: #e8e6dc;
    --parchment-border: #f0eee6;
    --terracotta: #c96442;
    --terracotta-deep: #a4502f;
    --ink: #171717;
    --ink-soft: #3a3a3a;
    --ink-muted: #595959;
  }

  @page {
    size: Letter;
    margin: 0.7in;
  }

  * { box-sizing: border-box; }

  html, body {
    margin: 0;
    padding: 0;
    background: var(--parchment);
    color: var(--ink-soft);
    font-family: "Crimson Pro", Georgia, "Times New Roman", serif;
    font-size: 9.5pt;
    line-height: 1.4;
    -webkit-font-smoothing: antialiased;
  }

  /* ── Page container ──────────────────────────────────────────────────
   * Each <section.page> must end on a fresh page. Use both the legacy
   * page-break-after and modern break-after aliases so Chromium honours
   * the break regardless of engine version. Block layout (no flex on the
   * page wrapper) keeps the page-break-after firing reliably — flex
   * parents swallowed the break in the first pass.
   */
  .page {
    page-break-after: always;
    break-after: page;
  }
  .page:last-of-type {
    page-break-after: auto;
    break-after: auto;
  }

  /* ── Cover ───────────────────────────────────────────────────────────
   * Give the cover the full printable height so the absolutely-positioned
   * footer anchors to the page bottom, not the bottom of the natural
   * content stack. Page-break-after on .page still fires on this section
   * because the cover itself is a plain block child.
   */
  .cover {
    position: relative;
    min-height: calc(10in - 1.4in);
    padding-top: 1.4in;
  }
  .cover-eyebrow {
    font-family: "Crimson Pro", Georgia, serif;
    font-size: 9pt;
    font-weight: 600;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--terracotta);
  }
  .cover-title {
    font-family: "Crimson Pro", Georgia, serif;
    font-weight: 600;
    font-size: 38pt;
    line-height: 1.06;
    letter-spacing: -0.015em;
    color: var(--ink);
    margin: 0.35in 0 0.5in 0;
  }
  .cover-sub {
    font-family: "Crimson Pro", Georgia, serif;
    font-style: italic;
    font-weight: 400;
    font-size: 14pt;
    line-height: 1.4;
    color: var(--ink-soft);
    max-width: 4.6in;
    margin: 0;
  }
  .cover-foot {
    font-family: "Crimson Pro", Georgia, serif;
    font-size: 10.5pt;
    color: var(--ink-muted);
    letter-spacing: 0.02em;
    /* Pinned to the bottom of the cover page so the title/subtitle can
     * flow at their natural position without flex distribution. */
    position: absolute;
    left: 0;
    bottom: 0.6in;
  }

  /* ── Content pages ─────────────────────────────────────────────────── */
  .page-eyebrow {
    font-family: "Crimson Pro", Georgia, serif;
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 0.28em;
    text-transform: uppercase;
    color: var(--terracotta);
    margin-bottom: 0.16in;
  }
  h2 {
    font-family: "Crimson Pro", Georgia, serif;
    font-weight: 600;
    font-size: 18pt;
    line-height: 1.14;
    letter-spacing: -0.01em;
    color: var(--ink);
    margin: 0 0 0.10in 0;
  }
  h3 {
    font-family: "Crimson Pro", Georgia, serif;
    font-weight: 600;
    font-size: 11pt;
    line-height: 1.25;
    color: var(--ink);
    margin: 0.12in 0 0.04in 0;
  }
  .section-h {
    margin-top: 0.14in;
    padding-top: 0.08in;
    border-top: 1px solid var(--parchment-border);
  }
  .muted-h {
    color: var(--ink-muted);
    font-weight: 500;
  }
  p {
    margin: 0 0 0.08in 0;
    max-width: 70ch;
  }
  strong { color: var(--ink); font-weight: 600; }
  em { color: var(--ink); }
  ul, ol {
    margin: 0 0 0.08in 0;
    padding-left: 1.2em;
    max-width: 70ch;
  }
  li {
    margin-bottom: 0.02in;
  }
  li::marker { color: var(--terracotta); }

  ol li { padding-left: 0.15em; }

  code {
    font-family: "SFMono-Regular", Menlo, Consolas, monospace;
    font-size: 0.92em;
    background: var(--parchment-ivory);
    border: 1px solid var(--parchment-border);
    border-radius: 3px;
    padding: 0.02in 0.08in;
    color: var(--ink);
  }

  /* ── Stack table (P5) ──────────────────────────────────────────────── */
  table.stack {
    width: 100%;
    border-collapse: collapse;
    margin: 0.04in 0 0.04in 0;
    font-size: 9pt;
    border-top: 1px solid var(--parchment-border);
    border-bottom: 1px solid var(--parchment-border);
  }
  table.stack th {
    text-align: left;
    font-weight: 600;
    color: var(--ink);
    padding: 0.04in 0.05in 0.03in 0;
    border-bottom: 1px solid var(--ink);
    font-size: 8pt;
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }
  table.stack td {
    padding: 0.03in 0.05in 0.03in 0;
    border-bottom: 1px solid var(--parchment-border);
    color: var(--ink-soft);
    vertical-align: top;
  }
  table.stack tr:last-child td { border-bottom: none; }
  table.stack td:last-child {
    color: var(--ink-muted);
    font-variant-numeric: tabular-nums;
    text-align: right;
    width: 1.2in;
  }
  .aside {
    color: var(--ink-muted);
    font-style: italic;
    margin-top: 0.04in;
  }

  /* ── Section break rule (P6, P7) ───────────────────────────────────── */
  .rule {
    border: 0;
    height: 1px;
    background: var(--terracotta);
    opacity: 0.35;
    margin: 0.24in 0 0.14in 0;
  }

  /* ── CTA block (P7) ────────────────────────────────────────────────── */
  .cta {
    margin-top: 0.20in;
    padding: 0.18in 0.20in;
    background: var(--parchment-ivory);
    border: 1px solid var(--parchment-border);
    border-left: 3px solid var(--terracotta);
    font-size: 11pt;
    color: var(--ink);
    line-height: 1.45;
  }
  .cta .accent {
    color: var(--terracotta);
    font-weight: 700;
    letter-spacing: 0.02em;
  }
`;

// ── Assemble document ──────────────────────────────────────────────────────
const html = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8"/>
    <title>The AI Workflow Automation Blueprint — Aeloria</title>
    <style>${css}</style>
  </head>
  <body>
    ${pageCover()}
    ${pageProblem()}
    ${pageLies()}
    ${pageFirstAutomation()}
    ${pageCoreAndStack()}
    ${pageMistakesAndSprint()}
    ${pageShiftAndCTA()}
  </body>
</html>`;

// ── Render via headless Chromium ───────────────────────────────────────────
mkdirSync(dirname(OUT_PDF), { recursive: true });

const browser = await chromium.launch();
try {
  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  // data: URL keeps the build offline-safe. `networkidle` lets the Google
  // Fonts @import complete (or time out to system fallback) before we print.
  await page.setContent(html, { waitUntil: "networkidle", timeout: 30000 });
  await page.emulateMedia({ media: "print" });
  await page.pdf({
    path: OUT_PDF,
    format: "Letter",
    printBackground: true,
    margin: { top: "0.7in", bottom: "0.7in", left: "0.7in", right: "0.7in" },
    preferCSSPageSize: false,
  });
} finally {
  await browser.close();
}

// Optional debug artefact: keep the rendered HTML alongside the PDF so a
// reviewer can diff layout without re-running Chromium. Overwritten each run.
writeFileSync(OUT_PDF.replace(/\.pdf$/, ".html"), html, "utf8");

console.log(`render-blueprint: wrote ${OUT_PDF}`);