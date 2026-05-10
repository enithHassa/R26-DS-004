import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Loader2, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { listProfiles } from "../api/profiles";
import { generateRecommendations } from "../api/recommendations";

function formatLkr(value: string | number): string {
  const num = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(num)) return String(value);
  return new Intl.NumberFormat("en-LK", {
    style: "currency",
    currency: "LKR",
    maximumFractionDigits: 0,
  }).format(num);
}

export function RecommendationsPage() {
  const [profileId, setProfileId] = useState<string>("");
  const [topK, setTopK] = useState<number>(5);

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
  });

  const profiles = profilesQuery.data?.items ?? [];
  const canGenerate = profileId.length > 0 && !recommendationsMutation.isPending;
  const generated = recommendationsMutation.data;

  const selectedProfile = profiles.find((p) => p.id === profileId);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Recommendations</h1>
        <p className="text-muted-foreground">
          Top-K ranked tax strategies with estimated savings, adoption probability,
          and confidence (FR5, FR6, FR9, FR11).
        </p>
      </div>

      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Generate top-K strategy recommendations</CardTitle>
          <CardDescription>
            Uses your trained artifacts plus rule feasibility filtering from the
            strategy catalog.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Profile</Label>
              <Select
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                disabled={profilesQuery.isLoading}
              >
                <option value="">
                  {profilesQuery.isLoading ? "Loading profiles…" : "Select a profile"}
                </option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} · {p.occupation} · {p.district}
                  </option>
                ))}
              </Select>
            </div>
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

          <div>
            <Button onClick={() => recommendationsMutation.mutate()} disabled={!canGenerate}>
              {recommendationsMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating…
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4" />
                  Generate Recommendations
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {generated && (
        <div className="space-y-3">
          <div className="text-sm text-muted-foreground">
            Model version: <span className="font-medium">{generated.model_version}</span> ·
            generated {new Date(generated.generated_at).toLocaleString()}
          </div>
          {generated.items.length === 0 && (
            <Card>
              <CardContent className="pt-6 text-sm text-muted-foreground">
                No eligible strategies found for this profile.
              </CardContent>
            </Card>
          )}
          {generated.items.map((item) => (
            <Card key={item.id}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>
                    #{item.rank} {item.strategy.name}
                  </span>
                  <span className="text-sm font-normal text-muted-foreground">
                    Score {item.scores.final_score.toFixed(3)}
                  </span>
                </CardTitle>
                <CardDescription>{item.strategy.code}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-muted-foreground">{item.strategy.description}</p>
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4 text-sm">
                  <Metric label="Estimated annual savings" value={formatLkr(item.estimated_annual_savings)} />
                  <Metric label="Adoption probability" value={`${(item.adoption_probability * 100).toFixed(1)}%`} />
                  <Metric label="Confidence" value={`${(item.confidence * 100).toFixed(1)}%`} />
                  <Metric label="Risk score" value={item.risk_score.toFixed(3)} />
                </div>
                {item.explanation?.narrative && (
                  <div className="rounded border bg-muted/40 p-3 text-xs text-muted-foreground">
                    {item.explanation.narrative}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}
