import { useState, type ComponentType, type ReactNode } from "react";
import {
  AlertCircle,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Eye,
  EyeOff,
  Info,
  Plus,
  Save,
  Trash2,
} from "lucide-react";

import { cn } from "@/lib/utils";

import "../tax-return-profile.css";

export const TRP_COLORS = {
  teal: "var(--trp-teal)",
  blue: "var(--trp-blue)",
  green: "var(--trp-green)",
  amber: "var(--trp-amber)",
  red: "var(--trp-red)",
  purple: "var(--trp-purple)",
  primary: "var(--trp-primary)",
  secondary: "var(--trp-secondary)",
  muted: "var(--trp-muted)",
} as const;

export function Label({
  children,
  required,
  hint,
}: {
  children: ReactNode;
  required?: boolean;
  hint?: string;
}) {
  return (
    <div className="trp-label-row">
      <span className="trp-label">{children}</span>
      {required && <span className="trp-label-required">*</span>}
      {hint && (
        <span title={hint}>
          <Info size={10} className="trp-text-muted cursor-help" />
        </span>
      )}
    </div>
  );
}

export function Hint({ children }: { children: ReactNode }) {
  return <p className="trp-hint">{children}</p>;
}

type InputProps = {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  required?: boolean;
  hint?: string;
  mono?: boolean;
  prefix?: ReactNode;
  suffix?: ReactNode;
  type?: string;
};

export function Field({
  label,
  value,
  onChange,
  placeholder,
  required,
  hint,
  mono,
  prefix,
  suffix,
  type = "text",
}: InputProps) {
  return (
    <div className="trp-field">
      <Label required={required} hint={hint}>
        {label}
      </Label>
      <div className="trp-input-wrap">
        {prefix && <div className="trp-input-affix">{prefix}</div>}
        <input
          type={type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder || ""}
          className={cn("trp-input", mono && "trp-input--mono")}
        />
        {suffix && (
          <div className="trp-input-affix trp-input-affix--suffix">{suffix}</div>
        )}
      </div>
    </div>
  );
}

export function AmountField({
  label,
  value,
  onChange,
  required,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  hint?: string;
}) {
  return (
    <Field
      label={label}
      value={value}
      onChange={onChange}
      required={required}
      hint={hint}
      prefix="LKR"
      mono
      placeholder="0.00"
      type="number"
    />
  );
}

export function DateField({
  label,
  value,
  onChange,
  required,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
  hint?: string;
}) {
  return (
    <Field
      label={label}
      value={value}
      onChange={onChange}
      required={required}
      hint={hint}
      type="date"
    />
  );
}

type SelOption = { value: string; label: string };

export function Select({
  label,
  value,
  onChange,
  options,
  required,
  hint,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: SelOption[];
  required?: boolean;
  hint?: string;
}) {
  return (
    <div>
      <Label required={required} hint={hint}>
        {label}
      </Label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn("trp-select", !value && "trp-select--empty")}
      >
        <option value="">— Select —</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Textarea({
  label,
  value,
  onChange,
  placeholder,
  hint,
  rows = 3,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  hint?: string;
  rows?: number;
}) {
  return (
    <div>
      <Label hint={hint}>{label}</Label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        rows={rows}
        className="trp-textarea"
      />
    </div>
  );
}

export function Toggle({
  label,
  subLabel,
  checked,
  onChange,
}: {
  label: string;
  subLabel?: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className={cn("trp-toggle", checked && "trp-toggle--checked")}>
      <div>
        <div className="trp-toggle-label">{label}</div>
        {subLabel && <div className="trp-toggle-sublabel">{subLabel}</div>}
      </div>
      <button
        type="button"
        onClick={() => onChange(!checked)}
        className={cn("trp-toggle-btn", checked && "trp-toggle-btn--checked")}
        aria-pressed={checked}
      >
        <div className="trp-toggle-knob" />
      </button>
    </div>
  );
}

export function G2({ children }: { children: ReactNode }) {
  return <div className="trp-g2">{children}</div>;
}

export function G3({ children }: { children: ReactNode }) {
  return <div className="trp-g3">{children}</div>;
}

export function G4({ children }: { children: ReactNode }) {
  return <div className="trp-g4">{children}</div>;
}

export function Stack({
  children,
  gap = 14,
}: {
  children: ReactNode;
  gap?: number;
}) {
  const gapClass =
    gap === 8 ? "trp-stack--sm" : gap === 12 ? "trp-stack--md" : gap === 16 ? "trp-stack--lg" : "";
  return <div className={cn("trp-stack", gapClass)}>{children}</div>;
}

export function Rule({ label }: { label?: string }) {
  return (
    <div className="trp-rule">
      <div className="trp-rule-line" />
      {label && <span className="trp-rule-label">{label}</span>}
      <div className="trp-rule-line" />
    </div>
  );
}

const INFOBOX_CLASS: Record<string, string> = {
  blue: "trp-infobox--blue",
  teal: "trp-infobox--teal",
  green: "trp-infobox--green",
  amber: "trp-infobox--amber",
  red: "trp-infobox--red",
  purple: "trp-infobox--purple",
};

export function InfoBox({
  color = "blue",
  children,
}: {
  color?: keyof typeof INFOBOX_CLASS | string;
  children: ReactNode;
}) {
  const tone = INFOBOX_CLASS[color] ?? "trp-infobox--blue";
  return (
    <div className={cn("trp-infobox", tone)}>
      <AlertCircle size={13} className={cn("trp-text-" + color, "shrink-0 mt-px")} />
      <p className="trp-infobox-text">{children}</p>
    </div>
  );
}

export function StatChip({
  label,
  value,
  color = TRP_COLORS.teal,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="trp-stat-chip">
      <div className="trp-stat-chip-label">{label}</div>
      <div className="trp-stat-chip-value" style={{ color }}>
        {value}
      </div>
    </div>
  );
}

export function Card({
  title,
  subtitle,
  icon: Icon,
  accent = TRP_COLORS.teal,
  children,
  open: controlledOpen,
  defaultOpen = false,
  badge,
  badgeColor,
  optional,
}: {
  title: string;
  subtitle?: string;
  icon?: ComponentType<{ size?: number; style?: React.CSSProperties }>;
  accent?: string;
  children: ReactNode;
  open?: boolean;
  defaultOpen?: boolean;
  badge?: string;
  badgeColor?: string;
  optional?: boolean;
}) {
  const [localOpen, setLocalOpen] = useState(defaultOpen);
  const open = controlledOpen !== undefined ? controlledOpen : localOpen;

  return (
    <div
      className={cn("trp-card", open && "trp-card--open")}
      style={{ ["--trp-accent" as string]: accent }}
    >
      <button
        type="button"
        onClick={() => setLocalOpen((o) => !o)}
        className={cn("trp-card-header", open && "trp-card-header--open")}
      >
        {Icon && (
          <div
            className="trp-card-icon"
            style={{ background: `${accent}18` }}
          >
            <Icon size={15} style={{ color: accent }} />
          </div>
        )}
        <div className="min-w-0 flex-1">
          <div className="trp-card-title-row">
            <span className="trp-card-title">{title}</span>
            {optional && <span className="trp-card-optional">Optional</span>}
            {badge && (
              <span
                className="trp-card-badge"
                style={{
                  background: `${badgeColor || accent}18`,
                  color: badgeColor || accent,
                }}
              >
                {badge}
              </span>
            )}
          </div>
          {subtitle && <div className="trp-card-subtitle">{subtitle}</div>}
        </div>
        <div className="trp-text-muted shrink-0">
          {open ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </div>
      </button>
      {open && (
        <div className="trp-card-body">
          <div className="trp-card-divider" />
          {children}
        </div>
      )}
    </div>
  );
}

export function Builder<T extends object>({
  items,
  onAdd,
  onRemove,
  onChange,
  addLabel,
  entryLabel = "Entry",
  render,
}: {
  items: T[];
  onAdd: () => void;
  onRemove: (i: number) => void;
  onChange: (i: number, k: keyof T, v: string) => void;
  addLabel: string;
  entryLabel?: string;
  render: (
    item: T,
    i: number,
    upd: (k: keyof T, v: string) => void,
  ) => ReactNode;
}) {
  return (
    <Stack gap={12}>
      {items.map((item, i) => (
        <div key={i} className="trp-builder-entry">
          <div className="trp-builder-entry-header">
            <span className="trp-builder-entry-label">
              {entryLabel} #{i + 1}
            </span>
            {items.length > 1 && (
              <button type="button" onClick={() => onRemove(i)} className="trp-builder-remove">
                <Trash2 size={10} /> Remove
              </button>
            )}
          </div>
          {render(item, i, (k, v) => onChange(i, k, v))}
        </div>
      ))}
      <button type="button" onClick={onAdd} className="trp-builder-add">
        <Plus size={13} /> {addLabel}
      </button>
    </Stack>
  );
}

export function SectionHeader({
  icon: Icon,
  color,
  title,
  subtitle,
  sectionNum,
  totalSections,
  onSave,
  onComplete,
}: {
  icon: ComponentType<{ size?: number; style?: React.CSSProperties }>;
  color: string;
  title: string;
  subtitle: string;
  sectionNum: number;
  totalSections: number;
  onSave: () => void;
  onComplete: () => void;
}) {
  return (
    <div className="trp-section-header">
      <div className="trp-section-header-left">
        <div
          className="trp-section-icon"
          style={{ background: `${color}1a`, border: `1px solid ${color}30` }}
        >
          <Icon size={22} style={{ color }} />
        </div>
        <div>
          <div className="trp-section-kicker">
            SECTION {sectionNum} OF {totalSections}
          </div>
          <h2 className="trp-section-title">{title}</h2>
          <p className="trp-section-subtitle">{subtitle}</p>
        </div>
      </div>
      <div className="trp-section-actions">
        <button type="button" onClick={onSave} className="trp-btn-ghost">
          <Save size={12} /> Save Draft
        </button>
        <button type="button" onClick={onComplete} className="trp-btn-primary">
          <CheckCircle size={12} /> Mark Complete
        </button>
      </div>
    </div>
  );
}

export function NavFooter({
  sectionNum,
  total,
  onPrev,
  onNext,
}: {
  sectionNum: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="trp-nav-footer">
      <button
        type="button"
        onClick={onPrev}
        disabled={sectionNum === 1}
        className="trp-btn-nav"
      >
        <ChevronRight size={14} className="rotate-180" /> Previous
      </button>
      <span className="trp-nav-footer-count">
        {sectionNum} / {total}
      </span>
      <button
        type="button"
        onClick={onNext}
        disabled={sectionNum === total}
        className={cn("trp-btn-nav", sectionNum !== total && "trp-btn-nav-next")}
      >
        Next <ChevronRight size={14} />
      </button>
    </div>
  );
}

export function NicField({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div>
      <Label required hint="Your 10 or 12-digit NIC number">
        NIC Number
      </Label>
      <div className="trp-input-wrap">
        <input
          type={visible ? "text" : "password"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="e.g. 922345678V"
          className="trp-input trp-input--mono"
        />
        <button
          type="button"
          onClick={() => setVisible((v) => !v)}
          className="trp-input-btn"
          aria-label={visible ? "Hide NIC" : "Show NIC"}
        >
          {visible ? <EyeOff size={13} /> : <Eye size={13} />}
        </button>
      </div>
    </div>
  );
}
