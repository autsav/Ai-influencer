import { Resend } from "resend";

// Server-side Resend client. Lazy-init so missing env in build doesn't crash
// until the function is actually called at runtime.
let _client: Resend | null = null;
function getClient(): Resend {
  if (_client) return _client;
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    throw new Error("RESEND_API_KEY is not set");
  }
  _client = new Resend(apiKey);
  return _client;
}

export type LeadEmailResult =
  | { ok: true; id: string }
  | { ok: false; error: string };

/**
 * Add a new lead to the Resend audience (contact list) and trigger the
 * welcome email. The audience is configured via RESEND_AUDIENCE_ID.
 *
 * Returns a discriminated result instead of throwing so the route handler
 * can decide how to surface failures (always 200 to caller, log internally).
 */
export async function sendLeadEmail(email: string): Promise<LeadEmailResult> {
  const audienceId = process.env.RESEND_AUDIENCE_ID;
  if (!audienceId) {
    return { ok: false, error: "RESEND_AUDIENCE_ID is not set" };
  }

  const fromAddress =
    process.env.RESEND_FROM_EMAIL ?? "Aeloria <hello@aeloria.ai>";

  try {
    const client = getClient();

    // 1. Add contact to the configured audience.
    const contact = await client.contacts.create({
      email,
      audienceId,
      unsubscribed: false,
    });

    if (contact.error) {
      return { ok: false, error: contact.error.message };
    }

    // 2. Send the welcome email with the blueprint link.
    const sent = await client.emails.send({
      from: fromAddress,
      to: email,
      subject: "Your AI Workflow Blueprint is here",
      html: blueprintEmailHtml(),
      text: blueprintEmailText(),
    });

    if (sent.error) {
      return { ok: false, error: sent.error.message };
    }

    return { ok: true, id: sent.data?.id ?? "unknown" };
  } catch (err) {
    return {
      ok: false,
      error: err instanceof Error ? err.message : "unknown error",
    };
  }
}

function blueprintEmailText(): string {
  return [
    "Hey,",
    "",
    "Here's your AI Workflow Blueprint — the 7-page guide to the workflows I",
    "actually use to run my business and save 15 hours a week.",
    "",
    "Download: https://aeloria.ai/blueprint.pdf",
    "",
    "If you ever want to stop reading it, hit reply and I'll unsubscribe you.",
    "No hard feelings.",
    "",
    "— Aeloria",
  ].join("\n");
}

function blueprintEmailHtml(): string {
  return [
    '<p>Hey,</p>',
    "<p>Here's your AI Workflow Blueprint — the 7-page guide to the workflows I",
    " actually use to run my business and save 15 hours a week.</p>",
    '<p><a href="https://aeloria.ai/blueprint.pdf">Download the blueprint</a></p>',
    "<p>If you ever want to stop reading it, hit reply and I'll unsubscribe you.",
    " No hard feelings.</p>",
    "<p>— Aeloria</p>",
  ].join("\n");
}
