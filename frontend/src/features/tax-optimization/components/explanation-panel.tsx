import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

import type { TaxOptBExplanationBulletKindV1, TaxOptBExplanationBundleV1 } from "../types";

type ExplanationPanelProps = {
  bundle: TaxOptBExplanationBundleV1 | null | undefined;
  title?: string;
  /** Consumer-friendly narrative (hides engine metadata, renames section labels). */
  presentation?: "default" | "advisory";
};

function countSlabBandBullets(bundle: TaxOptBExplanationBundleV1): number {
  const walk = bundle.sections.find((s) => s.title === "Tax computation walk");
  if (!walk) return 0;
  return walk.bullets.filter((b) => b.kind === "slab").length;
}

function kindLabel(kind: TaxOptBExplanationBulletKindV1, presentation: "default" | "advisory"): string {
  if (presentation === "default") return kind;
  const map: Partial<Record<TaxOptBExplanationBulletKindV1, string>> = {
    summary: "Summary",
    slab: "Tax calculation",
    comparison: "Strategy comparison",
    compliance: "Compliance",
    relief: "Relief",
    disclaimer: "Note",
  };
  return map[kind] ?? kind.charAt(0).toUpperCase() + kind.slice(1);
}

function sectionTitle(title: string, presentation: "default" | "advisory"): string {
  if (presentation !== "advisory") return title;
  if (title === "Tax computation walk") return "Tax calculation";
  return title;
}

/**
 * Renders template narrative from Component B (deterministic; not LLM output).
 */
export function ExplanationPanel({
  bundle,
  title = "Explanations",
  presentation = "default",
}: ExplanationPanelProps) {
  if (!bundle) return null;

  const showRefs = presentation === "default" && bundle.detail_level === "detailed";
  const slabBands = countSlabBandBullets(bundle);
  const isDetailed = bundle.detail_level === "detailed";

  const disclaimerFootnotes: string[] = [];
  if (presentation === "advisory") {
    for (const sec of bundle.sections) {
      for (const b of sec.bullets) {
        if (b.kind === "disclaimer") {
          if (b.text?.trim()) disclaimerFootnotes.push(b.text.trim());
          if (b.detail_text?.trim()) disclaimerFootnotes.push(b.detail_text.trim());
        }
      }
    }
  }

  return (
    <Card
      className={cn(
        "rounded-xl border shadow-sm",
        presentation === "advisory"
          ? "border-border/80 bg-card"
          : "border-teal-500/30 bg-teal-500/[0.03]",
      )}
    >
      <CardHeader className={cn("pb-2", presentation === "advisory" && "p-6 pb-3")}>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className={cn("text-base font-semibold", presentation === "advisory" && "text-lg")}>
            {title}
          </CardTitle>
          {presentation === "default" ? (
            <>
              <span
                className={cn(
                  "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                  isDetailed
                    ? "bg-teal-600/20 text-teal-900 dark:text-teal-100"
                    : "bg-muted text-muted-foreground",
                )}
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
            </>
          ) : null}
        </div>
        {presentation === "default" ? (
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
        ) : null}
      </CardHeader>
      <CardContent className={cn("space-y-4", presentation === "advisory" && "px-6 pb-6 pt-0")}>
        <p className="text-sm leading-relaxed text-foreground">{bundle.summary}</p>
        {bundle.sections.map((sec) => {
          const bullets =
            presentation === "advisory"
              ? sec.bullets.filter((b) => b.kind !== "disclaimer")
              : sec.bullets;
          if (presentation === "advisory" && bullets.length === 0) return null;
          return (
            <div key={sec.title} className="rounded-lg border border-border/60 bg-muted/10 p-4">
              <h4 className="mb-2 text-base font-semibold text-foreground">
                {sectionTitle(sec.title, presentation)}
              </h4>
              <ul className="space-y-2.5 text-sm">
                {bullets.map((b, i) => (
                  <li key={`${sec.title}-${i}`} className="border-l-2 border-teal-600/35 pl-3">
                    <span className="text-[11px] font-medium text-muted-foreground">
                      {kindLabel(b.kind, presentation)}
                    </span>
                    <p className="mt-0.5 leading-snug text-foreground">{b.text}</p>
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
          );
        })}
        {presentation === "advisory" && disclaimerFootnotes.length > 0 ? (
          <p className="border-t border-border/60 pt-4 text-xs leading-relaxed text-muted-foreground">
            {disclaimerFootnotes.join(" ")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
