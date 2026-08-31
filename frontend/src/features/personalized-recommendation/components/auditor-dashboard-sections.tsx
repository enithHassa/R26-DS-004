import type { ComponentType } from "react";
import { Link } from "react-router-dom";
import {
  BarChart3,
  Briefcase,
  Coins,
  Gauge,
  PiggyBank,
  Sparkles,
  UserRound,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { HybridResultItem } from "../api/hybrid";
import { AdoptionEvidenceModal } from "./adoption-evidence-panel";
import { AuditorImpactDetailSections } from "./auditor-recommendations/auditor-impact-detail-sections";
import type { DerivedFeatures, FinancialProfile, ImpactSimulationResponse } from "../types";
import type { AdoptionEvidence } from "../utils/adoption-evidence";
import { formatLkr } from "../utils/format-lkr";

function titleCase(s: string): string {
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function ageFromDob(dob: string): number {
  const d = new Date(dob);
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  if (now.getMonth() < d.getMonth() || (now.getMonth() === d.getMonth() && now.getDate() < d.getDate())) {
    age--;
  }
  return age;
}

function MetricTile({
  label,
  value,
  sub,
  tone = "default",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "default" | "danger" | "success" | "accent";
}) {
  const toneClass = {
    default: "text-foreground",
    danger: "text-rose-600",
    success: "text-emerald-600",
    accent: "text-primary",
  }[tone];

  return (
    <div className="rounded-xl border border-border/70 bg-card/90 p-4 shadow-sm backdrop-blur-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className={cn("mt-1.5 text-xl font-bold tabular-nums tracking-tight", toneClass)}>{value}</p>
      {sub && <p className="mt-1 text-[11px] text-muted-foreground">{sub}</p>}
    </div>
  );
}

export function AuditorKpiStrip({
  features,
  topItem,
}: {
  features: DerivedFeatures | undefined;
  topItem: HybridResultItem | undefined;
}) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <MetricTile
        label="Baseline tax liability"
        value={features ? formatLkr(features.baseline_tax_liability_annual) : "—"}
        sub="Annual · derived from profile"
        tone="danger"
      />
      <MetricTile
        label="Top strategy savings"
        value={topItem ? formatLkr(topItem.estimated_annual_savings) : "—"}
        sub={topItem?.name ?? "Select a taxpayer"}
        tone="success"
      />
      <MetricTile
        label="Adoption probability"
        value={topItem ? `${(topItem.adoption_probability * 100).toFixed(0)}%` : "—"}
        sub="Rank #1 hybrid score input"
        tone="accent"
      />
      <MetricTile
        label="Effective tax rate"
        value={features ? `${(features.effective_tax_rate * 100).toFixed(1)}%` : "—"}
        sub={
          features
            ? `Disposable ${formatLkr(features.disposable_income_monthly)}/mo`
            : undefined
        }
      />
    </div>
  );
}

export function AuditorTaxpayerCard({
  profile,
  features,
}: {
  profile: FinancialProfile;
  features: DerivedFeatures | undefined;
}) {
  return (
    <Card className="h-full border-border/70 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <UserRound className="h-4 w-4 text-primary" />
          Taxpayer
        </CardTitle>
        <CardDescription>Financial context for this case review</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-3 rounded-xl border bg-muted/30 p-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
            {profile.full_name.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="truncate font-semibold">{profile.full_name}</div>
            <div className="text-xs text-muted-foreground">
              {titleCase(profile.occupation)} · {profile.district} · {ageFromDob(profile.date_of_birth)} yrs
            </div>
          </div>
        </div>

        <SectionLabel icon={Briefcase} label="Income & cash flow" />
        <div className="grid grid-cols-2 gap-2">
          <MiniStat label="Gross income" value={`${formatLkr(profile.gross_monthly_income)}/mo`} />
          <MiniStat label="Expenses" value={`${formatLkr(profile.monthly_expenses)}/mo`} />
          <MiniStat label="Debt service" value={`${formatLkr(profile.monthly_debt_service)}/mo`} />
          <MiniStat
            label="Savings rate"
            value={features ? `${(features.savings_rate * 100).toFixed(1)}%` : "—"}
          />
        </div>

        <SectionLabel icon={PiggyBank} label="Balance sheet" />
        <div className="grid grid-cols-2 gap-2">
          <MiniStat label="Liquid savings" value={formatLkr(profile.liquid_savings)} />
          <MiniStat label="Investments" value={formatLkr(profile.existing_investments)} />
          <MiniStat label="Total debt" value={formatLkr(profile.total_debt)} />
          <MiniStat label="EPF" value={formatLkr(profile.epf_balance)} />
        </div>

        <SectionLabel icon={Coins} label="Reliefs & risk" />
        <div className="grid grid-cols-2 gap-2">
          <MiniStat
            label="Health cover"
            value={profile.health_insurance ? "Yes" : "No"}
          />
          <MiniStat label="Risk tolerance" value={titleCase(profile.risk_tolerance)} />
          <MiniStat label="Life premium/yr" value={formatLkr(profile.life_insurance_premium_annual)} />
          <MiniStat label="Horizon" value={`${profile.investment_horizon_years} yrs`} />
        </div>
      </CardContent>
    </Card>
  );
}

function SectionLabel({ icon: Icon, label }: { icon: ComponentType<{ className?: string }>; label: string }) {
  return (
    <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      <Icon className="h-3.5 w-3.5" />
      {label}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-background/60 px-2.5 py-2">
      <div className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 truncate text-sm font-semibold">{value}</div>
    </div>
  );
}

export function AuditorRecommendationsPanel({
  items,
  selectedId,
  onSelect,
  isLoading,
}: {
  items: HybridResultItem[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  isLoading: boolean;
}) {
  return (
    <Card className="h-full border-border/70 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Sparkles className="h-4 w-4 text-primary" />
          Recommendations
        </CardTitle>
        <CardDescription>
          Ranked strategy names — open Smart Recommendations for full detail.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Ranking strategies…</p>}
        {!isLoading && items.length === 0 && (
          <p className="text-sm text-muted-foreground">No eligible strategies for this profile.</p>
        )}
        {!isLoading && items.length > 0 && (
          <ol className="divide-y divide-border/70 rounded-xl border border-border/70">
            {items.map((item) => {
              const active = item.strategy_id === selectedId;
              return (
                <li key={item.strategy_id}>
                  <button
                    type="button"
                    onClick={() => onSelect(item.strategy_id)}
                    className={cn(
                      "flex w-full items-center gap-3 px-4 py-3 text-left transition-colors",
                      active
                        ? "bg-primary/[0.06] text-foreground"
                        : "hover:bg-muted/30",
                    )}
                  >
                    <span
                      className={cn(
                        "flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold tabular-nums",
                        active
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted text-muted-foreground",
                      )}
                    >
                      {item.rank}
                    </span>
                    <span className={cn("font-medium leading-snug", active && "font-semibold")}>
                      {item.name}
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  );
}

const VERDICT_BADGE: Record<AdoptionEvidence["verdict"], string> = {
  strong: "border-emerald-300 bg-emerald-50 text-emerald-800",
  moderate: "border-amber-300 bg-amber-50 text-amber-900",
  weak: "border-rose-300 bg-rose-50 text-rose-800",
};

export function AuditorAdoptionPanel({
  evidence,
  strategyName,
  onOpenDetail,
}: {
  evidence: AdoptionEvidence | null;
  strategyName: string;
  onOpenDetail: () => void;
}) {
  if (!evidence) {
    return (
      <Card className="h-full border-border/70 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Gauge className="h-4 w-4 text-primary" />
            Adoption evidence
          </CardTitle>
          <CardDescription>Select a recommendation to inspect uptake signals</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const metCount = evidence.signals.filter((s) => s.met).length;

  return (
    <Card className="h-full border-border/70 shadow-sm">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <Gauge className="h-4 w-4 text-primary" />
          Adoption evidence
        </CardTitle>
        <CardDescription>Trend checks vs model probability — {strategyName}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <span
            className={cn(
              "inline-flex rounded-full border px-2.5 py-0.5 text-xs font-semibold",
              VERDICT_BADGE[evidence.verdict],
            )}
          >
            {evidence.verdict === "strong"
              ? "Likely to adopt"
              : evidence.verdict === "moderate"
                ? "Possibly adopts"
                : "Unlikely to adopt"}
          </span>
          <span className="text-sm text-muted-foreground">
            Model {(evidence.adoptionProbability * 100).toFixed(0)}% · {metCount}/{evidence.signals.length}{" "}
            signals met
          </span>
        </div>

        <p className="rounded-lg border-l-4 border-l-primary/60 bg-muted/30 p-3 text-sm leading-relaxed">
          {evidence.verdictSummary}
        </p>

        <div className="space-y-2">
          {evidence.signals.slice(0, 4).map((signal) => (
            <div
              key={signal.key}
              className={cn(
                "rounded-lg border px-3 py-2 text-sm",
                signal.met ? "border-emerald-200 bg-emerald-50/50" : "border-rose-200 bg-rose-50/40",
              )}
            >
              <div className="font-medium">{signal.label}</div>
              <div className="text-xs text-muted-foreground">{signal.detail}</div>
            </div>
          ))}
        </div>

        <Button type="button" variant="outline" size="sm" className="w-full" onClick={onOpenDetail}>
          Open full evidence report
        </Button>
      </CardContent>
    </Card>
  );
}

export function AuditorImpactPanel({
  profileId,
  primaryResult,
  selectedItem,
  isLoading,
  error,
  strategyName,
}: {
  profileId: string;
  primaryResult: ImpactSimulationResponse | undefined;
  selectedItem?: HybridResultItem;
  isLoading: boolean;
  error?: string | null;
  strategyName: string | null;
}) {
  const impactLabHref =
    selectedItem && profileId
      ? `/impact/${encodeURIComponent(selectedItem.strategy_id)}?${new URLSearchParams({
          profile: profileId,
          rank: String(selectedItem.rank),
          name: selectedItem.name,
        }).toString()}`
      : null;

  return (
    <Card className="border-border/70 shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="flex items-center gap-2 text-base">
              <BarChart3 className="h-4 w-4 text-primary" />
              Financial impact
            </CardTitle>
            <CardDescription>
              2-year Monte Carlo projection
              {strategyName ? ` · ${strategyName}` : ""}
            </CardDescription>
          </div>
          {impactLabHref && (
            <Button variant="outline" size="sm" asChild>
              <Link to={impactLabHref}>Open in Impact Lab</Link>
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <AuditorImpactDetailSections
          primaryResult={primaryResult}
          selectedItem={selectedItem}
          strategyName={strategyName ?? "Selected strategy"}
          isLoading={isLoading}
          error={error}
        />
      </CardContent>
    </Card>
  );
}

export function AuditorEvidenceModalHost({
  open,
  evidence,
  strategyName,
  onClose,
}: {
  open: boolean;
  evidence: AdoptionEvidence | null;
  strategyName: string;
  onClose: () => void;
}) {
  if (!open || !evidence) return null;
  return <AdoptionEvidenceModal evidence={evidence} strategyName={strategyName} onClose={onClose} />;
}
