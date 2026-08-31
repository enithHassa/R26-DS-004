import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, ChevronDown, Loader2, RefreshCw, Scale } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";

import {
  getCatalogRulesStatus,
  previewCatalogRules,
  syncCatalogRules,
  type CatalogPreviewMetadata,
  type RulesFieldDiff,
} from "../api/catalog-rules";

type Props = {
  useCatalogRules: boolean;
  onUseCatalogRulesChange: (value: boolean) => void;
  assessmentYear: string;
  onAssessmentYearChange: (value: string) => void;
  onSynced?: () => void;
};

function formatYa(yearKey: string): string {
  const [start, end] = yearKey.split("_");
  if (!start || !end) return yearKey;
  return `${start}/${end}`;
}

function formatPromotedAt(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

function MetadataPanel({ meta }: { meta: CatalogPreviewMetadata }) {
  const promotedLabel = formatPromotedAt(meta.promoted_at);

  return (
    <div className="space-y-3 rounded-md border bg-muted/20 p-3 text-xs">
      <div className="flex items-start gap-2">
        <BookOpen className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
        <div className="min-w-0 space-y-2">
          <p className="font-medium text-foreground">{meta.assessment_period}</p>
          {promotedLabel && (
            <p className="text-muted-foreground">
              Promoted via Adaptive Tax catalog-admin
              {meta.promotion_source ? ` (${meta.promotion_source.replace(/_/g, " ")})` : ""}
              {" · "}
              {promotedLabel}
            </p>
          )}
          {meta.carried_forward_from && (
            <p className="text-muted-foreground">
              Carried forward from YA {formatYa(meta.carried_forward_from)}
              {meta.watcher_source_doc_id ? ` · source ${meta.watcher_source_doc_id}` : ""}
            </p>
          )}
          <p className="text-muted-foreground">
            Compared against {meta.default_rules_label} (version {meta.default_rules_version})
          </p>
          <p className="text-muted-foreground">
            Catalog contains {meta.relief_entries_count} relief entries and {meta.rate_bands_count}{" "}
            APIT rate bands for this year.
          </p>
        </div>
      </div>

      {meta.legal_references.length > 0 && (
        <div className="space-y-2 border-t pt-3">
          <p className="font-medium text-foreground">Legal basis (quote-gated extracts)</p>
          {meta.legal_references.map((ref) => (
            <div key={ref.label} className="rounded-md border bg-background/80 p-2.5">
              <p className="font-medium text-foreground">{ref.label}</p>
              <p className="mt-0.5 text-muted-foreground">
                {ref.act_name}
                {ref.section_ref ? ` · ${ref.section_ref}` : ""}
                {ref.source_doc_id ? ` · ${ref.source_doc_id}` : ""}
              </p>
              {ref.effective_from ? (
                <p className="mt-0.5 text-muted-foreground">Effective from {ref.effective_from}</p>
              ) : null}
              {ref.quote_excerpt ? (
                <p className="mt-1.5 italic leading-relaxed text-muted-foreground">
                  “{ref.quote_excerpt}”
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-2 border-t pt-3 sm:grid-cols-2">
        <div>
          <p className="font-medium text-foreground">Updated from catalog</p>
          <p className="mt-0.5 font-mono text-[11px] text-emerald-700 dark:text-emerald-400">
            {meta.mapped_fields.join(", ") || "—"}
          </p>
        </div>
        <div>
          <p className="font-medium text-foreground">Still from default YAML</p>
          <p className="mt-0.5 text-muted-foreground">
            Deduction caps (insurance, rent, etc.) and provident rates
          </p>
        </div>
      </div>

      {meta.catalog_notes ? (
        <p className="border-t pt-3 text-muted-foreground">{meta.catalog_notes}</p>
      ) : null}
    </div>
  );
}

function DiffTable({ diffs }: { diffs: RulesFieldDiff[] }) {
  if (diffs.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        No numeric differences vs the default YAML pack for this year.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-foreground">Rule changes vs default pack</p>
      <div className="overflow-x-auto rounded-md border text-xs">
        <table className="w-full min-w-[520px]">
          <thead className="bg-muted/40 text-left">
            <tr>
              <th className="px-3 py-2 font-medium">Field</th>
              <th className="px-3 py-2 font-medium">Default pack</th>
              <th className="px-3 py-2 font-medium">Catalog (YA)</th>
              <th className="px-3 py-2 font-medium">Act / section</th>
            </tr>
          </thead>
          <tbody>
            {diffs.map((row) => (
              <tr key={row.field} className="border-t align-top">
                <td className="px-3 py-2 font-mono text-[11px]">{row.field}</td>
                <td className="px-3 py-2 text-muted-foreground">{row.default_value}</td>
                <td className="px-3 py-2 font-medium text-emerald-700 dark:text-emerald-400">
                  {row.catalog_value}
                </td>
                <td className="px-3 py-2 text-muted-foreground">
                  {row.act_reference ? (
                    <>
                      {row.act_reference}
                      {row.section_ref ? ` · ${row.section_ref}` : ""}
                    </>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function CatalogRulesSyncPanel({
  useCatalogRules,
  onUseCatalogRulesChange,
  assessmentYear,
  onAssessmentYearChange,
  onSynced,
}: Props) {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [previewMeta, setPreviewMeta] = useState<CatalogPreviewMetadata | null>(null);
  const [previewDiffs, setPreviewDiffs] = useState<RulesFieldDiff[]>([]);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ["catalog-rules-status"],
    queryFn: getCatalogRulesStatus,
  });

  const years = statusQuery.data?.available_assessment_years ?? [];
  const syncedYears = useMemo(
    () => new Set((statusQuery.data?.synced_years ?? []).map((y) => y.assessment_year)),
    [statusQuery.data?.synced_years],
  );

  useEffect(() => {
    if (years.length === 0) return;
    if (!years.includes(assessmentYear)) {
      onAssessmentYearChange(years[years.length - 1] ?? years[0]);
    }
  }, [years, assessmentYear, onAssessmentYearChange]);

  useEffect(() => {
    setPreviewMeta(null);
    setPreviewDiffs([]);
    setSyncMessage(null);
  }, [assessmentYear]);

  const previewMutation = useMutation({
    mutationFn: () => previewCatalogRules(assessmentYear),
    onSuccess: (data) => {
      setPreviewMeta(data.metadata);
      setPreviewDiffs(data.diffs);
    },
  });

  const syncMutation = useMutation({
    mutationFn: () => syncCatalogRules(assessmentYear),
    onSuccess: (data) => {
      setPreviewMeta(data.metadata);
      setPreviewDiffs(data.diffs);
      setSyncMessage(`Loaded ${data.metadata.assessment_period}`);
      void queryClient.invalidateQueries({ queryKey: ["catalog-rules-status"] });
      onSynced?.();
    },
  });

  const isSynced = syncedYears.has(assessmentYear);
  const hasPreview = previewMeta !== null;

  const collapsedSummary = [
    `YA ${formatYa(assessmentYear)}`,
    isSynced ? "loaded" : "not loaded",
    useCatalogRules ? "applied to preview" : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return (
    <Card className="border-primary/20 bg-primary/[0.02] shadow-sm">
      <button
        type="button"
        className="flex w-full items-start gap-2 px-6 py-4 text-left transition-colors hover:bg-muted/30"
        aria-expanded={expanded}
        onClick={() => setExpanded((open) => !open)}
      >
        <Scale className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">Adaptive Tax catalog rules (opt-in)</CardTitle>
            <ChevronDown
              className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
                expanded ? "rotate-180" : ""
              }`}
            />
          </div>
          {expanded ? (
            <CardDescription className="mt-1">
              Preview which Act and assessment year drive rule changes before applying them to
              smart recommendations.
            </CardDescription>
          ) : (
            <p className="mt-1 text-sm text-muted-foreground">{collapsedSummary}</p>
          )}
        </div>
      </button>

      {expanded && (
      <CardContent className="space-y-4 border-t pt-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="min-w-[160px] space-y-1.5">
            <Label>Assessment year</Label>
            <Select
              value={assessmentYear}
              onChange={(e) => onAssessmentYearChange(e.target.value)}
              disabled={years.length === 0}
            >
              {years.map((y) => (
                <option key={y} value={y}>
                  YA {formatYa(y)}
                </option>
              ))}
            </Select>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={!assessmentYear || previewMutation.isPending}
              onClick={() => previewMutation.mutate()}
            >
              {previewMutation.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : null}
              Preview diff
            </Button>
            <Button
              type="button"
              size="sm"
              disabled={!assessmentYear || syncMutation.isPending}
              onClick={() => syncMutation.mutate()}
            >
              {syncMutation.isPending ? (
                <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
              )}
              Load catalog rules
            </Button>
          </div>
        </div>

        {statusQuery.data && (
          <p className="text-xs text-muted-foreground">
            Default pack: <span className="font-mono">{statusQuery.data.default_rules_version}</span>
            {isSynced ? (
              <span className="ml-2 rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-700 dark:text-emerald-400">
                YA {formatYa(assessmentYear)} loaded in memory
              </span>
            ) : (
              <span className="ml-2 rounded-full bg-amber-500/10 px-2 py-0.5 text-amber-800 dark:text-amber-300">
                Not loaded — preview or load before applying
              </span>
            )}
          </p>
        )}

        {syncMessage && <p className="text-xs text-emerald-700 dark:text-emerald-400">{syncMessage}</p>}

        {(previewMutation.isError || syncMutation.isError) && (
          <p className="text-xs text-destructive">
            {((previewMutation.error ?? syncMutation.error) as Error).message}
          </p>
        )}

        {hasPreview && previewMeta && <MetadataPanel meta={previewMeta} />}
        {hasPreview && <DiffTable diffs={previewDiffs} />}

        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-input"
            checked={useCatalogRules}
            onChange={(e) => onUseCatalogRulesChange(e.target.checked)}
            disabled={!isSynced}
          />
          <span>
            Apply catalog rules to smart recommendations preview
            {!isSynced && (
              <span className="ml-1 text-xs text-muted-foreground">(load a year first)</span>
            )}
          </span>
        </label>
      </CardContent>
      )}
    </Card>
  );
}
