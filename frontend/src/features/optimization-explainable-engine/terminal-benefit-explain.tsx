import type { TerminalBenefitBand, TerminalBenefitLadder } from "./api";
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
          <p className="text-[10px] font-medium text-muted-foreground">Provenance</p>
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
