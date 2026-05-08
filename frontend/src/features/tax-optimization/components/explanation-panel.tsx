import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { TaxOptBExplanationBundleV1 } from "../types";

type ExplanationPanelProps = {
  bundle: TaxOptBExplanationBundleV1 | null | undefined;
  title?: string;
};

function countSlabBandBullets(bundle: TaxOptBExplanationBundleV1): number {
  const walk = bundle.sections.find((s) => s.title === "Tax computation walk");
  if (!walk) return 0;
  return walk.bullets.filter((b) => b.kind === "slab").length;
}

/**
 * Renders FR5 template narrative from Component B (deterministic; not LLM output).
 */
export function ExplanationPanel({ bundle, title = "Explanations (FR5)" }: ExplanationPanelProps) {
  if (!bundle) return null;

  const showRefs = bundle.detail_level === "detailed";
  const slabBands = countSlabBandBullets(bundle);
  const isDetailed = bundle.detail_level === "detailed";

  return (
    <Card className="border-teal-500/30 bg-teal-500/[0.03]">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-base">{title}</CardTitle>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
              isDetailed
                ? "bg-teal-600/20 text-teal-900 dark:text-teal-100"
                : "bg-muted text-muted-foreground",
            )}
            title="Narrative tier requested for this response"
          >
            {isDetailed ? "Detailed" : "Summary"}
          </span>
          {slabBands > 0 ? (
            <span
              className="rounded-full bg-background/80 px-2 py-0.5 text-[10px] text-muted-foreground ring-1 ring-border"
              title="Progressive tax band lines under Tax computation walk"
            >
              {slabBands} slab line{slabBands === 1 ? "" : "s"}
            </span>
          ) : null}
        </div>
        <CardDescription className="text-xs leading-relaxed">
          Template-based narrative from the rule engine. Engine:{" "}
          <span className="font-mono">{String(bundle.provenance?.engine ?? "—")}</span>
          {bundle.rules_version_label ? (
            <>
              {" "}
              · Rules label: <span className="font-mono">{bundle.rules_version_label}</span>
            </>
          ) : null}
          {bundle.ruleset_assessment_year ? (
            <>
              {" "}
              · Year: <span className="font-mono">{bundle.ruleset_assessment_year}</span>
            </>
          ) : null}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm leading-relaxed text-foreground">{bundle.summary}</p>
        {bundle.sections.map((sec) => (
          <div key={sec.title} className="rounded-md border border-border/60 bg-background/50 p-3">
            <h4 className="mb-2 text-sm font-semibold">{sec.title}</h4>
            <ul className="space-y-2.5 text-sm">
              {sec.bullets.map((b, i) => (
                <li key={`${sec.title}-${i}`} className="border-l-2 border-teal-600/35 pl-3">
                  <span className="text-[10px] font-medium uppercase tracking-wide text-muted-foreground">
                    {b.kind}
                  </span>
                  <p className="mt-0.5 leading-snug">{b.text}</p>
                  {b.detail_text ? (
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{b.detail_text}</p>
                  ) : null}
                  {showRefs && b.source_refs.length > 0 ? (
                    <p className="mt-1 font-mono text-[10px] text-muted-foreground/90">
                      {b.source_refs.join(" · ")}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
