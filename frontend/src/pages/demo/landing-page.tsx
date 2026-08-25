import { DemoCtaSection } from "@/pages/demo/components/demo-cta-section";
import { DemoHeader } from "@/pages/demo/components/demo-header";
import { DemoHero } from "@/pages/demo/components/demo-hero";
import { DemoModulesSection } from "@/pages/demo/components/demo-modules-section";
import { DemoStatsBar } from "@/pages/demo/components/demo-stats-bar";
import "@/pages/demo/demo-theme.css";

export function DemoLandingPage() {
  return (
    <div className="demo-landing">
      <DemoHeader />
      <main>
        <DemoHero />
        <DemoStatsBar />
        <DemoModulesSection />
        <DemoCtaSection />
      </main>
    </div>
  );
}
