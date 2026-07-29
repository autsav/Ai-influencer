import Link from "next/link";

const automated: { label: string; body: string }[] = [
  {
    label: "Image generation",
    body: "FLUX.1 with a custom LoRA trained on the same character across every post.",
  },
  {
    label: "Some caption drafting",
    body: "Drafts, not finals. Every caption is reviewed before it goes out.",
  },
  {
    label: "Content scheduling",
    body: "Posts go live at the times my audience is most active.",
  },
  {
    label: "Analytics collection",
    body: "Reach, saves, replies, follower trends. The numbers behind what works.",
  },
];

const human: { label: string; body: string }[] = [
  {
    label: "Editorial strategy",
    body: "What to post about this week, this month, this quarter.",
  },
  {
    label: "Tool selection",
    body: "Every tool I share has been tested in my own business before I recommend it.",
  },
  {
    label: "Voice and tone",
    body: "The way the captions read is mine, not the model's.",
  },
  {
    label: "Replies to DMs and comments",
    body: "I read and respond to the inbox personally.",
  },
  {
    label: "The decision of what to publish vs. skip",
    body: "Some drafts never see the light of day. That call is mine.",
  },
];

function Section({
  eyebrow,
  title,
  items,
}: {
  eyebrow: string;
  title: string;
  items: { label: string; body: string }[];
}) {
  return (
    <section className="px-6 py-14 sm:py-16">
      <div className="mx-auto flex max-w-3xl flex-col gap-7">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-terracotta-deep">
          {eyebrow}
        </p>
        <h2 className="font-serif text-3xl leading-tight tracking-tightish text-ink sm:text-4xl">
          {title}
        </h2>
        <ul className="flex flex-col divide-y divide-parchment-border">
          {items.map((it) => (
            <li key={it.label} className="flex gap-5 py-5 first:pt-0 last:pb-0">
              <span
                aria-hidden="true"
                className="w-[2px] shrink-0 self-stretch rounded-full bg-terracotta/70"
              />
              <div className="flex flex-col gap-1">
                <p className="font-serif text-lg leading-snug text-ink">
                  {it.label}
                </p>
                <p className="font-sans text-base leading-relaxed text-ink-soft">
                  {it.body}
                </p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default function DisclosurePage() {
  return (
    <main className="pb-20">
      <header className="px-6 pt-20 pb-12 sm:pt-28">
        <div className="mx-auto flex max-w-3xl flex-col gap-7">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-terracotta-deep">
            Transparency
          </p>
          <h1 className="font-serif text-4xl leading-[1.05] tracking-tightish text-ink sm:text-5xl md:text-6xl">
            What Aeloria is &mdash; and isn&rsquo;t.
          </h1>
          <p className="max-w-prose font-sans text-lg leading-relaxed text-ink-soft sm:text-xl">
            Aeloria is an AI-generated virtual influencer. Every image you see
            is AI-generated. Some captions are AI-drafted, then reviewed by a
            human editor (me). The persona strategy, the editorial decisions,
            the tool recommendations, the business opinions &mdash; those are
            human-curated.
          </p>
        </div>
      </header>

      <div className="mx-auto max-w-3xl px-6">
        <hr className="border-0 h-px bg-terracotta/30" />
      </div>

      <Section
        eyebrow="What's automated"
        title="What the machine does"
        items={automated}
      />

      <div className="mx-auto max-w-3xl px-6">
        <hr className="border-0 h-px bg-terracotta/30" />
      </div>

      <Section
        eyebrow="What's human"
        title="What I do"
        items={human}
      />

      <div className="mx-auto max-w-3xl px-6">
        <hr className="border-0 h-px bg-terracotta/30" />
      </div>

      <section className="px-6 py-14 sm:py-16">
        <div className="mx-auto flex max-w-3xl flex-col gap-7">
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-terracotta-deep">
            Why this matters
          </p>
          <p className="max-w-prose font-sans text-lg leading-relaxed text-ink-soft sm:text-xl">
            Every AI workflow I share is one I have actually used. I
            don&rsquo;t recommend tools I haven&rsquo;t tested. The AI persona
            is a tool for me to share real workflow knowledge &mdash; not a
            way to fake expertise.
          </p>
        </div>
      </section>

      <footer className="px-6 pt-8">
        <div className="mx-auto flex max-w-3xl flex-col gap-3 text-sm text-ink-muted sm:flex-row sm:items-center sm:justify-between">
          <p>Last updated &middot; 29 July 2026</p>
          <Link
            href="/"
            className="hover:text-terracotta transition-colors"
          >
            &larr; Back to the blueprint
          </Link>
        </div>
      </footer>
    </main>
  );
}