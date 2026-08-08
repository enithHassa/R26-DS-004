/** Local LKR display helpers for Adaptive Tax (do not import tax-optimization). */

const nf = new Intl.NumberFormat("en-LK", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

export function formatLkr(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n =
    typeof value === "number"
      ? value
      : parseFloat(String(value).replace(/,/g, "").trim());
  if (!Number.isFinite(n)) return String(value);
  return `LKR ${nf.format(n)}`;
}

/** Normalize user input to a non-negative integer LKR string for the API. */
export function toMoneyWire(raw: string): string {
  const cleaned = raw.replace(/,/g, "").trim();
  if (!cleaned) return "0";
  const n = Number(cleaned);
  if (!Number.isFinite(n) || n < 0) return "0";
  return String(Math.round(n));
}
