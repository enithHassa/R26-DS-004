import { useQuery } from "@tanstack/react-query";
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

import { getHealth } from "../api";

export function AdaptiveTaxHomePage() {
  const healthQuery = useQuery({
    queryKey: ["adaptive-tax", "health"],
    queryFn: getHealth,
    retry: false,
  });

  const statusLabel = healthQuery.isLoading
    ? "checking…"
    : healthQuery.isSuccess && healthQuery.data.status === "ok"
      ? "ok"
      : "unreachable";

  const statusClass =
    statusLabel === "ok"
      ? "bg-emerald-100 text-emerald-800"
      : statusLabel === "checking…"
        ? "bg-muted text-muted-foreground"
        : "bg-destructive/10 text-destructive";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Adaptive Tax</h1>
        <p className="text-muted-foreground">
          Component 5 — explainable adaptive tax calculation. Phase 3: pure-Python rule
          engine and calculator (KG + param JSON, no GPT), plus Phase 1–2 amendment
          upload and knowledge stores.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button type="button" asChild>
          <Link to="/adaptive-tax/calculator">Open calculator</Link>
        </Button>
        <Button type="button" variant="secondary" asChild>
          <Link to="/adaptive-tax/coverage">Legal coverage dashboard</Link>
        </Button>
        <Button type="button" variant="secondary" asChild>
          <Link to="/adaptive-tax/admin/upload">Upload amendment PDF</Link>
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between gap-2 text-lg">
            Service status
            <span
              className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium ${statusClass}`}
            >
              {healthQuery.isLoading ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : null}
              {statusLabel}
            </span>
          </CardTitle>
          <CardDescription>
            Probes{" "}
            <code className="rounded bg-muted px-1 text-xs">
              GET /api/v1/adaptive-tax/health
            </code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          {healthQuery.isSuccess ? (
            <p>
              Component{" "}
              <span className="font-medium text-foreground">
                {healthQuery.data.component}
              </span>
              {healthQuery.data.version ? (
                <>
                  {" "}
                  · version{" "}
                  <span className="font-medium text-foreground">
                    {healthQuery.data.version}
                  </span>
                </>
              ) : null}
            </p>
          ) : healthQuery.isError ? (
            <p>
              Start the Adaptive Tax service on port 8005 (and the gateway on 8000) to
              see a live health response.
            </p>
          ) : (
            <p>Waiting for health response…</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
