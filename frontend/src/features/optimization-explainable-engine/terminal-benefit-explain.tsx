import { X } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";

import { getRates, type TerminalBenefitBand, type TerminalBenefitLadder } from "./api";
import { formatLkr, yaDisplay } from "./format-lkr";
import { TERMINAL_BENEFIT_TYPE_OPTIONS } from "./terminal-benefits";

const NO_RULE =
  "No promoted terminal-benefit rule is currently available for this assessment year.";
const NO_QUOTE = "Act quotation is not currently available.";
const SPLIT_YEAR = "Terminal-benefit rates changed during this assessment year.";

const CONDITION_LABELS: Record<string, string> = {
  upto_20_years: "20 years or less",
  over_20_years: "More than 20 years",
  not_applicable: "Employment period is not used for this ladder",
};

export function formatIsoDate(iso: string | undefined): string {
  const text = (iso || "").trim();
  if (!text) return "";
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(text);
  if (!match) return text;
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])));
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function qualifyingTypeLabel(type: string): string {
  const found = TERMINAL_BENEFIT_TYPE_OPTIONS.find((option) => option.value === type);
  if (found) return found.label;
  return type.replace(/_/g, " ");
}

function periodKey(ladder: TerminalBenefitLadder): string {
  return `${ladder.period_from || ""}|${ladder.period_to || ""}`;
}

export function groupLaddersByPeriod(ladders: TerminalBenefitLadder[]): {
  periodFrom: string;
  periodTo: string;
  ladders: TerminalBenefitLadder[];
}[] {
  const order: string[] = [];
  const buckets = new Map<string, TerminalBenefitLadder[]>();
  for (const ladder of ladders) {
    const key = periodKey(ladder);
    if (!buckets.has(key)) {
      order.push(key);
      buckets.set(key, []);
    }
    buckets.get(key)?.push(ladder);
  }
  return order
    .map((key) => {
      const [periodFrom = "", periodTo = ""] = key.split("|");
      return { periodFrom, periodTo, ladders: buckets.get(key) ?? [] };
    })
    .sort((a, b) => a.periodFrom.localeCompare(b.periodFrom));
}

function bandBound(raw: number | string | null | undefined): string {
  if (raw == null || raw === "") return "and above";
  return formatLkr(raw);
}

function BandList({ bands }: { bands: TerminalBenefitBand[] }) {
  if (!bands.length) return null;
  return (
    <ul className="list-disc space-y-1 pl-5 text-[11px] text-muted-foreground">
      {bands.map((band, index) => {
        const label = (band.band_label || "").trim();
        const rate = band.rate_percent == null || band.rate_percent === "" ? "" : `${band.rate_percent}%`;
        const range = `${bandBound(band.lower)} – ${bandBound(band.upper)}`;
        return (
          <li key={`${band.band_index ?? index}-${rate}`}>
            {label ? `${label} · ` : ""}
            {range}
            {rate ? ` · ${rate}` : ""}
          </li>
        );
      })}
    </ul>
  );
}

function LadderBlock({ ladder }: { ladder: TerminalBenefitLadder }) {
  const actName = (ladder.act_name || "").trim();
  const from = formatIsoDate(ladder.period_from || ladder.effective_from);
  const to = formatIsoDate(ladder.period_to || ladder.effective_to);
  const types = ladder.qualifying_income_types ?? [];
  const condition = (ladder.employment_period_condition || "").trim();
  const quote = (ladder.quote || "").trim();
  const bands = ladder.bands ?? [];

  return (
    <div className="space-y-2 rounded-md border bg-muted/20 p-2">
      {actName ? (
        <div className="space-y-0.5">
          <p className="text-[10px] font-medium text-muted-foreground">Applicable Act</p>
          <p className="text-[11px]">{actName}</p>
        </div>
      ) : null}
      {from || to ? (
        <div className="space-y-0.5">
          <p className="text-[10px] font-medium text-muted-foreground">Effective period</p>
          <p className="text-[11px]">
            {from && to ? `${from} – ${to}` : from ? `From ${from}` : to}
          </p>
        </div>
      ) : null}
      {types.length > 0 ? (
        <div className="space-y-0.5">
          <p className="text-[10px] font-medium text-muted-foreground">Applies to</p>
          <p className="text-[11px]">{types.map(qualifyingTypeLabel).join(", ")}</p>
        </div>
      ) : null}
      {condition && condition !== "not_applicable" ? (
        <div className="space-y-0.5">
          <p className="text-[10px] font-medium text-muted-foreground">Conditions</p>
          <p className="text-[11px]">{CONDITION_LABELS[condition] ?? condition}</p>
        </div>
      ) : null}
      {bands.length > 0 ? (
        <div className="space-y-0.5">
          <p className="text-[10px] font-medium text-muted-foreground">Tax treatment</p>
          <BandList bands={bands} />
        </div>
      ) : null}
      {ladder.source_doc_id || ladder.entry_id || ladder.section_ref ? (
        <div className="space-y-0.5">
          <p className="text-[10px] font-medium text-muted-foreground">Legal source</p>
          <p className="text-[11px] text-muted-foreground">
            {[ladder.source_doc_id, ladder.section_ref, ladder.entry_id]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
      ) : null}
      <div className="space-y-0.5">
        <p className="text-[10px] font-medium text-muted-foreground">Act quote</p>
        {quote ? (
          <blockquote className="rounded-md border bg-background px-2 py-1.5 text-[11px] italic leading-relaxed">
            “{quote}”
          </blockquote>
        ) : (
          <p className="text-[11px] text-muted-foreground">{NO_QUOTE}</p>
        )}
      </div>
    </div>
  );
}

export function TerminalBenefitExplainPanel({
  assessmentYear,
  ladders,
  loading,
  error,
}: {
  assessmentYear: string;
  ladders: TerminalBenefitLadder[] | undefined;
  loading?: boolean;
  error?: boolean;
}) {
  if (loading) {
    return <p className="text-[11px] text-muted-foreground">Loading the terminal-benefit rule for this year…</p>;
  }
  if (error) {
    return (
      <p className="text-[11px] text-muted-foreground">
        Could not load the promoted terminal-benefit rule for this assessment year.
      </p>
    );
  }
  const list = ladders ?? [];
  if (list.length === 0) {
    return <p className="text-[11px] text-muted-foreground">{NO_RULE}</p>;
  }
  const periods = groupLaddersByPeriod(list);
  const splitYear = periods.length > 1;

  return (
    <div className="space-y-3 text-[11px] leading-relaxed">
      <p className="font-medium text-foreground">
        Terminal-benefit rule for YA {yaDisplay(assessmentYear)}
      </p>
      {splitYear ? <p className="text-muted-foreground">{SPLIT_YEAR}</p> : null}
      {periods.map((period) => (
        <div key={`${period.periodFrom}|${period.periodTo}`} className="space-y-2">
          {splitYear && (period.periodFrom || period.periodTo) ? (
            <p className="font-medium text-foreground">
              {formatIsoDate(period.periodFrom)}
              {period.periodTo ? ` – ${formatIsoDate(period.periodTo)}` : ""}
            </p>
          ) : null}
          {period.ladders.map((ladder, index) => (
            <LadderBlock
              key={ladder.ladder_key || ladder.entry_id || `${period.periodFrom}-${index}`}
              ladder={ladder}
            />
          ))}
        </div>
      ))}
    </div>
  );
}

/** Same overlay + right drawer pattern as income field Explain. */
export function TerminalBenefitExplainDrawer({
  assessmentYear,
  actVersionLabel,
  open,
  onClose,
}: {
  assessmentYear: string;
  actVersionLabel?: string | null;
  open: boolean;
  onClose: () => void;
}) {
  const query = useQuery({
    queryKey: ["optimization-explainable-engine", "rates", assessmentYear],
    queryFn: () => getRates(assessmentYear),
    retry: false,
    enabled: open,
  });

  if (!open) return null;

  return (
    <>
      <button
        type="button"
        className="fixed inset-0 z-40 bg-black/40"
        aria-label="Close terminal benefit explain drawer"
        onClick={onClose}
      />
      <aside
        className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col border-l bg-background shadow-xl"
        role="dialog"
        aria-labelledby="oe-engine-terminal-explain-title"
      >
        <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
          <div className="space-y-1">
            <p id="oe-engine-terminal-explain-title" className="text-sm font-semibold">
              Retirement & terminal benefits
            </p>
            <p className="text-xs text-muted-foreground">
              Legal basis · terminal_benefit_tax_rate
            </p>
          </div>
          <Button type="button" size="sm" variant="ghost" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4 text-sm">
          <div className="flex flex-wrap gap-2">
            <span className="inline-flex max-w-full flex-wrap items-center gap-1 rounded border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-900 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">
              <span aria-hidden>✓</span>
              <span>High confidence</span>
              {actVersionLabel ? (
                <span className="text-muted-foreground">· {actVersionLabel}</span>
              ) : null}
            </span>
            <span className="inline-flex rounded border border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
              Special rate ladder (not ordinary income)
            </span>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Section</p>
            <p className="font-medium">Terminal-benefit tax rates</p>
            <p className="text-xs text-muted-foreground">
              Commuted pension, retiring gratuity, qualifying loss of office, and ETF at or
              after retirement are taxed on a separate progressive ladder for this year of
              assessment.
            </p>
          </div>

          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Year rule</p>
            <TerminalBenefitExplainPanel
              assessmentYear={assessmentYear}
              ladders={query.data?.terminal_benefit_ladders}
              loading={query.isPending}
              error={query.isError}
            />
          </div>
        </div>
      </aside>
    </>
  );
}
