import {
  Clock4,
  Layers3,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";

interface Card {
  icon: LucideIcon;
  title: string;
  body: string;
}

const cards: Card[] = [
  {
    icon: Clock4,
    title: "Save 15 hours/week",
    body: "Workflows that reply to leads, file invoices, and update your CRM while you sleep.",
  },
  {
    icon: Layers3,
    title: "Replace 6 apps with 1",
    body: "One AI assistant that handles email, scheduling, research, and reporting — for the price of a coffee.",
  },
  {
    icon: TrendingUp,
    title: "3× more leads, same budget",
    body: "Automated outreach and follow-up that runs on autopilot — without sounding like a robot.",
  },
];

export function ValueProps() {
  return (
    <section className="bg-parchment px-6 py-24">
      <div className="mx-auto flex max-w-5xl flex-col gap-12">
        <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
          <h2 className="font-serif text-2xl leading-tight text-ink sm:text-3xl">
            Built for owners who&rsquo;d rather save time than learn theory.
          </h2>
          <span className="h-[2px] w-12 rounded-full bg-terracotta" />
        </div>

        <ul className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {cards.map(({ icon: Icon, title, body }) => (
            <li
              key={title}
              className="flex flex-col gap-3 rounded-lg border border-parchment-border bg-parchment-ivory p-6"
            >
              <Icon
                aria-hidden="true"
                className="h-6 w-6 text-terracotta"
                strokeWidth={1.5}
              />
              <h3 className="font-serif text-xl leading-snug text-ink">
                {title}
              </h3>
              <p className="text-sm leading-relaxed text-ink-soft">{body}</p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}