/** Local LKR display helpers for Optimization and Explainable. */

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

export function formatMoneyInput(raw: string): string {
  const digits = String(raw ?? "").replace(/[^\d]/g, "");
  if (!digits) return "";
  const normalized = digits.replace(/^0+(?=\d)/, "");
  return nf.format(Number(normalized));
}

export function parseLkr(value: string | null | undefined): number {
  const cleaned = String(value ?? "").replace(/,/g, "").trim();
  const n = Number(cleaned);
  return Number.isFinite(n) && n >= 0 ? n : 0;
}

/** Display label e.g. 2024_25 → 2024/25 */
export function yaDisplay(ya: string): string {
  const m = /^(\d{4})_(\d{2})$/.exec(ya);
  if (!m) return ya;
  return `${m[1]}/${m[2]}`;
}
