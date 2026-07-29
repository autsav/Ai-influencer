"use client";

import { type FormEvent } from "react";
import { Button } from "@/components/ui/Button";
import { EmailField } from "@/components/ui/EmailField";

export function Hero() {
  // Phase 1: console.log only. Phase 2 wires /api/lead → Resend.
  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    const email = data.get("email");
    // eslint-disable-next-line no-console
    console.log("[lead:hero] submit", { email });
  }

  return (
    <section className="px-6 pt-20 pb-24 sm:pt-28 md:pt-32">
      <div className="mx-auto flex max-w-3xl flex-col items-start gap-7">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-terracotta">
          From Aeloria · 24-year-old AI entrepreneur
        </p>

        <h1 className="font-serif text-4xl leading-[1.05] tracking-tightish text-ink sm:text-5xl md:text-6xl">
          I save 15 hours a week with AI. Here&rsquo;s the blueprint.
        </h1>

        <p className="max-w-prose font-sans text-lg leading-relaxed text-ink-soft sm:text-xl">
          A free 7-page guide to the AI workflows I actually use to run my
          business. Built for owners who&rsquo;d rather save time than learn
          theory.
        </p>

        <form
          onSubmit={handleSubmit}
          className="flex w-full max-w-xl flex-col gap-3 sm:flex-row sm:items-end"
          aria-label="Get the AI Workflow Blueprint"
        >
          <div className="flex-1">
            <EmailField
              name="email"
              aria-label="Email address"
              required
            />
          </div>
          <Button type="submit" variant="ink" size="lg" className="sm:shrink-0">
            Send me the Blueprint
          </Button>
        </form>

        <p className="text-sm text-ink-muted">
          No spam. Unsubscribe in one click. 2,400+ business owners already get
          this.
        </p>
      </div>
    </section>
  );
}