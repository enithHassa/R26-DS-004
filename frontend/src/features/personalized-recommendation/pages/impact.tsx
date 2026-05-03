import { useParams } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function ImpactPage() {
  const { strategyId } = useParams();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Predictive Impact</h1>
        <p className="text-muted-foreground">
          Monte Carlo projection of salary, tax liability, and net worth over the
          chosen horizon with P10/P50/P90 risk bands (FR7, FR8).
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Simulation for {strategyId}</CardTitle>
          <CardDescription>
            Fan chart (recharts) and distribution histograms — implemented in Phase 5 + 7.
          </CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </div>
  );
}
