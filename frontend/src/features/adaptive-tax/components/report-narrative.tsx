import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import type { ReportNarrativeView } from "../build-report-narrative";

const DISCLAIMER = "Research prototype — not legal advice.";

function citationHeading(section: string, actName: string | null): string | null {
  const label = section
    ? /^\d/.test(section)
      ? `Section ${section}`
      : section
    : null;
  if (label && actName) return `${label} — ${actName}`;
  return label;
}

export function ReportNarrative({ view }: { view: ReportNarrativeView }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">How this was calculated</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {view.insufficientEvidence ? (
          <p className="text-sm leading-relaxed text-foreground/90">
            {view.insufficientEvidenceMessage}
          </p>
        ) : (
          <>
            {view.summary ? (
              <p className="text-sm leading-relaxed">{view.summary}</p>
            ) : null}
            {view.steps.length > 0 ? (
              <ol className="space-y-4">
                {view.steps.map((step, index) => (
                  <li key={index} className="space-y-1.5">
                    <div className="flex flex-wrap items-baseline gap-2">
                      <p className="text-sm font-medium">{step.label}</p>
                      {step.sectionTag ? (
                        <span className="text-[11px] text-muted-foreground">
                          {step.sectionTag}
                        </span>
                      ) : null}
                    </div>
                    <p className="text-sm leading-relaxed text-foreground/90">
                      {step.sentence}
                    </p>
                    {step.citation ? (
                      <details className="text-sm">
                        <summary className="cursor-pointer text-xs text-muted-foreground">
                          see legal text
                        </summary>
                        <div className="mt-2 space-y-1 rounded-md border bg-muted/30 p-3">
                          {citationHeading(step.citation.section, step.citation.actName) ? (
                            <p className="text-xs text-muted-foreground">
                              {citationHeading(step.citation.section, step.citation.actName)}
                            </p>
                          ) : null}
                          <blockquote className="border-l-2 border-muted-foreground/40 pl-3 text-xs italic">
                            {step.citation.quote}
                          </blockquote>
                        </div>
                      </details>
                    ) : null}
                  </li>
                ))}
              </ol>
            ) : null}
            {view.lawChanges.length > 0 ? (
              <div className="space-y-2 pt-2">
                <p className="text-sm font-medium">What changed in the law</p>
                {view.lawChanges.map((sentence) => (
                  <p key={sentence} className="text-sm leading-relaxed text-foreground/90">
                    {sentence}
                  </p>
                ))}
              </div>
            ) : null}
          </>
        )}
        <p className="border-t pt-4 text-center text-xs text-muted-foreground">
          {DISCLAIMER}
        </p>
      </CardContent>
    </Card>
  );
}
