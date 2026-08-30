import { CheckCircle, AlertTriangle, Search, Database, FileText, MessageSquare, Sparkles } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProofMap, ProofStepKind } from "../types";

interface ProofMapPanelProps {
  proofMap: ProofMap;
}

const KIND_ICON: Record<ProofStepKind, React.ElementType> = {
  user_query: MessageSquare,
  retrieval: Search,
  knowledge_graph: Database,
  evidence: FileText,
  symbolic_validation: CheckCircle,
  advisory_output: Sparkles,
};

const KIND_COLOR: Record<ProofStepKind, string> = {
  user_query: "text-blue-600 dark:text-blue-400",
  retrieval: "text-violet-600 dark:text-violet-400",
  knowledge_graph: "text-emerald-600 dark:text-emerald-400",
  evidence: "text-amber-600 dark:text-amber-400",
  symbolic_validation: "text-teal-600 dark:text-teal-400",
  advisory_output: "text-primary",
};

function ValidationBadge({ status }: { status: string }) {
  if (status === "passed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
        <CheckCircle className="h-3 w-3" /> Passed
      </span>
    );
  }
  if (status === "corrected") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
        <AlertTriangle className="h-3 w-3" /> Corrected
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700 dark:bg-red-900/40 dark:text-red-300">
        <AlertTriangle className="h-3 w-3" /> Failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
      {status}
    </span>
  );
}

export function ProofMapPanel({ proofMap }: ProofMapPanelProps) {
  return (
    <Card className="overflow-hidden rounded-xl border border-border/70 shadow-sm">
      <div className="h-1 w-full bg-gradient-to-r from-violet-500/60 to-teal-500/60" aria-hidden />
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-base">
          <span>Proof Map — audit trail</span>
          <ValidationBadge status={proofMap.validation_status} />
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Rule engine: <span className="font-mono">{proofMap.rule_engine_version}</span>
          {proofMap.evidence_refs.length > 0 && (
            <> · {proofMap.evidence_refs.length} source ref{proofMap.evidence_refs.length !== 1 ? "s" : ""}</>
          )}
        </p>
      </CardHeader>
      <CardContent>
        <ol className="relative border-l border-border/50 pl-4 space-y-4">
          {proofMap.steps.map((step) => {
            const Icon = KIND_ICON[step.kind] ?? FileText;
            const color = KIND_COLOR[step.kind] ?? "text-muted-foreground";
            return (
              <li key={step.step_id} className="relative">
                <span className="absolute -left-[1.1rem] flex h-6 w-6 items-center justify-center rounded-full border border-border/60 bg-background">
                  <Icon className={`h-3.5 w-3.5 ${color}`} />
                </span>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {step.kind.replace(/_/g, " ")}
                </p>
                <p className="text-sm font-medium text-foreground">{step.label}</p>
                {step.detail ? (
                  <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">{step.detail}</p>
                ) : null}
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}
