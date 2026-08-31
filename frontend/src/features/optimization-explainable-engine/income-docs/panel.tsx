import { useState, type ComponentType } from "react";
import {
  Briefcase,
  Building2,
  ChevronDown,
  ChevronRight,
  Gift,
  Landmark,
  Wallet,
} from "lucide-react";

import { cn } from "@/lib/utils";

import { INCOME_DOC_CATEGORIES, type IncomeDocCategoryId } from "./catalog";
import { IncomeDocSlotRow } from "./slot";
import { countIncomeDocsForCategory } from "./store";
import { useIncomeDocsRevision } from "./use-income-docs";

type Mode = "upload" | "auditor";

const CATEGORY_UI: Record<
  IncomeDocCategoryId,
  { accent: string; Icon: ComponentType<{ className?: string; size?: number }> }
> = {
  employment: { accent: "teal", Icon: Briefcase },
  business: { accent: "blue", Icon: Building2 },
  investment: { accent: "green", Icon: Landmark },
  other_income: { accent: "purple", Icon: Wallet },
  terminal_benefits: { accent: "amber", Icon: Gift },
};

export function IncomeDocsCategoryPanel({
  profileId,
  assessmentYear,
  categoryId,
  mode,
  defaultOpen = false,
  className,
  surface = "default",
}: {
  profileId: string | null | undefined;
  assessmentYear: string;
  categoryId: IncomeDocCategoryId;
  mode: Mode;
  defaultOpen?: boolean;
  className?: string;
  surface?: "default" | "trp";
}) {
  const category = INCOME_DOC_CATEGORIES.find((c) => c.category_id === categoryId);
  const [open, setOpen] = useState(defaultOpen);
  useIncomeDocsRevision();
  if (!category) return null;

  const count = countIncomeDocsForCategory(profileId, assessmentYear, categoryId);
  const ui = CATEGORY_UI[categoryId];
  const Icon = ui.Icon;
  const isTrp = surface === "trp";

  if (isTrp) {
    return (
      <div
        className={cn("trp-income-docs-cat", className)}
        data-accent={ui.accent}
        data-open={open ? "true" : "false"}
      >
        <button
          type="button"
          className="trp-income-docs-cat-btn"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
        >
          <span className="trp-income-docs-cat-icon" aria-hidden>
            <Icon size={18} />
          </span>
          <span className="trp-income-docs-cat-meta">
            <span className="trp-income-docs-cat-title-row">
              <span className="trp-income-docs-cat-title">{category.display_name}</span>
              <span className="trp-income-docs-cat-badge">{category.section_badge}</span>
              <span className={cn("trp-income-docs-cat-count", count > 0 && "is-ready")}>
                {count > 0 ? `${count} doc${count === 1 ? "" : "s"}` : "No docs"}
              </span>
            </span>
            <span className="trp-income-docs-cat-desc">
              {mode === "auditor"
                ? "Taxpayer uploads for this income head — use them while filling amounts."
                : category.description}
            </span>
          </span>
          <span className="trp-income-docs-cat-chevron" aria-hidden>
            {open ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
          </span>
        </button>
        {open ? (
          <div className="trp-income-docs-slots">
            {category.slots.map((slot) => (
              <IncomeDocSlotRow
                key={slot.slot_id}
                profileId={profileId}
                assessmentYear={assessmentYear}
                categoryId={category.category_id}
                slotId={slot.slot_id}
                label={slot.label}
                hint={slot.hint}
                mode={mode}
                surface="trp"
              />
            ))}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border border-border/80 bg-card/40 shadow-sm",
        className,
      )}
    >
      <button
        type="button"
        className="flex w-full items-start gap-3 px-3.5 py-3 text-left transition-colors hover:bg-muted/40"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">{category.display_name}</span>
            <span className="rounded-full border bg-muted/50 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
              {category.section_badge}
            </span>
            {count > 0 ? (
              <span className="rounded-full border border-emerald-500/40 bg-emerald-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300">
                {count} doc{count === 1 ? "" : "s"}
              </span>
            ) : (
              <span className="rounded-full border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                No docs
              </span>
            )}
          </span>
          <span className="mt-0.5 block text-[11px] text-muted-foreground">
            {mode === "auditor"
              ? "Taxpayer uploads for this income head — use them while filling amounts."
              : category.description}
          </span>
        </span>
        <span className="mt-1 text-muted-foreground">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </span>
      </button>
      {open ? (
        <div className="grid gap-2.5 border-t bg-muted/20 px-3 py-3 sm:grid-cols-2">
          {category.slots.map((slot) => (
            <IncomeDocSlotRow
              key={slot.slot_id}
              profileId={profileId}
              assessmentYear={assessmentYear}
              categoryId={category.category_id}
              slotId={slot.slot_id}
              label={slot.label}
              hint={slot.hint}
              mode={mode}
              surface="default"
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function IncomeDocsFullPanel({
  profileId,
  assessmentYear,
  yearOptions,
  onYearChange,
  mode = "upload",
}: {
  profileId: string;
  assessmentYear: string;
  yearOptions: { value: string; label: string }[];
  onYearChange: (ya: string) => void;
  mode?: Mode;
}) {
  useIncomeDocsRevision();

  return (
    <div className="trp-income-docs">
      <div className="trp-income-docs-head">
        <div>
          <p className="trp-income-docs-kicker">Supporting evidence</p>
          <p className="trp-income-docs-title">Additional documents</p>
          <p className="trp-income-docs-copy">
            Upload invoices and certificates for each income head — same layout as the Income form —
            plus retirement and terminal benefit papers for your auditor.
          </p>
        </div>
        <label className="trp-income-docs-year">
          Year of Assessment
          <select value={assessmentYear} onChange={(e) => onYearChange(e.target.value)}>
            {yearOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="trp-income-docs-list">
        {INCOME_DOC_CATEGORIES.map((cat) => (
          <IncomeDocsCategoryPanel
            key={cat.category_id}
            profileId={profileId}
            assessmentYear={assessmentYear}
            categoryId={cat.category_id}
            mode={mode}
            defaultOpen={cat.category_id === "employment"}
            surface="trp"
          />
        ))}
      </div>
    </div>
  );
}
