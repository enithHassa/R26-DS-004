import { cn } from "@/lib/utils";

import { relevanceBand } from "./language-model-display";

interface RelevanceMeterProps {
  score: number;
  maxScore: number;
  showRawScore?: boolean;
}

const toneStyles = {
  strong: "bg-emerald-600",
  good: "bg-primary",
  moderate: "bg-amber-500",
  low: "bg-muted-foreground/50",
} as const;

export function RelevanceMeter({ score, maxScore, showRawScore = false }: RelevanceMeterProps) {
  const band = relevanceBand(score, maxScore);

  return (
    <div className="flex min-w-[9rem] flex-col items-end gap-1 text-right">
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-foreground">{band.label}</span>
        <span className="text-xs tabular-nums text-muted-foreground">{band.percent}%</span>
      </div>
      <div className="h-1.5 w-28 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all", toneStyles[band.tone])}
          style={{ width: `${Math.max(band.percent, 6)}%` }}
        />
      </div>
      {showRawScore ? (
        <span className="text-[11px] tabular-nums text-muted-foreground/80">
          score {score.toFixed(4)}
        </span>
      ) : null}
    </div>
  );
}
