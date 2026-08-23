/**
 * Sec 52(3) framing notice (personal relief for non-resident citizens).
 * Out of scope for resident-individual Relief Interview (calculate is always resident).
 */

export const NON_RESIDENT_CITIZEN_RELIEF_GROUP =
  "non_resident_citizen_relief_deduction";

export function isNonResidentCitizenReliefGroup(
  compareGroupId: string,
): boolean {
  return compareGroupId === NON_RESIDENT_CITIZEN_RELIEF_GROUP;
}
