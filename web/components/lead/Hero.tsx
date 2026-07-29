import { LeadForm } from "@/components/lead/LeadForm";

export function Hero() {
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

        <LeadForm
          buttonVariant="ink"
          ariaLabel="Get the AI Workflow Blueprint"
        />

        <p className="text-sm text-ink-muted">
          No spam. Unsubscribe in one click. Owners across UK, US, CA, AU, SG
          already get this.
        </p>
      </div>
    </section>
  );
}
