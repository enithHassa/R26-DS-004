/** Local LKR display helpers for Optimization and Explainable Engine. */

const nfDisplay = new Intl.NumberFormat("en-LK", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

const nfInt = new Intl.NumberFormat("en-LK", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

/** Round to 2 decimal places (Sri Lankan rupees / cents). */
export function roundLkr(n: number): number {
  if (!Number.isFinite(n)) return 0;
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

export function formatLkr(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const n =
    typeof value === "number"
      ? value
      : parseFloat(String(value).replace(/,/g, "").trim());
  if (!Number.isFinite(n)) return String(value);
  return `LKR ${nfDisplay.format(roundLkr(n))}`;
}

/**
 * Live money input: thousands separators + up to 2 decimal places.
 * Preserves a trailing "." while the user is typing cents.
 */
export function formatMoneyInput(raw: string): string {
  const text = String(raw ?? "");
  const cleaned = text.replace(/[^\d.]/g, "");
  if (!cleaned) return "";

  const firstDot = cleaned.indexOf(".");
  const hasDot = firstDot >= 0;
  let intDigits = hasDot ? cleaned.slice(0, firstDot) : cleaned;
  let decDigits = hasDot ? cleaned.slice(firstDot + 1).replace(/\./g, "") : "";
  decDigits = decDigits.slice(0, 2);

  intDigits = intDigits.replace(/^0+(?=\d)/, "");
  if (!intDigits) intDigits = "0";

  const intFormatted = nfInt.format(Number(intDigits));
  if (!hasDot) return intFormatted;
  return `${intFormatted}.${decDigits}`;
}

export function parseLkr(value: string | null | undefined): number {
  const cleaned = String(value ?? "").replace(/,/g, "").trim();
  if (!cleaned || cleaned === ".") return 0;
  const n = Number(cleaned);
  return Number.isFinite(n) && n >= 0 ? roundLkr(n) : 0;
}

/** Display label e.g. 2024_25 → 2024/25 */
export function yaDisplay(ya: string): string {
  const m = /^(\d{4})_(\d{2})$/.exec(ya);
  if (!m) return ya;
  return `${m[1]}/${m[2]}`;
}
