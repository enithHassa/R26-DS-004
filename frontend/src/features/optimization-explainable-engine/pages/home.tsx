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

export function OptimizationExplainableHomePage() {
  const healthQuery = useQuery({
    queryKey: ["optimization-explainable-engine", "health"],
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
        <h1 className="text-2xl font-semibold tracking-tight">
          Optimization and Explainable Engine
        </h1>
        <p className="text-muted-foreground">
          Independent year-aware interview. Years and reliefs load from promoted
          Act year views. Phase 7 goldens use extracted 2025/26 and 2023/24
          slabs. The original Optimization and Explainable sidebar still uses
          port 8008.
        </p>
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
              GET /api/v1/optimization-explainable-engine/health
            </code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-muted-foreground">
          {healthQuery.isSuccess ? (
            <p>
              {healthQuery.data.component} v{healthQuery.data.version ?? "?"}{" "}
              (phase {healthQuery.data.phase ?? "?"}).
            </p>
          ) : healthQuery.isError ? (
            <p>
              Start the service on port 8009, then refresh. Vite proxies this
              path to that process.
            </p>
          ) : (
            <p>Checking service…</p>
          )}
        </CardContent>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button type="button" asChild>
          <Link to="/optimization-explainable-engine">Start interview</Link>
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/acts">Acts</Link>
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/income">Income</Link>
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/reliefs">Reliefs</Link>
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/compare">Compare</Link>
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/result">Result</Link>
        </Button>
        <Button type="button" variant="outline" asChild>
          <Link to="/optimization-explainable-engine/load-act">Load new act</Link>
        </Button>
      </div>
    </div>
  );
}
