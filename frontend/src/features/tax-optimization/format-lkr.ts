/** Display helper for dissertation UI — LKR with grouped thousands. */

const nf = new Intl.NumberFormat("en-LK", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

export function formatLkrAmount(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "number" ? value : parseFloat(String(value).replace(/,/g, "").trim());
  if (!Number.isFinite(n)) return String(value);
  return `LKR ${nf.format(n)}`;
}

export function parseDecimalSafe(value: string | null | undefined): number | null {
  if (value == null || value === "") return null;
  const n = parseFloat(String(value).trim());
  return Number.isFinite(n) ? n : null;
}
