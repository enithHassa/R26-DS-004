import { Link } from "react-router-dom";
import { BarChart3, ChevronRight } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import { recommendationCodeToCatalog } from "../constants/strategies";
import type { RecommendationItem } from "../types";
import { formatLkr } from "../utils/format-lkr";
import { AdoptionChip, ConfidenceChip, RiskChip, SavingsChip } from "./metric-chips";

type Props = {
  item: RecommendationItem;
  profileId: string;
};

export function RecommendationCard({ item, profileId }: Props) {
  const catalogCode = recommendationCodeToCatalog(item.strategy.code);

  return (
    <Card className="overflow-hidden transition-shadow hover:shadow-md">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle className="text-lg">
              <span className="text-muted-foreground">#{item.rank}</span> {item.strategy.name}
            </CardTitle>
            <CardDescription className="font-mono text-xs">{item.strategy.code}</CardDescription>
          </div>
          <div className="text-right text-sm text-muted-foreground">
            Rank score <span className="font-semibold text-foreground">{item.scores.final_score.toFixed(3)}</span>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 pt-2">
          <SavingsChip value={formatLkr(item.estimated_annual_savings)} />
          <AdoptionChip probability={item.adoption_probability} />
          <RiskChip score={item.risk_score} />
          <ConfidenceChip value={item.confidence} />
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground line-clamp-2">{item.strategy.description}</p>
        {item.explanation?.narrative && (
          <div className="rounded-md border-l-4 border-l-primary/60 bg-muted/40 p-3 text-sm">
            {item.explanation.narrative}
          </div>
        )}
        <div className="flex flex-wrap gap-4 border-t pt-3 text-sm">
          <Link
            to={`/strategy/${encodeURIComponent(catalogCode)}?profile=${profileId}`}
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            Details & SHAP
            <ChevronRight className="h-3.5 w-3.5" />
          </Link>
          <Link
            to={`/impact/${encodeURIComponent(catalogCode)}?profile=${profileId}`}
            className="inline-flex items-center gap-1 font-medium text-primary hover:underline"
          >
            <BarChart3 className="h-3.5 w-3.5" />
            Impact simulation
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
