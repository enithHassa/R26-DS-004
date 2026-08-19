import { formatLkr } from "../format-lkr";
import type { UnresolvedClaim } from "../api";
import { CLAIM_CONCEPT_LABELS } from "../taxpayer-labels";

function claimSentence(claim: UnresolvedClaim): string {
  const label = CLAIM_CONCEPT_LABELS[claim.concept_id];
  if (label) {
    return `You claimed ${label} (${formatLkr(claim.claimed_lkr)}) but we couldn't confirm it against the current tax rules, so it wasn't deducted from your taxable income.`;
  }
  return "You claimed an amount we couldn't confirm against the current tax rules, so it wasn't deducted from your taxable income.";
}

export function UnresolvedClaimsBanner({ claims }: { claims: UnresolvedClaim[] }) {
  if (claims.length === 0) return null;
  return (
    <div
      className="rounded-lg border border-amber-400/70 bg-amber-50 px-3 py-2.5 text-xs text-amber-950 dark:bg-amber-950/40 dark:text-amber-100"
      role="status"
    >
      <p className="mb-1 font-semibold">Some amounts were not deducted</p>
      <ul className="space-y-1">
        {claims.map((claim) => (
          <li key={`${claim.concept_id}:${claim.reason}`}>{claimSentence(claim)}</li>
        ))}
      </ul>
    </div>
  );
}
