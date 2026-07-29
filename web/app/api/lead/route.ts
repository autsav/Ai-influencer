import { NextResponse, type NextRequest } from "next/server";
import { sendLeadEmail } from "@/lib/resend";

// In-memory rate limit: 5 POSTs per IP per hour. Single-instance only —
// fine for a lead-capture form on a single-server Railway deploy.
const RATE_LIMIT_MAX = 5;
const RATE_LIMIT_WINDOW_MS = 60 * 60 * 1000; // 1 hour
const ipBuckets = new Map<string, number[]>();

// Prune stale entries every 30 min so the Map doesn't grow forever.
const now = Date.now();
let lastPrune = now;
function pruneIfNeeded(currentTime: number) {
  if (currentTime - lastPrune < 30 * 60 * 1000) return;
  lastPrune = currentTime;
  const cutoff = currentTime - RATE_LIMIT_WINDOW_MS;
  for (const [ip, stamps] of ipBuckets) {
    const fresh = stamps.filter((t) => t > cutoff);
    if (fresh.length === 0) {
      ipBuckets.delete(ip);
    } else {
      ipBuckets.set(ip, fresh);
    }
  }
}

// Standard email regex — strict enough to reject garbage, lenient enough
// to accept all real addresses. Server-side only.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function getClientIp(req: NextRequest): string {
  // Trust x-forwarded-for first (Railway / Vercel proxy), fall back to
  // x-real-ip, then a constant so rate-limit still works in dev.
  const fwd = req.headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0].trim();
  const real = req.headers.get("x-real-ip");
  if (real) return real.trim();
  return "unknown";
}

function isRateLimited(ip: string): boolean {
  const currentTime = Date.now();
  pruneIfNeeded(currentTime);
  const cutoff = currentTime - RATE_LIMIT_WINDOW_MS;
  const stamps = (ipBuckets.get(ip) ?? []).filter((t) => t > cutoff);
  if (stamps.length >= RATE_LIMIT_MAX) {
    ipBuckets.set(ip, stamps);
    return true;
  }
  stamps.push(currentTime);
  ipBuckets.set(ip, stamps);
  return false;
}

export async function POST(req: NextRequest) {
  const ip = getClientIp(req);

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ ok: false, error: "Invalid JSON" }, { status: 400 });
  }

  if (!body || typeof body !== "object") {
    return NextResponse.json({ ok: false, error: "Invalid body" }, { status: 400 });
  }

  const { email, website } = body as { email?: unknown; website?: unknown };

  // Honeypot: real users never fill this. Bots do. Return 200 silently so
  // the bot thinks it succeeded and stops trying.
  if (typeof website === "string" && website.trim() !== "") {
    return NextResponse.json({ ok: true });
  }

  if (typeof email !== "string" || !EMAIL_RE.test(email.trim())) {
    return NextResponse.json(
      { ok: false, error: "Invalid email" },
      { status: 400 },
    );
  }

  if (isRateLimited(ip)) {
    return NextResponse.json(
      { ok: false, error: "Too many requests" },
      { status: 429 },
    );
  }

  const result = await sendLeadEmail(email.trim().toLowerCase());
  if (!result.ok) {
    // Log internally; return generic error to caller.
    console.error("[lead] resend failed", { ip, error: result.error });
    return NextResponse.json(
      { ok: false, error: "Could not subscribe. Try again later." },
      { status: 502 },
    );
  }

  return NextResponse.json({ ok: true });
}
