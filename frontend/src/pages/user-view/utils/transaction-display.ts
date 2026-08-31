export function formatTransactionDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("en-LK", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function transactionStatusLabel(status: string, needsReview = false): string {
  if (needsReview || status === "unknown") return "Uncertain";
  switch (status) {
    case "taxable":
      return "Taxable";
    case "exempt":
      return "Non-Taxable";
    case "partially_taxable":
      return "Partial";
    default:
      return status;
  }
}

export function transactionStatusClass(status: string, needsReview = false): string {
  if (needsReview || status === "unknown") {
    return "bg-amber-500/15 text-amber-300";
  }
  if (status === "taxable") return "bg-red-500/15 text-red-300";
  if (status === "exempt") return "bg-emerald-500/15 text-emerald-300";
  return "bg-sky-500/15 text-sky-300";
}

export function categoryLabel(value: string): string {
  return value.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

export function complianceSubtext(score: number | null | undefined): string {
  if (score == null) return "No released transactions yet";
  if (score >= 90) return "Excellent standing";
  if (score >= 75) return "Good — a few items to review";
  if (score >= 50) return "Review recommended";
  return "Several items need attention";
}
