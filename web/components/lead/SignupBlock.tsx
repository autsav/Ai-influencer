"use client";

import { type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { EmailField } from "@/components/ui/EmailField";

export function SignupBlock() {
  // Second-touch signup. Same handler as Hero for Phase 1.
  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const email = data.get("email");
    // eslint-disable-next-line no-console
    console.log("[lead:signup-block] submit", { email });
  }

  return (
    <section className="bg-parchment px-6 py-24">
      <div className="mx-auto flex max-w-3xl flex-col items-start gap-7">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-terracotta">
          Get the Blueprint
        </p>

        <h2 className="font-serif text-3xl leading-tight tracking-tightish text-ink sm:text-4xl md:text-5xl">
          Stop reading about AI. Start using it.
        </h2>

        <p className="max-w-prose text-lg leading-relaxed text-ink-soft">
          Free 7-page guide. Delivered in 60 seconds. Built for SMB owners who
          want hours back, not homework.
        </p>

        <form
          onSubmit={handleSubmit}
          className="flex w-full max-w-xl flex-col gap-3 sm:flex-row sm:items-end"
          aria-label="Get the AI Workflow Blueprint (second signup)"
        >
          <div className="flex-1">
            <EmailField name="email" aria-label="Email address" required />
          </div>
          <Button
            type="submit"
            variant="terracotta"
            size="lg"
            className="sm:shrink-0"
          >
            Send me the Blueprint
          </Button>
        </form>

        <p className="text-sm text-ink-muted">
          Used by 2,400+ owners · UK · US · CA · AU · SG
        </p>
      </div>
    </section>
  );
}