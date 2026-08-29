import type { ReactNode } from "react";
import {
  CircleDollarSign,
  Landmark,
  Layers,
  PiggyBank,
} from "lucide-react";

import { cn } from "@/lib/utils";

import type { PlainExplanation, PlainExplanationBlock } from "./build-plain-explanation";

const STEP_ICONS: Record<string, typeof PiggyBank> = {
  "What came off your income?": PiggyBank,
  "How the tax is added up": Layers,
  "Terminal-benefit tax": Landmark,
  "The bottom line": CircleDollarSign,
};

export type PlainExplanationVariant = "auditor" | "taxpayer";

type Tone = {
  section: string;
  headerBorder: string;
  title: string;
  titleText: string;
  subtitle: string;
  subtitleText: string;
  summaryCard: string;
  summaryTitle: string;
  summaryBody: string;
  stepCard: string;
  stepCardBottom: string;
  stepIcon: string;
  stepIconBottom: string;
  stepLabel: string;
  stepHeading: string;
  bodyMuted: string;
  nestCard: string;
  nestTitle: string;
  nestBody: string;
  nestFooter: string;
  stepBadge: string;
  stepBadgeText: string;
  footerBorder: string;
};

const TONES: Record<PlainExplanationVariant, Tone> = {
  auditor: {
    section: "rounded-xl border border-border/80 bg-card/40 p-3 shadow-sm",
    headerBorder: "border-border/60",
    title: "text-foreground",
    titleText: "In plain English",
    subtitle: "text-muted-foreground",
    subtitleText: "Walkthrough of this calculation",
    summaryCard: "border-border/80 bg-background",
    summaryTitle: "text-foreground",
    summaryBody: "text-muted-foreground",
    stepCard: "border-border/80 bg-background",
    stepCardBottom: "border-primary/25 bg-primary/5",
    stepIcon: "bg-muted text-foreground",
    stepIconBottom: "bg-primary/10 text-primary",
    stepLabel: "text-muted-foreground",
    stepHeading: "text-foreground",
    bodyMuted: "text-muted-foreground",
    nestCard: "border-border/80 bg-background",
    nestTitle: "text-foreground",
    nestBody: "text-muted-foreground",
    nestFooter: "border-border/70 bg-muted/30 text-foreground",
    stepBadge: "bg-muted text-foreground",
    stepBadgeText: "text-foreground",
    footerBorder: "border-border/60",
  },
  taxpayer: {
    section: "rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-3",
    headerBorder: "border-[var(--uv-border)]",
    title: "text-[var(--uv-text)]",
    titleText: "Your tax, decoded",
    subtitle: "text-[var(--uv-text-muted)]",
    subtitleText: "The short story behind every number",
    summaryCard: "border-[var(--uv-border)] bg-black/20",
    summaryTitle: "text-[var(--uv-text)]",
    summaryBody: "text-[var(--uv-text-muted)]",
    stepCard: "border-[var(--uv-border)] bg-black/20",
    stepCardBottom: "border-[var(--uv-accent)]/35 bg-[var(--uv-accent)]/10",
    stepIcon: "bg-white/10 text-[var(--uv-text)]",
    stepIconBottom: "bg-[var(--uv-accent)]/20 text-[var(--uv-accent)]",
    stepLabel: "text-[var(--uv-text-muted)]",
    stepHeading: "text-[var(--uv-text)]",
    bodyMuted: "text-[var(--uv-text-muted)]",
    nestCard: "border-[var(--uv-border)] bg-[var(--uv-bg-card)]",
    nestTitle: "text-[var(--uv-text)]",
    nestBody: "text-[var(--uv-text-muted)]",
    nestFooter: "border-[var(--uv-border)] bg-black/25 text-[var(--uv-text)]",
    stepBadge: "bg-white/10 text-[var(--uv-text)]",
    stepBadgeText: "text-[var(--uv-text)]",
    footerBorder: "border-[var(--uv-border)]",
  },
};

function StepIcon({ heading }: { heading: string }) {
  const Icon = STEP_ICONS[heading] ?? CircleDollarSign;
  return <Icon className="h-3.5 w-3.5" aria-hidden />;
}

function BlockBody({ block, tone }: { block: PlainExplanationBlock; tone: Tone }) {
  const [lead, ...rest] = block.lines;
  const isRelief =
    block.heading === "What came off your income?" && rest.length > 1;
  const isTaxSteps =
    (block.heading === "How the tax is added up" ||
      block.heading === "Terminal-benefit tax") &&
    rest.some((line) => line.startsWith("Step "));

  if (isRelief) {
    const closing =
      rest.find((line) => line.startsWith("Add those up:")) ?? rest[rest.length - 1];
    const items = rest.filter(
      (line) => line.includes(" — ") && !line.startsWith("Add those up:"),
    );
    return (
      <div className="space-y-2">
        {lead ? <p className={cn("text-xs leading-relaxed", tone.bodyMuted)}>{lead}</p> : null}
        <ul className="grid auto-rows-fr gap-2 sm:grid-cols-2">
          {items.map((line) => {
            const [title, detail] = splitReliefLine(line);
            return (
              <li
                key={line}
                className={cn(
                  "flex h-full flex-col rounded-md border px-2.5 py-2",
                  tone.nestCard,
                )}
              >
                <p className={cn("text-xs font-medium leading-snug", tone.nestTitle)}>{title}</p>
                {detail ? (
                  <p className={cn("mt-1 flex-1 text-[11px] leading-relaxed", tone.nestBody)}>
                    {detail}
                  </p>
                ) : null}
              </li>
            );
          })}
        </ul>
        {closing ? (
          <p className={cn("rounded-md border px-2.5 py-2 text-xs font-medium", tone.nestFooter)}>
            {closing}
          </p>
        ) : null}
      </div>
    );
  }

  if (isTaxSteps) {
    const intro = lead;
    const steps = rest.filter((line) => line.startsWith("Step "));
    const footer = rest.filter((line) => !line.startsWith("Step "));
    return (
      <div className="space-y-2">
        {intro ? <p className={cn("text-xs leading-relaxed", tone.bodyMuted)}>{intro}</p> : null}
        <ol className="space-y-1.5">
          {steps.map((line, index) => (
            <li
              key={line}
              className={cn("flex gap-2 rounded-md border px-2.5 py-2", tone.nestCard)}
            >
              <span
                className={cn(
                  "flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold",
                  tone.stepBadge,
                )}
              >
                {index + 1}
              </span>
              <p className={cn("text-xs leading-relaxed", tone.stepBadgeText)}>
                {stripStepPrefix(line)}
              </p>
            </li>
          ))}
        </ol>
        {footer.map((line) => (
          <p
            key={line}
            className={cn("rounded-md border px-2.5 py-2 text-xs font-medium", tone.nestFooter)}
          >
            {line}
          </p>
        ))}
      </div>
    );
  }

  return (
    <ul className="space-y-1.5">
      {block.lines.map((line) => (
        <li key={line} className={cn("text-xs leading-relaxed", tone.bodyMuted)}>
          {line}
        </li>
      ))}
    </ul>
  );
}

function splitReliefLine(line: string): [string, string] {
  const dash = line.indexOf(" — ");
  if (dash < 0) return [line, ""];
  return [line.slice(0, dash), line.slice(dash + 3)];
}

function stripStepPrefix(line: string): string {
  return line.replace(/^Step \d+:\s*/, "");
}

/** Plain English walkthrough. Default auditor tone; taxpayer uses TaxWise dark tokens. */
export function PlainExplanationView({
  explanation,
  className,
  footer,
  variant = "auditor",
}: {
  explanation: PlainExplanation;
  className?: string;
  footer?: ReactNode;
  variant?: PlainExplanationVariant;
}) {
  const tone = TONES[variant];

  return (
    <section className={cn(tone.section, className)}>
      <div className={cn("mb-3 border-b pb-3", tone.headerBorder)}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h3 className={cn("text-sm font-semibold", tone.title)}>{tone.titleText}</h3>
          <p className={cn("text-[11px]", tone.subtitle)}>{tone.subtitleText}</p>
        </div>
        <div className={cn("mt-2 rounded-lg border px-2.5 py-2", tone.summaryCard)}>
          <p className={cn("text-sm font-semibold leading-snug", tone.summaryTitle)}>
            {explanation.headline}
          </p>
          <p className={cn("mt-1 text-xs leading-relaxed", tone.summaryBody)}>
            {explanation.summary}
          </p>
        </div>
      </div>

      <ol className="space-y-3">
        {explanation.blocks.map((block, index) => {
          const isBottom = block.heading === "The bottom line";
          return (
            <li
              key={block.heading}
              className={cn(
                "rounded-lg border px-2.5 py-2.5",
                isBottom ? tone.stepCardBottom : tone.stepCard,
              )}
            >
              <div className="mb-2 flex items-center gap-2">
                <span
                  className={cn(
                    "flex h-6 w-6 items-center justify-center rounded-md",
                    isBottom ? tone.stepIconBottom : tone.stepIcon,
                  )}
                >
                  <StepIcon heading={block.heading} />
                </span>
                <div className="min-w-0">
                  <p
                    className={cn(
                      "text-[10px] font-medium uppercase tracking-wide",
                      tone.stepLabel,
                    )}
                  >
                    Step {index + 1}
                  </p>
                  <h4 className={cn("text-xs font-semibold", tone.stepHeading)}>
                    {block.heading}
                  </h4>
                </div>
              </div>
              <BlockBody block={block} tone={tone} />
            </li>
          );
        })}
      </ol>
      {footer ? (
        <div className={cn("mt-3 border-t pt-3", tone.footerBorder)}>{footer}</div>
      ) : null}
    </section>
  );
}
