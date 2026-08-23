/**
 * Sec 52 framing notice (“aggregate Fifth Schedule reliefs for residents”).
 * Not a claimable amount — removed from individual Relief Interview UX.
 */

export const RESIDENT_RELIEFS_DEDUCTION_GROUP = "resident_reliefs_deduction";

export function isResidentReliefsDeductionGroup(compareGroupId: string): boolean {
  return compareGroupId === RESIDENT_RELIEFS_DEDUCTION_GROUP;
}
