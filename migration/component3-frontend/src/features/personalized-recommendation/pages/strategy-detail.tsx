import { useParams } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function StrategyDetailPage() {
  const { strategyId } = useParams();
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Strategy Detail</h1>
        <p className="text-muted-foreground">
          Full eligibility trace, legal reference, and SHAP-based reasons (FR10, NFR3).
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Strategy {strategyId}</CardTitle>
          <CardDescription>Populated in Phase 6.</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </div>
  );
}
