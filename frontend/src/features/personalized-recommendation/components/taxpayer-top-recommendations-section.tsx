import { Link } from "react-router-dom";

import { TAXWISE_RECOMMENDATIONS } from "@/pages/user-view/paths";

import { useTaxpayerRecommendations } from "../hooks/use-taxpayer-recommendations";
import { TaxpayerRecommendationPreviewRow } from "./taxpayer-recommendation-preview-row";

type TaxpayerTopRecommendationsSectionProps = {
  profileId: string;
  /** How many rows to show on the dashboard preview. */
  limit?: number;
  showViewAll?: boolean;
};

export function TaxpayerTopRecommendationsSection({
  profileId,
  limit = 3,
  showViewAll = true,
}: TaxpayerTopRecommendationsSectionProps) {
  const recommendationsQuery = useTaxpayerRecommendations(profileId);
  const items = (recommendationsQuery.data?.items ?? []).slice(0, limit);

  return (
    <section className="rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] lg:col-span-2">
      <div className="flex items-center justify-between border-b border-[var(--uv-border)] px-5 py-4">
        <h2 className="font-semibold text-[var(--uv-text)]">Top Recommendations</h2>
        {showViewAll && (
          <Link
            to={TAXWISE_RECOMMENDATIONS}
            className="text-sm font-medium text-[var(--uv-accent)] transition-colors hover:text-[var(--uv-accent-hover)] hover:underline"
          >
            View all
          </Link>
        )}
      </div>

      {recommendationsQuery.isLoading && (
        <p className="px-5 py-6 text-sm text-[var(--uv-text-muted)]">Loading your recommendations…</p>
      )}

      {recommendationsQuery.isError && (
        <p className="px-5 py-6 text-sm text-red-400">{(recommendationsQuery.error as Error).message}</p>
      )}

      {!recommendationsQuery.isLoading && !recommendationsQuery.isError && items.length === 0 && (
        <p className="px-5 py-6 text-sm text-[var(--uv-text-muted)]">
          No recommendations yet — complete your profile to get personalized tips.
        </p>
      )}

      {items.length > 0 && (
        <ul className="divide-y divide-[var(--uv-border)]/60">
          {items.map((item) => (
            <li key={item.id} className="px-5 py-4">
              <TaxpayerRecommendationPreviewRow
                rank={item.rank}
                title={item.strategy.name}
                savings={item.estimated_annual_savings}
              />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
