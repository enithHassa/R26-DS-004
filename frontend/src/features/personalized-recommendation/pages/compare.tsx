import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function ComparePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Compare Strategies</h1>
        <p className="text-muted-foreground">
          Side-by-side comparison over the same profile + horizon (Objective 2.2.3).
        </p>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Coming in Phase 7</CardTitle>
          <CardDescription>
            Calls <code>POST /api/v1/recommendation/impact/compare</code>.
          </CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
    </div>
  );
}
