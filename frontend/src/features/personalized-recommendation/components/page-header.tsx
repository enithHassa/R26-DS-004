import type { ComponentType } from "react";

type Props = {
  icon: ComponentType<{ className?: string }>;
  title: string;
  description?: string;
};

/** Branded page header used across the auditor dashboard for visual consistency. */
export function PageHeader({ icon: Icon, title, description }: Props) {
  return (
    <div className="flex items-start gap-3">
      <div
        className="flex h-11 w-11 flex-none items-center justify-center rounded-xl shadow-sm"
        style={{
          background:
            "linear-gradient(135deg, var(--primary) 0%, var(--tax-accent) 100%)",
        }}
      >
        <Icon className="h-5 w-5 text-white" />
      </div>
      <div className="min-w-0 pt-0.5">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-0.5 text-muted-foreground">{description}</p>}
      </div>
    </div>
  );
}
