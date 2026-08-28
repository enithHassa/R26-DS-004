import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { listProfiles } from "../api/profiles";
import { generateRecommendations } from "../api/recommendations";
import { PageHeader } from "../components/page-header";
import { ProfilePicker } from "../components/profile-picker";
import { RecommendationCard } from "../components/recommendation-card";
import { useActiveProfileId, useDashboardStore } from "../store/dashboard-store";
import { formatLkr } from "../utils/format-lkr";

export function RecommendationsPage() {
  const activeProfileId = useActiveProfileId();
  const lastRecommendations = useDashboardStore((s) => s.lastRecommendations);
  const setLastRecommendations = useDashboardStore((s) => s.setLastRecommendations);

  const [profileId, setProfileId] = useState(activeProfileId ?? "");
  const [topK, setTopK] = useState(5);

  useEffect(() => {
    if (activeProfileId && !profileId) setProfileId(activeProfileId);
  }, [activeProfileId, profileId]);

  const profilesQuery = useQuery({
    queryKey: ["profiles", "recommendation-picker"],
    queryFn: () => listProfiles({ page: 1, page_size: 50 }),
  });

  const recommendationsMutation = useMutation({
    mutationFn: () =>
      generateRecommendations({
        profile_id: profileId,
        top_k: topK,
        regenerate_candidates: false,
      }),
    onSuccess: (data) => setLastRecommendations(data),
  });

  const profiles = profilesQuery.data?.items ?? [];
  const canGenerate = profileId.length > 0 && !recommendationsMutation.isPending;
  const generated = recommendationsMutation.data ?? lastRecommendations;
  const selectedProfile = profiles.find((p) => p.id === profileId);

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Sparkles}
        title="Strategy recommendations"
        description="Top-K ranked strategies with savings, adoption probability, risk, and confidence."
      />

      <Card className="max-w-3xl border-t-4 border-t-primary/70">
        <CardHeader>
          <CardTitle>Generate ranked list</CardTitle>
          <CardDescription>
            LambdaMART ranking with rule-based feasibility filtering from the strategy catalog.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <ProfilePicker value={profileId} onChange={setProfileId} />
            <div className="space-y-1.5">
              <Label>Top K</Label>
              <Select value={String(topK)} onChange={(e) => setTopK(Number(e.target.value))}>
                {[3, 5, 7, 10].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {selectedProfile && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="font-medium">{selectedProfile.full_name}</div>
              <div className="text-muted-foreground">
                {selectedProfile.occupation} · {selectedProfile.district} ·{" "}
                {formatLkr(selectedProfile.gross_monthly_income)}/month
              </div>
            </div>
          )}

          {recommendationsMutation.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
              {(recommendationsMutation.error as Error).message}
            </div>
          )}

          <Button onClick={() => recommendationsMutation.mutate()} disabled={!canGenerate}>
            {recommendationsMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Ranking strategies…
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4" />
                Generate recommendations
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {generated && (
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">
            Model <span className="font-medium">{generated.model_version}</span> ·{" "}
            {new Date(generated.generated_at).toLocaleString()} · {generated.items.length} strategies
          </div>
          {generated.items.length === 0 && (
            <Card>
              <CardContent className="pt-6 text-sm text-muted-foreground">
                No eligible strategies found for this profile.
              </CardContent>
            </Card>
          )}
          <div className="grid gap-4">
            {generated.items.map((item) => (
              <RecommendationCard key={item.id} item={item} profileId={profileId} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
