import { BarChart3 } from "lucide-react";

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 px-8 py-16 text-center">
      <BarChart3 className="mb-3 h-10 w-10 text-[var(--revenue-muted)]" />
      <p className="max-w-md text-sm text-[var(--revenue-muted)]">{message}</p>
    </div>
  );
}
