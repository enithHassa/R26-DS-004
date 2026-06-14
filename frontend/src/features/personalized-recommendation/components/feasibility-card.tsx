import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { RecommendationItem } from "../types";

type Props = {
  item?: RecommendationItem | null;
};

export function FeasibilityCard({ item }: Props) {
  if (!item) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Feasibility & scores</CardTitle>
          <CardDescription>
            Run Strategy Match for this profile to load feasibility and ranking breakdown.
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  const s = item.scores;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Feasibility & ranking breakdown</CardTitle>
        <CardDescription>
          Composite score from tax savings, adoption, feasibility, and risk (FR5, FR6).
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <ScoreBar label="Final rank score" value={s.final_score} max={1} highlight />
          <ScoreBar label="Tax savings (norm)" value={s.tax_savings_norm} max={1} />
          <ScoreBar label="Adoption probability" value={s.adoption_prob} max={1} />
          <ScoreBar label="Feasibility" value={s.feasibility} max={1} />
          <ScoreBar label="Risk penalty" value={s.risk_penalty} max={1} invert />
        </div>
        <p className="mt-4 text-sm text-muted-foreground">
          Estimated annual savings:{" "}
          <span className="font-medium text-foreground">{item.estimated_annual_savings} LKR</span>
          {" · "}
          Model confidence {(item.confidence * 100).toFixed(0)}%
        </p>
      </CardContent>
    </Card>
  );
}

function ScoreBar({
  label,
  value,
  max,
  highlight,
  invert,
}: {
  label: string;
  value: number;
  max: number;
  highlight?: boolean;
  invert?: boolean;
}) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const barColor = invert
    ? pct > 50
      ? "bg-amber-500"
      : "bg-emerald-500"
    : highlight
      ? "bg-primary"
      : "bg-primary/70";

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">{value.toFixed(3)}</span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
