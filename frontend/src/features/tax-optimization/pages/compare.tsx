import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { postCompareStrategies } from "../api";
import { CompareStrategiesTable } from "../components/compare-strategies-table";
import { ExplanationPanel } from "../components/explanation-panel";
import type { TaxOptBCompareStrategiesRequestV1, TaxOptBCompareStrategiesResponseV1 } from "../types";

const DEFAULT_MANUAL_COMPARE = `{
  "profile": {
    "tax_year": "2024_25",
    "employment_type": "employee",
    "dependents": 0,
    "annual_gross_income": "2400000",
    "estimated_annual_taxable_income": "1800000"
  },
  "variants": [
    {
      "variant_id": "none",
      "label": "No claims",
      "strategy": { "claims": [] }
    },
    {
      "variant_id": "life50",
      "label": "Life insurance 50k",
      "strategy": {
        "claims": [
          {
            "relief_code": "life_insurance_premium",
            "claimed_amount_annual": "50000"
          }
        ]
      }
    }
  ],
  "baseline_variant_id": "none",
  "include_result_detail": true,
  "include_explanations": true,
  "explanation_detail": "summary"
}`;

export function ComparePage() {
  const [bodyJson, setBodyJson] = useState(DEFAULT_MANUAL_COMPARE);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<TaxOptBCompareStrategiesResponseV1 | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggleExpand = useCallback((variantId: string) => {
    setExpanded((p) => ({ ...p, [variantId]: !p[variantId] }));
  }, []);

  const onRun = async () => {
    setError(null);
    setData(null);
    setLoading(true);
    try {
      const parsed = JSON.parse(bodyJson) as TaxOptBCompareStrategiesRequestV1;
      const out = await postCompareStrategies(parsed);
      setData(out);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Strategy comparison (FR6)</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          POST body for <span className="font-mono">/compliance/compare-strategies</span>. Edit JSON
          and run, or use the{" "}
          <Link to="/tax-optimization/compliance" className="text-primary underline">
            Compliance
          </Link>{" "}
          page for structured intake + presets.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Request JSON</CardTitle>
          <CardDescription>
            Must include <span className="font-mono">profile</span>,{" "}
            <span className="font-mono">variants</span> (1–12), optional{" "}
            <span className="font-mono">baseline_variant_id</span>. Add{" "}
            <span className="font-mono">include_explanations: true</span> (and optional{" "}
            <span className="font-mono">explanation_detail</span>:{" "}
            <span className="font-mono">&quot;summary&quot;</span> or{" "}
            <span className="font-mono">&quot;detailed&quot;</span>) for FR5 narrative in the response.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <textarea
            value={bodyJson}
            onChange={(e) => setBodyJson(e.target.value)}
            spellCheck={false}
            rows={22}
            className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 font-mono text-xs leading-relaxed shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            aria-label="Compare strategies JSON body"
          />
          <Button type="button" disabled={loading} onClick={() => void onRun()}>
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Comparing…
              </>
            ) : (
              "Run comparison"
            )}
          </Button>
        </CardContent>
      </Card>

      {error ? (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader>
            <CardTitle className="text-destructive text-base">Request failed</CardTitle>
            <CardDescription className="text-destructive/90">{error}</CardDescription>
          </CardHeader>
        </Card>
      ) : null}

      <CompareStrategiesTable data={data} expanded={expanded} onToggleExpand={toggleExpand} />
      <ExplanationPanel bundle={data?.explanations} title="Narrative — scenario comparison (FR5)" />
    </div>
  );
}
