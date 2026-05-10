import { ChevronDown, ChevronRight } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import type { TaxOptBCompareStrategiesResponseV1 } from "../types";

type Props = {
  data: TaxOptBCompareStrategiesResponseV1 | null;
  expanded: Record<string, boolean>;
  onToggleExpand: (variantId: string) => void;
};

export function CompareStrategiesTable({ data, expanded, onToggleExpand }: Props) {
  if (!data) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Comparison results</CardTitle>
        <CardDescription>
          {data.research_disclaimer.slice(0, 120)}
          {data.research_disclaimer.length > 120 ? "…" : ""}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="overflow-x-auto rounded-md border">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="border-b bg-muted/50 font-medium">
              <tr>
                <th className="px-3 py-2">Rank</th>
                <th className="px-3 py-2">Variant</th>
                <th className="px-3 py-2">Passed</th>
                <th className="px-3 py-2 text-right font-mono">Total tax (LKR)</th>
                <th className="px-3 py-2 text-right font-mono">Δ vs baseline</th>
                <th className="px-3 py-2">Detail</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row) => (
                <tr key={row.variant_id} className="border-b border-border/60 last:border-0">
                  <td className="px-3 py-2 font-mono text-muted-foreground">
                    {row.rank ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    <span className="font-mono text-xs">{row.variant_id}</span>
                    {row.label ? (
                      <div className="text-xs text-muted-foreground">{row.label}</div>
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    {row.passed ? (
                      <span className="text-emerald-700 dark:text-emerald-400">Yes</span>
                    ) : (
                      <span className="text-destructive">No</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right font-mono">{row.total_tax ?? "—"}</td>
                  <td className="px-3 py-2 text-right font-mono">
                    {row.delta_total_tax_vs_baseline ?? "—"}
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      onClick={() => onToggleExpand(row.variant_id)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                      disabled={!row.result}
                    >
                      {expanded[row.variant_id] ? (
                        <ChevronDown className="h-3.5 w-3.5" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5" />
                      )}
                      {row.result ? "Violations / slabs" : "—"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {data.rows.map((row) =>
          expanded[row.variant_id] && row.result ? (
            <div
              key={`${row.variant_id}-detail`}
              className="rounded-lg border border-border/80 bg-muted/20 p-3 text-sm"
            >
              <div className="font-medium">{row.variant_id} — detail</div>
              {row.result.tax_computation ? (
                <div className="mt-2 space-y-2">
                  <div className="font-mono text-xs">
                    Total tax: {row.result.tax_computation.total_tax}
                  </div>
                  <ul className="space-y-1 font-mono text-xs text-muted-foreground">
                    {row.result.tax_computation.slab_slices.map((s) => (
                      <li key={s.slab_index}>
                        Band {s.slab_index}: {s.taxable_in_slice} @ {s.rate} → {s.tax_in_slice}
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {row.result.compliance.violations.length > 0 ? (
                <ul className="mt-2 space-y-1 text-xs">
                  {row.result.compliance.violations.map((v, i) => (
                    <li key={`${v.rule_id}-${i}`}>
                      <span className="font-mono text-muted-foreground">{v.rule_id}</span>: {v.message}
                    </li>
                  ))}
                </ul>
              ) : row.passed ? (
                <p className="mt-2 text-xs text-muted-foreground">No violations.</p>
              ) : null}
            </div>
          ) : null,
        )}
      </CardContent>
    </Card>
  );
}
