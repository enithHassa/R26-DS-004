import { useState } from "react";
import {
  Briefcase,
  Building2,
  CheckCircle,
  FileCheck,
  FolderOpen,
  Globe,
  Home,
  Landmark,
  Shield,
  User,
} from "lucide-react";

import { useEvidenceYearOptions } from "@/features/optimization-explainable-engine/relief-evidence";
import { yaDisplay } from "@/features/optimization-explainable-engine/format-lkr";
import { normalizeTaxYearToOrm } from "@/lib/profile-bridge/tax-year-bridge";
import { cn } from "@/lib/utils";

import { TRP_COLORS } from "./ui/primitives";
import { useTaxReturnProfile } from "./use-tax-return-profile";
import { NavFooter } from "./ui/primitives";
import {
  Sec1,
  Sec2,
  Sec3,
  Sec4,
  Sec5,
  Sec6,
  Sec7,
  Sec8,
  SecAdditionalDocs,
} from "./ui/sections";

import "./tax-return-profile.css";

const SECTIONS = [
  { num: 1, label: "Taxpayer Identity & Statutory Status", short: "Identity", icon: User, color: TRP_COLORS.teal },
  { num: 2, label: "Employment & Remuneration", short: "Employment", icon: Briefcase, color: TRP_COLORS.blue },
  { num: 3, label: "Fixed Deposits & Investments", short: "Investments", icon: Landmark, color: TRP_COLORS.green },
  { num: 4, label: "Business, Freelance & Trades", short: "Business", icon: Building2, color: TRP_COLORS.purple },
  { num: 5, label: "Real Estate & Rental Incomes", short: "Real Estate", icon: Home, color: TRP_COLORS.amber },
  { num: 6, label: "Deductions & Qualifying Reliefs", short: "Deductions", icon: Shield, color: TRP_COLORS.green },
  { num: 7, label: "Foreign Income & Overseas Assets", short: "Foreign", icon: Globe, color: TRP_COLORS.blue },
  { num: 8, label: "Additional Documents", short: "Documents", icon: FolderOpen, color: TRP_COLORS.blue },
  { num: 9, label: "Review & Declaration", short: "Review", icon: FileCheck, color: TRP_COLORS.teal },
] as const;

function formatLkr(amount: string): string {
  const n = Number(amount);
  if (!Number.isFinite(n)) return amount;
  return `LKR ${n.toLocaleString("en-LK")}`;
}

function computeQuickEstimates(detail: NonNullable<ReturnType<typeof useTaxReturnProfile>["detail"]>) {
  const empGross = detail.section2.employers.reduce((sum, e) => sum + (Number(e.gross) || 0), 0);
  const bonus = detail.section2.employers.reduce((sum, e) => sum + (Number(e.bonus) || 0), 0);
  const freelance = Number(detail.section4.freelanceLkr) || 0;
  const rental = detail.section5.properties.reduce((sum, p) => sum + (Number(p.gross) || 0), 0);
  const totalIncome = empGross + bonus + freelance + rental;

  const epf = detail.section2.employers.reduce((sum, e) => sum + (Number(e.epf) || 0), 0);
  const life = Number(detail.section6.lifePremium) || 0;
  const mortgage = Number(detail.section6.mortgageInterest) || 0;
  const personalRelief = 3_000_000;
  const totalDeductions = personalRelief + epf + life + mortgage;

  const apit = detail.section2.employers.reduce((sum, e) => sum + (Number(e.apit) || 0), 0);
  const taxable = Math.max(0, totalIncome - totalDeductions);
  const grossTax = taxable * 0.18;
  const taxPayable = Math.max(0, grossTax - apit);

  return {
    totalIncome: formatLkr(String(Math.round(totalIncome))),
    totalDeductions: formatLkr(String(Math.round(totalDeductions))),
    taxPayable: formatLkr(String(Math.round(taxPayable))),
  };
}

export function TaxReturnProfile({ profileId }: { profileId: string }) {
  const {
    detail,
    setDetail,
    completed,
    activeSection,
    setActiveSection,
    saveDraft,
    markComplete,
    isSaving,
    isLoading,
    loadError,
    saveError,
  } = useTaxReturnProfile(profileId);
  const [evidenceYear, setEvidenceYear] = useState("");
  const profileTaxYearOrm = normalizeTaxYearToOrm(detail?.section1.taxYear) ?? "";
  const resolvedEvidenceYear = evidenceYear || profileTaxYearOrm;
  const evidenceYearOptions = useEvidenceYearOptions(resolvedEvidenceYear);

  if (isLoading) {
    return <div className="trp-loading">Loading tax return profile…</div>;
  }

  if (loadError) {
    const message =
      loadError instanceof Error ? loadError.message : "Could not load your profile from the server.";
    const needsMigration =
      message.includes("500") ||
      message.toLowerCase().includes("internal server") ||
      message.toLowerCase().includes("network");
    return (
      <div className="trp-loading max-w-lg space-y-3 text-left">
        <p className="trp-text-red font-semibold">Failed to load tax return profile</p>
        <p className="text-sm text-[var(--uv-text-muted)]">{message}</p>
        {needsMigration && (
          <p className="text-sm text-[var(--uv-text-muted)]">
            If you just pulled the latest code, run{" "}
            <code className="rounded bg-black/20 px-1.5 py-0.5">alembic upgrade head</code> against
            your database, then restart Comp 3 on port 8003.
          </p>
        )}
      </div>
    );
  }

  if (!detail) {
    return <div className="trp-loading">Preparing tax return profile…</div>;
  }

  const progress = Math.round((completed.size / SECTIONS.length) * 100);
  const estimates = computeQuickEstimates(detail);
  const taxYear = detail.section1.taxYear;
  const saveErrorMessage =
    saveError instanceof Error ? saveError.message : saveError ? String(saveError) : null;

  const sectionProps = {
    detail,
    onDetailChange: setDetail,
    onSave: () => void saveDraft(),
    onComplete: () => {
      void saveDraft();
      void markComplete(activeSection);
    },
  };

  return (
    <div className="tax-return-profile">
      <div className="trp-topbar">
        <div>
          <h1 className="trp-topbar-title">Tax Return Profile</h1>
          <p className="trp-topbar-subtitle">
            Year of Assessment {taxYear.replace("-", " / ")} · Due: 30 November{" "}
            {taxYear.split("-")[1] ?? "2025"}
            {isSaving ? " · Saving…" : ""}
          </p>
          <label className="trp-topbar-year">
            <span>Supporting docs year</span>
            <select
              value={resolvedEvidenceYear}
              onChange={(event) => setEvidenceYear(event.target.value)}
              aria-label="Year of assessment for supporting documents"
            >
              {evidenceYearOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
              {resolvedEvidenceYear &&
              !evidenceYearOptions.some((opt) => opt.value === resolvedEvidenceYear) ? (
                <option value={resolvedEvidenceYear}>
                  YA {yaDisplay(resolvedEvidenceYear)}
                </option>
              ) : null}
            </select>
          </label>
        </div>
        <div className="trp-progress-wrap">
          <div>
            <div className="trp-progress-label">RETURN COMPLETION</div>
            <div className="trp-progress-value">{progress}%</div>
          </div>
          <div className="flex flex-col gap-[5px]">
            <div className="trp-progress-bar-track">
              <div className="trp-progress-bar-fill" style={{ width: `${progress}%` }} />
            </div>
            <div className="trp-progress-dots">
              {SECTIONS.map((s) => (
                <button
                  key={s.num}
                  type="button"
                  title={s.short}
                  onClick={() => setActiveSection(s.num)}
                  className={cn(
                    "trp-progress-dot",
                    completed.has(s.num) && "trp-progress-dot--done",
                    activeSection === s.num && !completed.has(s.num) && "trp-progress-dot--active",
                  )}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      <div className="trp-shell-body">
        <aside className="trp-sidebar">
          <div className="trp-sidebar-header">
            <div className="trp-sidebar-heading">TAX RETURN SECTIONS</div>
          </div>
          <div className="trp-sidebar-nav">
            {SECTIONS.map((s) => {
              const isActive = activeSection === s.num;
              const isDone = completed.has(s.num);
              const Icon = s.icon;
              return (
                <button
                  key={s.num}
                  type="button"
                  onClick={() => setActiveSection(s.num)}
                  className="trp-nav-item"
                  style={{
                    background: isActive ? `${s.color}12` : "transparent",
                    borderLeftColor: isActive ? s.color : "transparent",
                  }}
                >
                  <div
                    className="trp-nav-item-icon"
                    style={{
                      background: isDone
                        ? `${TRP_COLORS.green}20`
                        : isActive
                          ? `${s.color}20`
                          : `${TRP_COLORS.muted}15`,
                    }}
                  >
                    {isDone ? (
                      <CheckCircle size={12} className="trp-text-green" />
                    ) : (
                      <Icon size={12} style={{ color: isActive ? s.color : TRP_COLORS.muted }} />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div
                      className="trp-nav-item-label"
                      style={{
                        color: isActive
                          ? TRP_COLORS.primary
                          : isDone
                            ? TRP_COLORS.secondary
                            : TRP_COLORS.muted,
                        fontWeight: isActive ? 600 : 400,
                      }}
                    >
                      {s.label}
                    </div>
                    <div
                      className="trp-nav-item-status"
                      style={{ color: isDone ? TRP_COLORS.green : TRP_COLORS.muted }}
                    >
                      {isDone ? "✓ Complete" : isActive ? "In progress" : "Pending"}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
          <div className="trp-quick-estimates">
            <div className="trp-quick-estimates-heading">QUICK ESTIMATES</div>
            <div className="trp-stack trp-stack--sm">
              {[
                ["Total Income", estimates.totalIncome, TRP_COLORS.primary],
                ["Total Deductions", estimates.totalDeductions, TRP_COLORS.green],
                ["Tax Payable", estimates.taxPayable, TRP_COLORS.amber],
              ].map(([label, value, color]) => (
                <div key={label as string} className="trp-quick-row">
                  <span className="trp-quick-label">{label as string}</span>
                  <span className="trp-quick-value trp-font-mono" style={{ color: color as string }}>
                    {value as string}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </aside>

        <div className="trp-main">
          {saveErrorMessage ? (
            <div
              className="mb-4 rounded-md border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-300"
              role="alert"
            >
              <p className="font-semibold">Could not save draft</p>
              <p className="mt-1 text-red-200/90">{saveErrorMessage}</p>
            </div>
          ) : null}

          {activeSection === 1 && <Sec1 {...sectionProps} />}
          {activeSection === 2 && <Sec2 {...sectionProps} />}
          {activeSection === 3 && <Sec3 {...sectionProps} />}
          {activeSection === 4 && <Sec4 {...sectionProps} />}
          {activeSection === 5 && <Sec5 {...sectionProps} />}
          {activeSection === 6 && (
            <Sec6
              {...sectionProps}
              profileId={profileId}
              evidenceYear={resolvedEvidenceYear}
              onEvidenceYearChange={setEvidenceYear}
              evidenceYearOptions={evidenceYearOptions}
            />
          )}
          {activeSection === 7 && <Sec7 {...sectionProps} />}
          {activeSection === 8 && (
            <SecAdditionalDocs
              onSave={sectionProps.onSave}
              onComplete={sectionProps.onComplete}
              profileId={profileId}
              evidenceYear={resolvedEvidenceYear}
              onEvidenceYearChange={setEvidenceYear}
              evidenceYearOptions={evidenceYearOptions}
            />
          )}
          {activeSection === 9 && (
            <Sec8 detail={detail} onDetailChange={setDetail} completedSections={completed} />
          )}

          <NavFooter
            sectionNum={activeSection}
            total={SECTIONS.length}
            onPrev={() => setActiveSection((a) => Math.max(1, a - 1))}
            onNext={() => setActiveSection((a) => Math.min(SECTIONS.length, a + 1))}
          />
        </div>
      </div>
    </div>
  );
}
