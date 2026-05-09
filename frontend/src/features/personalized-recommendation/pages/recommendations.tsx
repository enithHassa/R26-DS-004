import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function RecommendationsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Recommendations</h1>
        <p className="text-muted-foreground">
          Top-K ranked tax strategies with estimated savings, adoption probability,
          and confidence (FR5, FR6, FR9, FR11).
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Coming in Phase 4 + 7</CardTitle>
          <CardDescription>
            Calls <code>POST /api/v1/recommendation/recommendations</code>{" "}
            and renders ranked cards with SHAP explanation popovers.
          </CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </div>
  );
}
