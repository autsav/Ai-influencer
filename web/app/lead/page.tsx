import { Hero } from "@/components/lead/Hero";
import { ValueProps } from "@/components/lead/ValueProps";
import { Trust } from "@/components/lead/Trust";
import { SignupBlock } from "@/components/lead/SignupBlock";
import { Footer } from "@/components/lead/Footer";

// Phase 1 visual scaffold. All five sections from the design spec.
// Form submission = console.log only. /api/lead + Resend land in Phase 2.
export default function LeadPage() {
  return (
    <main>
      <Hero />
      <ValueProps />
      <Trust />
      <SignupBlock />
      <Footer />
    </main>
  );
}