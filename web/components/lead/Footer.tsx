import Link from "next/link";

const links: { label: string; href: string }[] = [
  { label: "About", href: "/about" },
  { label: "Instagram", href: "https://instagram.com/aeloria.ai" },
  { label: "Newsletter Archive", href: "/archive" },
  { label: "Disclosure", href: "/disclosure" },
];

export function Footer() {
  return (
    <footer className="bg-parchment-sand px-6 py-10">
      <div className="mx-auto flex max-w-5xl flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <span className="font-serif text-lg text-ink">Aeloria</span>
          <span className="text-xs text-ink-muted">
            AI entrepreneur · UK
          </span>
        </div>

        <nav
          aria-label="Footer"
          className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-soft"
        >
          {links.map(({ label, href }) => (
            <Link
              key={label}
              href={href}
              className="hover:text-terracotta transition-colors"
            >
              {label}
            </Link>
          ))}
        </nav>

        <p className="text-xs text-ink-muted">
          Made with AI, disclosed honestly.
        </p>
      </div>
    </footer>
  );
}