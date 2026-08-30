import type { ComponentTraceItem, FilingCatalogCard } from "../api";
import { formatLkr } from "../format-lkr";

function Chip({ children }: { children: string }) {
  return (
    <span className="inline-flex max-w-full truncate rounded-md border bg-muted/60 px-1.5 py-0.5 text-[11px] text-foreground">
      {children}
    </span>
  );
}

const HEAD_SUBTOTAL_LABELS: Record<string, string> = {
  employment_include: "Employment included",
  employment_exempt: "Employment excluded",
  employment_net_for_assessable: "Employment net",
  business_net: "Business net",
  business_gross: "Business gross",
  investment_include: "Investment included",
  investment_exempt: "Investment excluded",
  other_include: "Other income included",
  other_exempt: "Other excluded",
  qualifying_payments_claimed: "QP claimed",
  donations_claimed: "Donations claimed",
  apit_already_paid: "APIT credit",
};

export function HeadSubtotalsPanel({
  subtotals,
}: {
  subtotals: Record<string, string> | undefined;
}) {
  if (!subtotals || Object.keys(subtotals).length === 0) return null;

  const rows = Object.entries(subtotals).filter(([, v]) => v && v !== "0");
  if (rows.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-muted-foreground">Head subtotals</p>
      <div className="flex flex-wrap gap-1.5">
        {rows.map(([key, value]) => (
          <Chip key={key}>{`${HEAD_SUBTOTAL_LABELS[key] ?? key}: ${formatLkr(value)}`}</Chip>
        ))}
      </div>
    </div>
  );
}

export function ComponentTraceByCard({
  trace,
  cards,
}: {
  trace: ComponentTraceItem[] | undefined;
  cards: FilingCatalogCard[];
}) {
  if (!trace?.length) return null;

  const cardLabel = (cardId: string | null | undefined): string => {
    if (!cardId) return "Other";
    return cards.find((c) => c.card_id === cardId)?.display_name ?? cardId;
  };

  const grouped = new Map<string, ComponentTraceItem[]>();
  for (const row of trace) {
    const key = row.card_id ?? "_other";
    const list = grouped.get(key) ?? [];
    list.push(row);
    grouped.set(key, list);
  }

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-muted-foreground">Component trace by catalog card</p>
      {Array.from(grouped.entries()).map(([cardId, rows]) => (
        <div key={cardId} className="space-y-1.5">
          <p className="text-[11px] font-medium text-foreground/80">
            {cardLabel(cardId === "_other" ? null : cardId)}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {rows.map((row) => (
              <Chip key={`${row.component_id}-${row.treatment_applied}`}>
                {`${row.display_name}: ${formatLkr(row.amount)} (${row.treatment_applied}${row.legal_confidence ? ` · ${row.legal_confidence}` : ""})`}
              </Chip>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
