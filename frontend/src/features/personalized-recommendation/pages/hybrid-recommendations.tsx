import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertTriangle, BookOpen, ChevronDown, ChevronUp,
  ClipboardList, FileText, LineChart, Lightbulb, Loader2,
  Merge, Search, ShieldCheck, Sparkles,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { listProfiles, getProfileHistory } from "../api/profiles";
import { hybridQuery } from "../api/hybrid";
import type { HybridResultItem } from "../api/hybrid";
import type { RagDetailedExplanation } from "../api/rag";
import type { ProfileHistorySnapshot } from "../types";
import { AdoptionEvidenceModal } from "../components/adoption-evidence-panel";
import { PageHeader } from "../components/page-header";
import { computeAdoptionEvidence } from "../utils/adoption-evidence";

function formatLkr(value: number): string {
  return new Intl.NumberFormat("en-LK", {
    style: "currency",
    currency: "LKR",
    maximumFractionDigits: 0,
  }).format(value);
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold">{pct}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted">
        <div
          className={`h-1.5 rounded-full ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function HybridBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 70 ? "bg-primary/15 text-primary" :
    pct >= 45 ? "bg-amber-100 text-amber-800" :
    "bg-muted text-muted-foreground";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${color}`}>
      <Merge className="h-3 w-3" />
      {pct}% hybrid
    </span>
  );
}

function CategoryBadge({ category }: { category: string }) {
  return (
    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
      {category}
    </span>
  );
}

function DetailSection({ icon, title, content }: {
  icon: React.ReactNode; title: string; content: string;
}) {
  return (
    <div className="rounded-md border bg-white p-3 text-sm">
      <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}{title}
      </div>
      <p className="whitespace-pre-line text-sm leading-relaxed text-black">{content}</p>
    </div>
  );
}

function DetailedPanel({ detail }: { detail: RagDetailedExplanation }) {
  return (
    <div className="mt-1 space-y-3 rounded-md border border-primary/15 bg-primary/[0.04] p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-primary">In-depth Explanation</p>
      <div className="grid gap-3 sm:grid-cols-2">
        <DetailSection icon={<Lightbulb className="h-3 w-3" />} title="What it means" content={detail.what_it_means} />
        <DetailSection icon={<ShieldCheck className="h-3 w-3" />} title="Why you qualify" content={detail.why_you_qualify} />
      </div>
      <DetailSection icon={<ClipboardList className="h-3 w-3" />} title="What to do — step by step" content={detail.what_to_do} />
      <div className="grid gap-3 sm:grid-cols-2">
        <DetailSection icon={<Sparkles className="h-3 w-3" />} title="Potential benefit" content={detail.potential_benefit} />
        <DetailSection icon={<AlertTriangle className="h-3 w-3" />} title="Risk level" content={detail.risk_level} />
      </div>
    </div>
  );
}

function ResultCard({ item, history }: { item: HybridResultItem; history: ProfileHistorySnapshot[] | undefined }) {
  const [expanded, setExpanded] = useState(false);
  const [evidenceOpen, setEvidenceOpen] = useState(false);

  const evidence = history
    ? computeAdoptionEvidence(history, item.adoption_probability, item.estimated_annual_savings)
    : null;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="flex items-center gap-2 text-base">
              <span>#{item.rank} {item.name}</span>
              <HybridBadge score={item.hybrid_score} />
            </CardTitle>
            <div className="mt-1.5 flex flex-wrap items-center gap-2">
              <CategoryBadge category={item.category} />
              <span className="text-xs text-muted-foreground">{item.strategy_id}</span>
            </div>
          </div>
          {evidence && (
            <button
              onClick={() => setEvidenceOpen(true)}
              className="inline-flex shrink-0 items-center gap-1.5 rounded-md border border-emerald-300 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800 shadow-sm transition-colors hover:bg-emerald-100"
            >
              <LineChart className="h-3 w-3" />
              Will this user adopt?
            </button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{item.description}</p>

        {/* Score breakdown */}
        <div className="rounded-md border bg-muted/30 p-3 space-y-2">
          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-2">Score Breakdown</p>
          <ScoreBar label={`LambdaMART (×0.7)`} value={item.lambdamart_score} color="bg-emerald-500" />
          <ScoreBar label={`RAG Similarity (×0.3)`} value={item.rag_similarity_score} color="bg-blue-500" />
          <ScoreBar label="Hybrid Score (final)" value={item.hybrid_score} color="bg-primary" />
          <div className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
            <div className="rounded border bg-white p-1.5">
              <div className="text-muted-foreground">Adoption</div>
              <div className="font-semibold">{(item.adoption_probability * 100).toFixed(1)}%</div>
            </div>
            <div className="rounded border bg-white p-1.5">
              <div className="text-muted-foreground">Confidence</div>
              <div className="font-semibold">{(item.confidence * 100).toFixed(1)}%</div>
            </div>
            <div className="rounded border bg-white p-1.5">
              <div className="text-muted-foreground">Est. Savings</div>
              <div className="font-semibold">{formatLkr(item.estimated_annual_savings)}</div>
            </div>
          </div>
        </div>

        {/* Why retrieved */}
        <div className="rounded-md border border-primary/20 border-l-4 border-l-primary bg-primary/[0.04] p-3 text-sm">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">
            Why this applies to you
          </div>
          <span className="text-foreground">{item.why_relevant}</span>
          <div className="mt-2.5">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-colors hover:opacity-90"
            >
              {expanded
                ? <><ChevronUp className="h-3 w-3" /> Hide details</>
                : <><ChevronDown className="h-3 w-3" /> View more details</>}
            </button>
          </div>
        </div>

        {expanded && <DetailedPanel detail={item.detailed_explanation} />}

        {evidence && evidenceOpen && (
          <AdoptionEvidenceModal
            evidence={evidence}
            strategyName={item.name}
            onClose={() => setEvidenceOpen(false)}
          />
        )}

        {/* IRD + docs */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border bg-muted/30 p-3 text-sm">
            <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <BookOpen className="h-3 w-3" /> IRD Legal Reference
            </div>
            <span className="text-xs">{item.ird_reference}</span>
          </div>
          {item.required_docs.length > 0 && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                <FileText className="h-3 w-3" /> Documents Required
              </div>
              <ul className="space-y-0.5">
                {item.required_docs.map((doc) => (
                  <li key={doc} className="text-xs text-muted-foreground">
                    · {doc.replace(/_/g, " ")}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function HybridRecommendationsPage() {
  const [profileId, setProfileId] = useState<string>("");
  const [topK, setTopK] = useState<number>(5);
  const [lambdaWeight, setLambdaWeight] = useState<number>(0.7);

  const profilesQuery = useQuery({
    queryKey: ["profiles", "hybrid-picker"],
    queryFn: () => listProfiles({ page: 1, page_size: 50 }),
  });

  const hybridMutation = useMutation({
    mutationFn: () =>
      hybridQuery({ profile_id: profileId, top_k: topK, lambda_weight: lambdaWeight }),
  });

  const historyQuery = useQuery({
    queryKey: ["profile-history", profileId],
    queryFn: () => getProfileHistory(profileId, 36),
    enabled: profileId.length > 0,
  });

  const profiles = profilesQuery.data?.items ?? [];
  const canQuery = profileId.length > 0 && !hybridMutation.isPending;
  const result = hybridMutation.data;
  const selectedProfile = profiles.find((p) => p.id === profileId);

  return (
    <div className="space-y-6">
      <PageHeader icon={Merge} title="Smart Recommendations" />

      <Card className="max-w-3xl border-t-4 border-t-primary/70">
        <CardHeader>
          <CardTitle>Generate Smart Recommendations</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label>Profile</Label>
              <Select
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                disabled={profilesQuery.isLoading}
              >
                <option value="">
                  {profilesQuery.isLoading ? "Loading…" : "Select a profile"}
                </option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.full_name} · {p.occupation}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Top K</Label>
              <Select value={String(topK)} onChange={(e) => setTopK(Number(e.target.value))}>
                {[3, 5, 7, 10].map((n) => (
                  <option key={n} value={n}>{n}</option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>LambdaMART Weight (α)</Label>
              <Select
                value={String(lambdaWeight)}
                onChange={(e) => setLambdaWeight(Number(e.target.value))}
              >
                {[
                  { val: 0.5, label: "0.5 / 0.5 — Equal" },
                  { val: 0.6, label: "0.6 / 0.4 — Balanced" },
                  { val: 0.7, label: "0.7 / 0.3 — Recommended" },
                  { val: 0.8, label: "0.8 / 0.2 — Model-heavy" },
                  { val: 0.9, label: "0.9 / 0.1 — Near-model" },
                ].map(({ val, label }) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </Select>
            </div>
          </div>

          {selectedProfile && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="font-medium">{selectedProfile.full_name}</div>
              <div className="text-muted-foreground">
                {selectedProfile.occupation} · {selectedProfile.district}
              </div>
            </div>
          )}

          {hybridMutation.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
              {(hybridMutation.error as Error).message}
            </div>
          )}

          <Button onClick={() => hybridMutation.mutate()} disabled={!canQuery}>
            {hybridMutation.isPending ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Generating…</>
            ) : (
              <><Search className="h-4 w-4" /> Generate Smart Recommendations</>
            )}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4">
          <div className="space-y-3">
            {result.items.map((item) => (
              <ResultCard key={item.strategy_id} item={item} history={historyQuery.data} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
