import { LeadForm } from "@/components/lead/LeadForm";

export function SignupBlock() {
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

        <LeadForm
          buttonVariant="terracotta"
          ariaLabel="Get the AI Workflow Blueprint (second signup)"
        />

        <p className="text-sm text-ink-muted">
          Used by 2,400+ owners · UK · US · CA · AU · SG
        </p>
      </div>
    </section>
  );
}
