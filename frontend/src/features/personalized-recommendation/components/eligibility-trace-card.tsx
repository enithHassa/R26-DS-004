import { CheckCircle2, XCircle } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

import type { DerivedFeatures } from "../types";
import { buildEligibilityTrace } from "../utils/eligibility-trace";

type Props = {
  strategyCode: string;
  features?: DerivedFeatures;
  isLoading?: boolean;
};

export function EligibilityTraceCard({ strategyCode, features, isLoading }: Props) {
  const trace = buildEligibilityTrace(strategyCode, features);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Eligibility evidence trace</CardTitle>
        <CardDescription>
          Rule-engine flags from your financial profile (FR2). {trace.rationale}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Loading profile features…</p>}
        {!features && !isLoading && (
          <p className="text-sm text-muted-foreground">
            Link a profile via <code className="text-xs">?profile=</code> to see eligibility evidence.
          </p>
        )}
        {features && trace.items.length > 0 && (
          <ul className="space-y-2">
            {trace.items.map((item) => (
              <li
                key={item.flag}
                className="flex items-start gap-2 rounded-md border px-3 py-2 text-sm"
              >
                {item.met ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                ) : (
                  <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                )}
                <div>
                  <div className="font-medium">{item.label}</div>
                  <div className="text-xs text-muted-foreground">
                    {item.met ? "Evidence satisfied" : "Not met — strategy may be filtered or down-ranked"}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
        {features && trace.items.length > 0 && (
          <p
            className={`mt-4 text-sm font-medium ${trace.allMet ? "text-emerald-700" : "text-amber-700"}`}
          >
            {trace.allMet
              ? "All required eligibility checks passed for this strategy family."
              : "Some eligibility checks failed — review profile inputs or choose another strategy."}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
