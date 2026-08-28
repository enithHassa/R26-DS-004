import { cn } from "@/lib/utils";

type Props = {
  steps: string[];
  current: number;
  onStepClick?: (index: number) => void;
  theme?: "default" | "user-view";
};

export function WizardNav({ steps, current, onStepClick, theme = "default" }: Props) {
  const isUserView = theme === "user-view";

  return (
    <nav className="mb-6 flex flex-wrap gap-2" aria-label="Form steps">
      {steps.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <button
            key={label}
            type="button"
            onClick={() => onStepClick?.(i)}
            className={cn(
              "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors",
              isUserView
                ? cn(
                    active &&
                      "border-[var(--uv-accent)] bg-[var(--uv-accent)] text-[var(--uv-accent-foreground)]",
                    done &&
                      !active &&
                      "border-[var(--uv-accent)]/40 bg-[var(--uv-accent)]/10 text-[var(--uv-accent)]",
                    !done &&
                      !active &&
                      "border-[var(--uv-border)] bg-white/5 text-[var(--uv-text-muted)] hover:bg-white/10",
                  )
                : cn(
                    active && "border-primary bg-primary text-primary-foreground",
                    done && !active && "border-primary/40 bg-primary/10 text-primary",
                    !done && !active && "border-border bg-muted/30 text-muted-foreground hover:bg-muted/50",
                  ),
            )}
          >
            <span
              className={cn(
                "flex h-5 w-5 items-center justify-center rounded-full text-[10px]",
                isUserView
                  ? active
                    ? "bg-[var(--uv-accent-foreground)]/20"
                    : "bg-white/10"
                  : active
                    ? "bg-primary-foreground/20"
                    : "bg-muted",
              )}
            >
              {done && !active ? "✓" : i + 1}
            </span>
            {label}
          </button>
        );
      })}
    </nav>
  );
}
