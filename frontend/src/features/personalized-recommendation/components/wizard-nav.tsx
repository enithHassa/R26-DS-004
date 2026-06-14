import { cn } from "@/lib/utils";

type Props = {
  steps: string[];
  current: number;
  onStepClick?: (index: number) => void;
};

export function WizardNav({ steps, current, onStepClick }: Props) {
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
              active && "border-primary bg-primary text-primary-foreground",
              done && !active && "border-primary/40 bg-primary/10 text-primary",
              !done && !active && "border-border bg-muted/30 text-muted-foreground hover:bg-muted/50",
            )}
          >
            <span
              className={cn(
                "flex h-5 w-5 items-center justify-center rounded-full text-[10px]",
                active ? "bg-primary-foreground/20" : "bg-muted",
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
