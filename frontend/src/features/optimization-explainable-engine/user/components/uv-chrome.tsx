import type { ReactNode } from "react";

import { yaDisplay } from "../../format-lkr";

type YaSelectorProps = {
  value: string;
  years: string[];
  onChange: (ya: string) => void;
};

export function YaSelector({ value, years, onChange }: YaSelectorProps) {
  return (
    <label className="flex items-center gap-2 text-sm text-[var(--uv-text-muted)]">
      <span className="shrink-0">Assessment year</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-[var(--uv-border)] bg-[var(--uv-bg-card)] px-3 py-1.5 text-[var(--uv-text)] outline-none focus:border-[var(--uv-accent)]"
      >
        {years.map((ya) => (
          <option key={ya} value={ya}>
            YA {yaDisplay(ya)}
          </option>
        ))}
      </select>
    </label>
  );
}

export function UvTile({
  label,
  value,
  emphasize,
}: {
  label: string;
  value: string;
  emphasize?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border border-[var(--uv-border)] bg-[var(--uv-bg-card)] p-4 ${
        emphasize ? "ring-1 ring-[var(--uv-accent)]/40" : ""
      }`}
    >
      <p className="text-xs text-[var(--uv-text-muted)]">{label}</p>
      <p
        className={`mt-1 text-lg font-semibold tracking-tight ${
          emphasize ? "text-[var(--uv-accent)]" : "text-[var(--uv-text)]"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

export function UvPanelShell({
  children,
  header,
}: {
  children: ReactNode;
  header?: ReactNode;
}) {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      {header}
      {children}
    </div>
  );
}
