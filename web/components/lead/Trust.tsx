const signals: string[] = [
  "Featured in my AI Workflow Blueprint — the PDF thousands of business owners have downloaded.",
  "I test the workflows I share in my own business.",
  "Disclosed AI persona — full transparency about what's human and what's automated.",
];

export function Trust() {
  return (
    <section className="bg-parchment-sand/60 px-6 py-20">
      <div className="mx-auto flex max-w-3xl flex-col gap-8">
        <p className="text-xs font-medium uppercase tracking-[0.18em] text-terracotta">
          Trust
        </p>

        <ul className="flex flex-col divide-y divide-parchment-border">
          {signals.map((line, i) => (
            <li
              key={i}
              className="flex gap-5 py-5 first:pt-0 last:pb-0"
            >
              {/* Thin terracotta vertical rule between signals */}
              <span
                aria-hidden="true"
                className="w-[2px] shrink-0 self-stretch rounded-full bg-terracotta/70"
              />
              <p className="font-serif text-lg leading-relaxed text-ink sm:text-xl">
                {line}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}