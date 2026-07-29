"use client";

import {
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { Button } from "@/components/ui/Button";
import { EmailField } from "@/components/ui/EmailField";

type Status = "idle" | "submitting" | "success" | "error";

interface Props {
  /** Variant drives the submit button color. Hero = ink, SignupBlock = terracotta. */
  buttonVariant: "ink" | "terracotta";
  /** Form id used for aria-label. */
  ariaLabel: string;
  /** Optional override for className on the form row. */
  className?: string;
  /** Optional content rendered after a successful submit (replaces form). */
  successExtra?: ReactNode;
}

const SUCCESS_MESSAGE = "Check your inbox.";
const ERROR_MESSAGE = "Something went wrong, try again.";

/**
 * Shared form for the lead-capture page. Hero and SignupBlock both render
 * this with different button variants. Owns the submit / loading / success
 * / error state machine so the calling sections stay presentational.
 */
export function LeadForm({
  buttonVariant,
  ariaLabel,
  className,
  successExtra,
}: Props) {
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState<string>(ERROR_MESSAGE);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (status === "submitting") return;

    const form = e.currentTarget;
    const data = new FormData(form);
    const email = String(data.get("email") ?? "").trim();
    const website = String(data.get("website") ?? "").trim();

    setStatus("submitting");
    setErrorMsg(ERROR_MESSAGE);

    try {
      const res = await fetch("/api/lead", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, website }),
      });

      if (res.status === 429) {
        setErrorMsg("Too many attempts. Try again later.");
        setStatus("error");
        return;
      }

      if (!res.ok) {
        setStatus("error");
        return;
      }

      const json = (await res.json()) as { ok?: boolean };
      if (json.ok) {
        setStatus("success");
        form.reset();
        return;
      }
      setStatus("error");
    } catch {
      setStatus("error");
    }
  }

  if (status === "success") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="flex max-w-xl flex-col items-start gap-2 rounded-md border border-parchment-border bg-white px-5 py-4"
      >
        <p className="font-serif text-xl text-ink">{SUCCESS_MESSAGE}</p>
        <p className="text-sm text-ink-muted">
          The blueprint should land in your inbox in under a minute. If it
          doesn&rsquo;t, check spam or try again.
        </p>
        {successExtra}
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      aria-label={ariaLabel}
      className={className}
    >
      <div className="flex w-full max-w-xl flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <EmailField
            name="email"
            aria-label="Email address"
            required
            disabled={status === "submitting"}
          />
        </div>
        <Button
          type="submit"
          variant={buttonVariant}
          size="lg"
          className="sm:shrink-0"
          disabled={status === "submitting"}
        >
          {status === "submitting" ? "Sending…" : "Send me the Blueprint"}
        </Button>
      </div>

      {/* Honeypot — hidden from real users, visible to bots. Must stay empty. */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          left: "-10000px",
          top: "auto",
          width: 1,
          height: 1,
          overflow: "hidden",
        }}
      >
        <label htmlFor="lead-website">Website</label>
        <input
          id="lead-website"
          name="website"
          type="text"
          tabIndex={-1}
          autoComplete="off"
        />
      </div>

      {status === "error" ? (
        <p
          role="alert"
          className="mt-2 text-sm text-terracotta-deep"
        >
          {errorMsg}
        </p>
      ) : null}
    </form>
  );
}
