/**
 * Focused test for /api/lead route. Monkey-patches globalThis.fetch to
 * mock the Resend API responses so we can verify the route returns 200
 * on a valid email without sending real emails.
 *
 * Run: npx tsx scripts/test-lead-route.ts
 */
import { POST } from "../app/api/lead/route";
import { NextRequest } from "next/server";

type FetchMock = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

// Save the original fetch, install a mock that responds 200 to anything
// hitting api.resend.com, then restore.
const originalFetch = globalThis.fetch;
(globalThis as any).fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
  const url = typeof input === "string" ? input : input.toString();
  if (url.includes("api.resend.com")) {
    return new Response(
      JSON.stringify({ id: "mock-id-123", object: "email" }),
      { status: 200, headers: { "content-type": "application/json" } },
    );
  }
  return (originalFetch as FetchMock)(input, init);
}) as typeof fetch;

function makeRequest(body: unknown, ip = "1.2.3.4") {
  return new NextRequest("http://localhost:3000/api/lead", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-forwarded-for": ip,
    },
    body: JSON.stringify(body),
  });
}

async function expectStatus(name: string, req: NextRequest, want: number) {
  const res = await POST(req);
  const json = await res.json().catch(() => null);
  const ok = res.status === want;
  console.log(
    `[${ok ? "PASS" : "FAIL"}] ${name}: status=${res.status} want=${want} body=${JSON.stringify(json)}`,
  );
  if (!ok) process.exitCode = 1;
  return res;
}

async function run() {
  // 1. Valid email → 200 (success path with mocked resend)
  await expectStatus(
    "valid email",
    makeRequest({ email: "user@example.com" }),
    200,
  );

  // 2. Invalid email → 400
  await expectStatus(
    "invalid email",
    makeRequest({ email: "not-an-email" }),
    400,
  );

  // 3. Honeypot filled → 200 silent
  await expectStatus(
    "honeypot filled",
    makeRequest({ email: "bot@spam.com", website: "http://spam.com" }),
    200,
  );

  // 4. Rate limit: 6 valid from same IP → 6th is 429
  const ip = "9.9.9.9";
  for (let i = 1; i <= 5; i++) {
    await expectStatus(
      `rate-limit req ${i}/5`,
      makeRequest({ email: `user${i}@example.com` }, ip),
      200,
    );
  }
  await expectStatus(
    "rate-limit req 6 (429)",
    makeRequest({ email: "user6@example.com" }, ip),
    429,
  );

  // Bonus: honeypot does NOT consume rate limit.
  await expectStatus(
    "honeypot after rate limit (still 200)",
    makeRequest({ email: "bot@spam.com", website: "x" }, ip),
    200,
  );

  console.log("\nDone.");
}

run()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => {
    (globalThis as any).fetch = originalFetch;
  });
