import { Star } from "lucide-react";

import { cn } from "@/lib/utils";

import { formatLkr } from "../utils/format-lkr";

type TaxpayerRecommendationPreviewRowProps = {
  rank: number;
  title: string;
  savings: string;
  className?: string;
};

/** Compact row — rank badge, strategy title, star + savings (TaxWise dashboard style). */
export function TaxpayerRecommendationPreviewRow({
  rank,
  title,
  savings,
  className,
}: TaxpayerRecommendationPreviewRowProps) {
  return (
    <div className={cn("flex items-start gap-3", className)}>
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--uv-accent)]/15 text-xs font-semibold text-[var(--uv-accent)]">
        {rank}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-snug text-[var(--uv-text)]">{title}</p>
        <p className="mt-1 flex items-center gap-1 text-sm font-semibold text-[var(--uv-accent)]">
          <Star className="h-3.5 w-3.5 shrink-0 fill-[var(--uv-accent)]/20" />
          {formatLkr(savings)}
        </p>
      </div>
    </div>
  );
}
