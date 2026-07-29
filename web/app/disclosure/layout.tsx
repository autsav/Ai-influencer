import type { Metadata } from "next";
import { Inter, Crimson_Pro } from "next/font/google";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});
const crimson = Crimson_Pro({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Disclosure · Aeloria",
  description:
    "What's human and what's automated on Aeloria — full transparency about the AI persona, image generation, and editorial decisions.",
};

// Disclosure layout — same font + surface setup as app/lead/layout.tsx so the
// /disclosure page reads as part of the same warm Claude-aesthetic surface.
export default function DisclosureLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className={`${inter.variable} ${crimson.variable} bg-parchment text-ink min-h-screen font-sans`}
    >
      {children}
    </div>
  );
}