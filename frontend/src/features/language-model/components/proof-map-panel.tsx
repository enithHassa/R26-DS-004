import { useState } from "react";
import {
  CheckCircle,
  AlertTriangle,
  Search,
  Database,
  FileText,
  MessageSquare,
  Sparkles,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { ProofMap, ProofMapStep, ProofStepKind } from "../types";

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

const KIND_TITLE: Record<ProofStepKind, string> = {
  user_query: "Question",
  retrieval: "Retrieval",
  knowledge_graph: "Knowledge graph",
  evidence: "Source evidence",
  symbolic_validation: "Rule check",
  advisory_output: "Answer",
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

function MetaChip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-border/60 bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
      {children}
    </span>
  );
}

function EvidenceMeta({ meta }: { meta: Record<string, unknown> | null | undefined }) {
  if (!meta) return null;
  const source = typeof meta.source_doc_id === "string" ? meta.source_doc_id : null;
  const section =
    (typeof meta.section_label === "string" && meta.section_label) ||
    (typeof meta.section_uid === "string" ? meta.section_uid : null);
  const tier = meta.tier != null ? String(meta.tier) : null;
  const score = typeof meta.score === "number" ? meta.score.toFixed(3) : null;
  const chips = [
    source ? <MetaChip key="src">{source}</MetaChip> : null,
    section ? <MetaChip key="sec">{section}</MetaChip> : null,
    tier ? <MetaChip key="tier">tier {tier}</MetaChip> : null,
    score ? <MetaChip key="score">score {score}</MetaChip> : null,
  ].filter(Boolean);
  if (chips.length === 0) return null;
  return <div className="mt-1.5 flex flex-wrap gap-1">{chips}</div>;
}

function StepBody({ step }: { step: ProofMapStep }) {
  const [open, setOpen] = useState(step.kind !== "evidence");
  const isEvidence = step.kind === "evidence";
  const detail = step.detail?.trim() ?? "";

  if (!detail && !step.metadata) return null;

  if (isEvidence) {
    return (
      <div className="mt-1">
        <EvidenceMeta meta={step.metadata} />
        <button
          type="button"
          className="mt-1.5 inline-flex items-center gap-1 text-xs font-medium text-amber-800/90 hover:underline dark:text-amber-300"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          {open ? "Hide verbatim excerpt" : "Show verbatim excerpt"}
        </button>
        {open && detail ? (
          <pre className="mt-1.5 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-amber-500/20 bg-amber-500/5 p-2 text-[11px] leading-relaxed text-muted-foreground">
            {detail}
          </pre>
        ) : null}
      </div>
    );
  }

  if (step.kind === "symbolic_validation" && step.metadata?.issues) {
    const issues = Array.isArray(step.metadata.issues) ? step.metadata.issues : [];
    return (
      <div className="mt-1 space-y-1">
        {detail ? <p className="text-xs leading-relaxed text-muted-foreground">{detail}</p> : null}
        {issues.length > 0 ? (
          <ul className="space-y-1 pl-3 text-[11px] text-muted-foreground">
            {issues.map((issue, idx) => {
              const row = issue as { severity?: string; message?: string; code?: string };
              return (
                <li key={`${row.code ?? "issue"}-${idx}`} className="list-disc">
                  <span className="font-medium uppercase tracking-wide text-[10px] text-muted-foreground/80">
                    {row.severity ?? "note"}
                  </span>
                  {": "}
                  {row.message ?? row.code}
                </li>
              );
            })}
          </ul>
        ) : null}
      </div>
    );
  }

  return detail ? (
    <p className="mt-0.5 whitespace-pre-wrap text-xs leading-relaxed text-muted-foreground">{detail}</p>
  ) : null;
}

export function ProofMapPanel({ proofMap }: ProofMapPanelProps) {
  const evidenceCount = proofMap.steps.filter((s) => s.kind === "evidence").length;

  return (
    <Card className="overflow-hidden rounded-xl border border-border/70 shadow-sm">
      <div className="h-1 w-full bg-gradient-to-r from-violet-500/60 to-teal-500/60" aria-hidden />
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center justify-between text-base">
          <span>Proof Map — audit trail</span>
          <ValidationBadge status={proofMap.validation_status} />
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Shows how the answer was grounded: retrieval → knowledge graph → verbatim sources → rule
          check → Gemini summary. Evidence text is not rewritten by AI.
        </p>
        <p className="text-xs text-muted-foreground">
          Rule engine: <span className="font-mono">{proofMap.rule_engine_version}</span>
          {evidenceCount > 0 && (
            <>
              {" "}
              · {evidenceCount} evidence step{evidenceCount !== 1 ? "s" : ""}
            </>
          )}
          {proofMap.evidence_refs.length > 0 && (
            <>
              {" "}
              · {proofMap.evidence_refs.length} source ref
              {proofMap.evidence_refs.length !== 1 ? "s" : ""}
            </>
          )}
        </p>
      </CardHeader>
      <CardContent>
        <ol className="relative space-y-4 border-l border-border/50 pl-4">
          {proofMap.steps.map((step) => {
            const Icon = KIND_ICON[step.kind] ?? FileText;
            const color = KIND_COLOR[step.kind] ?? "text-muted-foreground";
            return (
              <li key={step.step_id} className="relative">
                <span className="absolute -left-[1.1rem] flex h-6 w-6 items-center justify-center rounded-full border border-border/60 bg-background">
                  <Icon className={`h-3.5 w-3.5 ${color}`} />
                </span>
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {KIND_TITLE[step.kind] ?? step.kind.replace(/_/g, " ")}
                </p>
                <p className="text-sm font-medium text-foreground">{step.label}</p>
                <StepBody step={step} />
              </li>
            );
          })}
        </ol>
      </CardContent>
    </Card>
  );
}
