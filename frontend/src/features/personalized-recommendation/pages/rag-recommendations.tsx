import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertTriangle, BookOpen, Brain, ChevronDown, ChevronUp, FileText, Lightbulb, Loader2, Search, ShieldCheck, Sparkles, ClipboardList } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import { listProfiles } from "../api/profiles";
import { ragQuery } from "../api/rag";
import { ProfilePicker } from "../components/profile-picker";
import { useActiveProfileId } from "../store/dashboard-store";
import type { RagDetailedExplanation, RagResultItem } from "../api/rag";

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 60 ? "bg-emerald-100 text-emerald-800" :
    pct >= 35 ? "bg-amber-100 text-amber-800" :
    "bg-gray-100 text-gray-600";
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${color}`}>
      {pct}% match
    </span>
  );
}

function CategoryBadge({ category }: { category: string }) {
  const label = category.replace(/_/g, " ");
  return (
    <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
      {label}
    </span>
  );
}

function DetailSection({
  icon,
  title,
  content,
}: {
  icon: React.ReactNode;
  title: string;
  content: string;
}) {
  return (
    <div className="rounded-md border bg-white p-3 text-sm">
      <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
      </div>
      <p className="whitespace-pre-line text-sm leading-relaxed text-black">{content}</p>
    </div>
  );
}

function DetailedPanel({ detail }: { detail: RagDetailedExplanation }) {
  return (
    <div className="mt-1 space-y-3 rounded-md border border-blue-100 bg-blue-50/50 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-blue-700">In-depth Explanation</p>
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

function ResultCard({ item, rank }: { item: RagResultItem; rank: number }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-start justify-between gap-2 text-base">
          <span>#{rank} {item.name}</span>
          <ScoreBadge score={item.similarity_score} />
        </CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <CategoryBadge category={item.category} />
          <span className="text-xs text-muted-foreground">{item.strategy_id}</span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{item.description}</p>

        <div className="rounded-md border border-blue-200 border-l-4 border-l-blue-500 bg-blue-50 p-3 text-sm">
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-blue-700">
            Why retrieved for you
          </div>
          <span className="text-black">{item.why_relevant}</span>
          <div className="mt-2.5">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white transition-colors hover:bg-blue-700"
            >
              {expanded ? (
                <><ChevronUp className="h-3 w-3" /> Hide details</>
              ) : (
                <><ChevronDown className="h-3 w-3" /> View more details</>
              )}
            </button>
          </div>
        </div>

        {expanded && <DetailedPanel detail={item.detailed_explanation} />}

        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border bg-muted/30 p-3 text-sm">
            <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <BookOpen className="h-3 w-3" />
              IRD Legal Reference
            </div>
            <span className="text-xs">{item.ird_reference}</span>
          </div>
          {item.required_docs.length > 0 && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <div className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                <FileText className="h-3 w-3" />
                Documents Required
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

export function RagRecommendationsPage() {
  const activeProfileId = useActiveProfileId();
  const [profileId, setProfileId] = useState<string>(activeProfileId ?? "");
  const [topK, setTopK] = useState<number>(5);

  useEffect(() => {
    if (activeProfileId && !profileId) setProfileId(activeProfileId);
  }, [activeProfileId, profileId]);

  const profilesQuery = useQuery({
    queryKey: ["profiles", "rag-picker"],
    queryFn: () => listProfiles({ page: 1, page_size: 50 }),
  });

  const ragMutation = useMutation({
    mutationFn: () => ragQuery({ profile_id: profileId, top_k: topK }),
  });

  const profiles = profilesQuery.data?.items ?? [];
  const canQuery = profileId.length > 0 && !ragMutation.isPending;
  const result = ragMutation.data;
  const selectedProfile = profiles.find((p) => p.id === profileId);

  return (
    <div className="space-y-6">
      <div>
        <div className="flex items-center gap-2">
          <Brain className="h-6 w-6 text-blue-600" />
          <h1 className="text-2xl font-semibold tracking-tight">Knowledge Match</h1>
        </div>
        <p className="mt-1 text-muted-foreground">
          Retrieval-Augmented Generation — strategies are retrieved by semantic similarity between
          your financial profile and the strategy knowledge base, then explained in plain English.
        </p>
      </div>

      <Card className="max-w-3xl">
        <CardHeader>
          <CardTitle>Query the Strategy Knowledge Base</CardTitle>
          <CardDescription>
            Select a profile to generate a semantic query and retrieve the most relevant tax
            strategies from the IRD-grounded strategy catalog.
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
                {selectedProfile.occupation} · {selectedProfile.district}
              </div>
            </div>
          )}

          {ragMutation.isError && (
            <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
              {(ragMutation.error as Error).message}
            </div>
          )}

          <Button onClick={() => ragMutation.mutate()} disabled={!canQuery}>
            {ragMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Retrieving…
              </>
            ) : (
              <>
                <Search className="h-4 w-4" />
                Retrieve Strategies
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {result && (
        <div className="space-y-4">
          <div className="max-w-3xl rounded-md border border-blue-200 bg-blue-50 p-3 text-sm">
            <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-blue-700">
              Semantic Query Generated from Profile
            </div>
            <code className="text-xs text-blue-900 break-all">{result.query_text}</code>
            <div className="mt-2 text-xs text-blue-600">
              Method: {result.retrieval_method}
            </div>
          </div>

          <div className="space-y-3">
            {result.items.map((item, i) => (
              <ResultCard key={item.strategy_id} item={item} rank={i + 1} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
