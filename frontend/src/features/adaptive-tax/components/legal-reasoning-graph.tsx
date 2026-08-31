import { useState } from "react";
import { ChevronRight } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import type { ReasoningGraphNode, ReasoningGraphResponse } from "../api";
import { formatLkr } from "../format-lkr";

function GraphBox({
  node,
  selected,
  onSelect,
}: {
  node: ReasoningGraphNode;
  selected: boolean;
  onSelect: () => void;
}) {
  if (!node.present) return null;
  return (
    <button
      type="button"
      onClick={onSelect}
      className={
        selected
          ? "min-w-[7.5rem] rounded-lg border-2 border-primary bg-primary/5 px-3 py-2 text-left text-xs shadow-sm"
          : "min-w-[7.5rem] rounded-lg border bg-card px-3 py-2 text-left text-xs shadow-sm hover:bg-muted/40"
      }
    >
      <p className="font-medium leading-tight">{node.label}</p>
      {node.amount != null && /^-?\d/.test(node.amount) ? (
        <p className="mt-0.5 text-[11px] text-muted-foreground">
          {formatLkr(node.amount)}
        </p>
      ) : null}
      {node.section ? (
        <p className="mt-0.5 text-[10px] text-muted-foreground">Sec {node.section}</p>
      ) : null}
    </button>
  );
}

function NodeDetail({ node }: { node: ReasoningGraphNode }) {
  return (
    <div className="space-y-2 rounded-md border bg-muted/30 p-3 text-sm">
      <p className="font-medium">{node.label}</p>
      {node.source_quote ? (
        <blockquote className="border-l-2 border-muted-foreground/40 pl-3 text-xs italic">
          {node.source_quote}
        </blockquote>
      ) : (
        <p className="text-xs text-muted-foreground">No Act quote linked on this node.</p>
      )}
      {node.kg_node_ids.length > 0 ? (
        <div>
          <p className="text-xs font-medium text-muted-foreground">Neo4j / section anchors</p>
          <ul className="mt-1 space-y-0.5 font-mono text-[11px]">
            {node.kg_node_ids.map((id) => (
              <li key={id}>{id}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {node.legal_confidence ? (
        <p className="text-xs text-muted-foreground">
          Confidence: <span className="font-medium text-foreground">{node.legal_confidence}</span>
        </p>
      ) : null}
      {node.rule_source_ids.length > 0 ? (
        <p className="text-[11px] text-muted-foreground">
          rule_source: {node.rule_source_ids.join(", ")}
        </p>
      ) : null}
    </div>
  );
}

export function LegalReasoningGraphPanel({
  graph,
  loading = false,
}: {
  graph: ReasoningGraphResponse | undefined;
  loading?: boolean;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const ordered = graph?.nodes.filter((n) => n.present) ?? [];
  const selected = ordered.find((n) => n.node_id === selectedId) ?? ordered[0] ?? null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Legal reasoning graph</CardTitle>
        <CardDescription>
          Deterministic pipeline from calculation trace + component trace + rule sources
          (Phase 6.8 viva). Click a box for quote, graph node id, and confidence.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <p className="text-sm text-muted-foreground">Building graph…</p>
        ) : !graph || ordered.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No reasoning graph available for this calculation.
          </p>
        ) : (
          <>
            <div className="flex flex-wrap items-center gap-1 overflow-x-auto pb-2">
              {ordered.map((node, idx) => (
                <div key={node.node_id} className="flex items-center gap-1">
                  <GraphBox
                    node={node}
                    selected={selected?.node_id === node.node_id}
                    onSelect={() => setSelectedId(node.node_id)}
                  />
                  {idx < ordered.length - 1 ? (
                    <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                  ) : null}
                </div>
              ))}
            </div>
            {selected ? <NodeDetail node={selected} /> : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
