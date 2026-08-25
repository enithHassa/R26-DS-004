import { Link } from "react-router-dom";
import { FileText } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import type { CalculateTaxResponse } from "../api";
import { buildTaxpayerSummary, type BreakdownRow } from "../build-taxpayer-summary";
import { formatLkr } from "../format-lkr";

function rowPrefix(kind: BreakdownRow["kind"]): string {
  if (kind === "deduction" || kind === "credit") return "− ";
  if (kind === "subtotal" || kind === "payable") return "= ";
  return "";
}

function BreakdownTable({ rows }: { rows: BreakdownRow[] }) {
  return (
    <div>
      {rows.map((row, index) => {
        const isPayable = row.kind === "payable";
        return (
          <div key={`${row.kind}-${row.label}-${index}`}>
            {isPayable ? <div className="my-2 border-t" /> : null}
            <div className="flex items-baseline justify-between gap-4 py-1.5">
              <div className="min-w-0">
                <p
                  className={
                    isPayable ? "text-sm font-semibold" : "text-sm text-foreground"
                  }
                >
                  {rowPrefix(row.kind)}
                  {row.label}
                  {row.note ? (
                    <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                      → {row.note}
                    </span>
                  ) : null}
                </p>
                {row.detail ? (
                  <p className="text-xs text-muted-foreground">{row.detail}</p>
                ) : null}
              </div>
              <p
                className={[
                  "shrink-0 tabular-nums",
                  isPayable ? "text-sm font-semibold" : "text-sm",
                ].join(" ")}
              >
                {formatLkr(row.amount)}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function TaxpayerResultSummary({
  result,
  assessmentYear,
  calcId,
}: {
  result: CalculateTaxResponse;
  assessmentYear: "2024_25" | "2025_26";
  calcId?: string;
}) {
  const summary = buildTaxpayerSummary(result, assessmentYear);
  const reportId = calcId || result.calc_id;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Your tax estimate</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="space-y-2">
          <p className="text-4xl font-semibold tracking-tight text-balance">
            {summary.headline}
          </p>
          <p className="text-sm text-muted-foreground">{summary.explanation}</p>
        </div>

        <BreakdownTable rows={summary.rows} />

        {summary.whyParagraphs.length > 0 ? (
          <details className="rounded-md border bg-muted/30 p-3">
            <summary className="cursor-pointer text-sm font-medium">
              Why this amount?
            </summary>
            <div className="mt-2 space-y-2 text-sm text-muted-foreground">
              {summary.whyParagraphs.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </div>
          </details>
        ) : null}

        {reportId ? (
          <div className="flex flex-wrap items-center gap-2">
            <Button type="button" asChild>
              <Link to={`/adaptive-tax/report/${reportId}`}>
                <FileText className="h-4 w-4" />
                View report
              </Link>
            </Button>
            <p className="text-xs text-muted-foreground">
              See the full calculation and legal sources.
            </p>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
