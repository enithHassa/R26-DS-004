import { useNavigate } from "react-router-dom";
import { BookOpen, Eye, Merge } from "lucide-react";

import { cn } from "@/lib/utils";

import type { HybridResultItem } from "../../api/hybrid";
import { formatLkr } from "../../utils/format-lkr";
import { AuditorMetricBar } from "./metric-bar";

type Props = {
  item: HybridResultItem;
  profileId: string;
  onExplain: () => void;
};

function auditRiskLabel(level: string): { label: string; tone: "low" | "medium" | "high" } {
  const normalized = level.toLowerCase();
  if (normalized === "high") return { label: "High", tone: "high" };
  if (normalized === "medium") return { label: "Medium", tone: "medium" };
  return { label: "Low", tone: "low" };
}

function feasibilityLabel(value: number): { label: string; tone: "high" | "medium" | "low" } {
  if (value >= 0.75) return { label: "High", tone: "high" };
  if (value >= 0.5) return { label: "Medium", tone: "medium" };
  return { label: "Low", tone: "low" };
}

function chipClass(tone: "low" | "medium" | "high", kind: "risk" | "feasibility") {
  if (kind === "risk") {
    return tone === "low"
      ? "border-emerald-300 bg-emerald-50 text-emerald-800"
      : tone === "medium"
        ? "border-amber-300 bg-amber-50 text-amber-900"
        : "border-rose-300 bg-rose-50 text-rose-800";
  }
  return tone === "high"
    ? "border-emerald-300 bg-emerald-50 text-emerald-800"
    : tone === "medium"
      ? "border-amber-300 bg-amber-50 text-amber-900"
      : "border-border bg-muted text-muted-foreground";
}

export function AuditorHybridRecommendationCard({ item, profileId, onExplain }: Props) {
  const navigate = useNavigate();
  const auditRisk = auditRiskLabel(item.strategy_audit_risk ?? "medium");
  const feasibility = feasibilityLabel(item.confidence);
  const adoptionPct = (item.adoption_probability * 100).toFixed(1);

  const viewImpact = () => {
    const params = new URLSearchParams({
      profile: profileId,
      rank: String(item.rank),
      name: item.name,
    });
    navigate(`/impact/${encodeURIComponent(item.strategy_id)}?${params.toString()}`);
  };

  return (
    <article className="rounded-xl border border-border/70 bg-card p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-lg font-bold tracking-tight">
          <span className="mr-2 text-muted-foreground">#{item.rank}</span>
          {item.name}
        </h3>
        <span className="rounded-full border bg-muted/50 px-2.5 py-0.5 text-[10px] font-medium text-muted-foreground">
          {item.category}
        </span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {item.description || item.why_relevant}
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        <span className="inline-flex rounded-md border border-emerald-300 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-800">
          Tax Saving: {formatLkr(item.estimated_annual_savings)}
        </span>
        <span className="inline-flex rounded-md border border-sky-300 bg-sky-50 px-2.5 py-1 text-xs font-medium text-sky-900">
          Adoption probability: {adoptionPct}%
        </span>
        <span
          className={cn(
            "inline-flex rounded-md border px-2.5 py-1 text-xs font-medium",
            chipClass(auditRisk.tone, "risk"),
          )}
          title={`Strategy audit-risk band (low 5%, medium 12%, high 20% base penalty). Combined score: ${(item.risk_score * 100).toFixed(0)}%`}
        >
          Audit risk: {auditRisk.label}
        </span>
        <span
          className={cn(
            "inline-flex rounded-md border px-2.5 py-1 text-xs font-medium",
            chipClass(feasibility.tone, "feasibility"),
          )}
        >
          Feasibility: {feasibility.label}
        </span>
      </div>

      <div className="mt-5 rounded-lg border bg-muted/20 p-3">
        <p className="mb-3 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <Merge className="h-3.5 w-3.5" />
          Ranker scores
        </p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <AuditorMetricBar label="LambdaMART (tax fit)" value={item.lambdamart_score} colorClass="bg-emerald-500" />
          <AuditorMetricBar label="Retrieval (RAG)" value={item.rag_similarity_score} colorClass="bg-sky-500" />
          <AuditorMetricBar
            label="Retrieval hybrid"
            value={item.retrieval_hybrid_score ?? item.hybrid_score}
            colorClass="bg-violet-500"
          />
          <AuditorMetricBar
            label="Final Rank"
            value={item.fusion_score ?? item.hybrid_score}
            colorClass="bg-primary"
          />
        </div>
        <p className="mt-2 text-[11px] text-muted-foreground">
          Final rank blends tax fit (40%), adoption (30%), feasibility (20%), risk fit (12%), minus audit-risk penalty (10%).
        </p>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <AuditorMetricBar label="Compliance" value={item.confidence} colorClass="bg-sky-500" />
        <AuditorMetricBar
          label="Risk fit"
          value={item.risk_alignment ?? 1}
          colorClass="bg-emerald-500"
        />
        <AuditorMetricBar
          label="Rank penalty"
          value={item.risk_score}
          colorClass="bg-rose-500"
        />
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={viewImpact}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
        >
          <Eye className="h-4 w-4" />
          View Impact
        </button>
        <button
          type="button"
          onClick={onExplain}
          className="inline-flex items-center gap-2 rounded-lg border border-primary/30 px-4 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/5"
        >
          <BookOpen className="h-4 w-4" />
          Explanation
        </button>
      </div>
    </article>
  );
}
