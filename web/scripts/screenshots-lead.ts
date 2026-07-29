// Phase 4: capture full-page screenshots at mobile (375px) and desktop (1280px).
// Saves to scripts/screenshots/lead-{mobile,desktop}.png.

import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const URL = "http://localhost:3000/lead";
const OUT_DIR = join(process.cwd(), "scripts", "screenshots");
mkdirSync(OUT_DIR, { recursive: true });

const targets: Array<{ name: string; width: number; height: number }> = [
  { name: "mobile", width: 375, height: 812 },
  { name: "desktop", width: 1280, height: 800 },
];

(async () => {
  const browser = await chromium.launch();
  for (const t of targets) {
    const context = await browser.newContext({
      viewport: { width: t.width, height: t.height },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();
    await page.goto(URL, { waitUntil: "networkidle" });
    // give webfonts a beat to settle
    await page.waitForTimeout(500);
    const file = join(OUT_DIR, `lead-${t.name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    console.log(`✓ ${t.name} (${t.width}x${t.height}) → ${file}`);
    await context.close();
  }
  await browser.close();
})().catch((err) => {
  console.error(err);
  process.exit(1);
});
