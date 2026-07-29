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
  title: "Aeloria · AI Workflow Blueprint (free 7-page guide)",
  description:
    "Free 7-page guide to the AI workflows a 24-year-old AI entrepreneur actually uses to save 15+ hours a week. Built for SMB owners who'd rather save time than learn theory.",
};

// Lead layout registers serif + sans font CSS variables and applies the warm
// parchment surface. Wrapped (not nested) so the dashboard's dark root
// styles don't bleed in.
export default function LeadLayout({
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