import { BarChart3, MessageSquare, Star, TrendingUp, type LucideIcon } from "lucide-react";

interface ModuleCard {
  title: string;
  description: string;
  icon: LucideIcon;
  iconBg: string;
  iconColor: string;
}

const MODULES: ModuleCard[] = [
  {
    title: "Transaction Analysis",
    description:
      "AI-powered semantic classification of every bank transaction with taxability scoring and SHAP-backed reasoning.",
    icon: BarChart3,
    iconBg: "bg-blue-500/15",
    iconColor: "text-blue-400",
  },
  {
    title: "Tax Strategy Optimizer",
    description:
      "Ranked deduction strategies with composite compliance scores and 5-year financial impact projections.",
    icon: TrendingUp,
    iconBg: "bg-emerald-500/15",
    iconColor: "text-emerald-400",
  },
  {
    title: "AI Tax Advisor",
    description:
      "Neuro-symbolic SLM grounded in IRA 2017 and IRD circulars. Every answer backed by a legal proof map.",
    icon: MessageSquare,
    iconBg: "bg-violet-500/15",
    iconColor: "text-violet-400",
  },
  {
    title: "Smart Recommendations",
    description:
      "Personalized, ranked action items with adoption scores, risk ratings, and one-click impact simulations.",
    icon: Star,
    iconBg: "bg-amber-500/15",
    iconColor: "text-amber-400",
  },
];

export function DemoModulesSection() {
  return (
    <section id="features" className="px-6 py-20">
      <div className="mx-auto max-w-6xl">
        <div className="mb-14 text-center">
          <h2 className="mb-4 text-3xl font-bold tracking-tight text-[var(--demo-text)] sm:text-4xl">
            Four AI Modules. One Platform.
          </h2>
          <p className="text-lg text-[var(--demo-text-muted)]">
            Every layer of tax compliance, automated and explainable.
          </p>
        </div>

        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {MODULES.map((module) => (
            <article
              key={module.title}
              className="rounded-xl border border-[var(--demo-border)] bg-[var(--demo-bg-card)] p-6 transition-colors hover:border-slate-600/40"
            >
              <span
                className={`mb-5 inline-flex h-10 w-10 items-center justify-center rounded-lg ${module.iconBg}`}
              >
                <module.icon className={`h-5 w-5 ${module.iconColor}`} />
              </span>
              <h3 className="mb-3 text-base font-semibold text-[var(--demo-text)]">
                {module.title}
              </h3>
              <p className="text-sm leading-relaxed text-[var(--demo-text-muted)]">
                {module.description}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
