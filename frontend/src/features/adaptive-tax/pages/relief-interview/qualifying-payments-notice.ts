/**
 * Sec 52(1) framing notice (“aggregate Fifth Schedule qualifying payments”).
 * Not a claimable amount — QPs are already entered on earlier interview steps.
 */

export const QUALIFYING_PAYMENTS_DEDUCTION_GROUP = "qualifying_payments_deduction";

export function isQualifyingPaymentsDeductionGroup(
  compareGroupId: string,
): boolean {
  return compareGroupId === QUALIFYING_PAYMENTS_DEDUCTION_GROUP;
}
